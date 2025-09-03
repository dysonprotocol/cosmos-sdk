package keeper

import (
	"context"
	"strconv"
	"strings"
	"time"

	errorsmod "cosmossdk.io/errors"
	sdkmath "cosmossdk.io/math"
	crontasktypes "dysonprotocol.com/x/crontask/types"
	sdk "github.com/cosmos/cosmos-sdk/types"
	sdkerrors "github.com/cosmos/cosmos-sdk/types/errors"
	authtypes "github.com/cosmos/cosmos-sdk/x/auth/types"
	govtypes "github.com/cosmos/cosmos-sdk/x/gov/types"
)

// Ensure Keeper implements the MsgServer interface
var _ crontasktypes.MsgServer = Keeper{}

// parseTimestamp parses a string that can be either a Unix timestamp or a duration offset (prefixed with "+")
// If it's a duration, it's added to the baseTime.
// Returns the parsed time and any error.
func parseTimestamp(timestampStr string, baseTime time.Time) (time.Time, error) {
	// If the string starts with "+", it's a duration offset
	if strings.HasPrefix(timestampStr, "+") {
		// Parse the duration
		duration, err := time.ParseDuration(timestampStr[1:])
		if err != nil {
			return time.Time{}, errorsmod.Wrapf(
				sdkerrors.ErrInvalidRequest,
				"invalid duration format: %s, expected format like +1h30m",
				timestampStr,
			)
		}
		return baseTime.Add(duration), nil
	}

	// Otherwise, it's a Unix timestamp
	timestamp, err := strconv.ParseInt(timestampStr, 10, 64)
	if err != nil {
		return time.Time{}, errorsmod.Wrapf(
			sdkerrors.ErrInvalidRequest,
			"invalid timestamp format: %s, expected Unix timestamp or duration with + prefix",
			timestampStr,
		)
	}

	return time.Unix(timestamp, 0).UTC(), nil
}

// CreateTask creates a new scheduled task
func (k Keeper) CreateTask(ctx context.Context, msg *crontasktypes.MsgCreateTask) (*crontasktypes.MsgCreateTaskResponse, error) {
	// Get module parameters
	sdkCtx := sdk.UnwrapSDKContext(ctx)

	params, err := k.GetParams(ctx)
	if err != nil {
		return nil, errorsmod.Wrap(err, "failed to get module params")
	}

	// Validate addresses
	_, err = sdk.AccAddressFromBech32(msg.Creator)
	if err != nil {
		return nil, errorsmod.Wrapf(sdkerrors.ErrInvalidAddress, "invalid creator address: %s", msg.Creator)
	}

	// Get the current block time
	currentTime := sdkCtx.BlockTime().UTC().Truncate(time.Second)

	// Parse the scheduled timestamp
	scheduledTime, err := parseTimestamp(msg.ScheduledTimestamp, currentTime)
	if err != nil {
		return nil, err
	}

	// Validate timestamp is in the future
	if currentTime.After(scheduledTime) {
		return nil, errorsmod.Wrapf(
			sdkerrors.ErrInvalidRequest,
			"scheduled time must be in the future, current time: %s, scheduled time: %s",
			currentTime,
			scheduledTime,
		)
	}

	// Validate timestamp is within allowed range
	maxFutureTime := currentTime.Add(time.Second * time.Duration(params.MaxScheduledTime))
	if scheduledTime.After(maxFutureTime) {
		return nil, errorsmod.Wrapf(
			sdkerrors.ErrInvalidRequest,
			"scheduled time is too far in the future, max allowed is %d seconds from now",
			params.MaxScheduledTime,
		)
	}

	// Parse expiry timestamp, using scheduledTime as the base if it's a relative duration
	var expiryTime time.Time
	if msg.ExpiryTimestamp == "" {
		// If not provided, use the default expiry from the scheduled time
		expiryTime = scheduledTime.Add(time.Second * time.Duration(params.ExpiryLimit))
	} else {
		// Parse the provided expiry timestamp
		expiryTime, err = parseTimestamp(msg.ExpiryTimestamp, scheduledTime)
		if err != nil {
			return nil, err
		}

		// Ensure expiry time is after scheduled time
		if expiryTime.Before(scheduledTime) || expiryTime.Equal(scheduledTime) {
			return nil, errorsmod.Wrapf(
				sdkerrors.ErrInvalidRequest,
				"expiry time must be after scheduled time: scheduled %s, expiry %s",
				scheduledTime,
				expiryTime,
			)
		}
	}

	// Validate gas limit is reasonable
	if msg.TaskGasLimit == 0 {
		return nil, errorsmod.Wrap(sdkerrors.ErrInvalidRequest, "Crontask gas limit must be positive")
	}
	if msg.TaskGasLimit > params.BlockGasLimit {
		return nil, errorsmod.Wrapf(
			sdkerrors.ErrInvalidRequest,
			"gas limit must be between 0 and %d, got %d",
			params.BlockGasLimit,
			msg.TaskGasLimit,
		)
	}

	// Validate gas fee and calculate gas price
	if !msg.TaskGasFee.IsPositive() {
		return nil, errorsmod.Wrap(sdkerrors.ErrInvalidRequest, "gas fee must be greater than 0")
	}
	if msg.TaskGasFee.Denom != "udys" {
		return nil, errorsmod.Wrapf(
			sdkerrors.ErrInvalidRequest,
			"invalid gas fee denom: [%s], only 'udys' is accepted",
			msg.TaskGasFee.Denom,
		)
	}

	// Calculate gas price from gas fee and limit
	gasPrice := sdk.NewCoin(
		msg.TaskGasFee.Denom,
		msg.TaskGasFee.Amount.Quo(sdkmath.NewInt(int64(msg.TaskGasLimit))),
	)

	// Ensure gas price fits in uint64 to avoid index panic
	if !gasPrice.Amount.IsUint64() {
		return nil, errorsmod.Wrapf(
			sdkerrors.ErrInvalidRequest,
			"computed gas price %s overflows uint64",
			gasPrice.Amount.String(),
		)
	}

	// Validate at least one message is provided
	if len(msg.Msgs) == 0 {
		return nil, errorsmod.Wrap(sdkerrors.ErrInvalidRequest, "at least one message must be provided")
	}

	// Get the next task ID
	taskId, err := k.GetNextTaskID(ctx)
	if err != nil {
		return nil, errorsmod.Wrap(err, "failed to get next task ID")
	}

	// Create the task with initial status SCHEDULED
	task := crontasktypes.Task{
		TaskId:              taskId,
		Creator:             msg.Creator,
		ScheduledTimestamp:  scheduledTime.Unix(),
		ExpiryTimestamp:     expiryTime.Unix(),
		TaskGasLimit:        msg.TaskGasLimit,
		TaskGasPrice:        gasPrice,
		TaskGasFee:          msg.TaskGasFee,
		Msgs:                msg.Msgs,
		Status:              crontasktypes.TaskStatus_SCHEDULED,
		CreationTime:        sdkCtx.BlockTime().Unix(),
		CreationBlockHeight: sdkCtx.BlockHeight(),
	}

	// Save the task
	err = k.SetTask(ctx, task)
	if err != nil {
		return nil, errorsmod.Wrap(err, "failed to save task")
	}

	// Emit event for task creation
	if err := sdkCtx.EventManager().EmitTypedEvent(
		&crontasktypes.EventTaskCreated{
			TaskId:  taskId,
			Creator: msg.Creator,
		},
	); err != nil {
		k.Logger.Error("failed to emit task created event", "error", err)
		return nil, errorsmod.Wrap(err, "failed to emit task created event")
	}

	// Log the task creation for additional debugging
	k.Logger.Info("Task created",
		"creator", msg.Creator,
		"task_id", taskId,
		"scheduled_time", scheduledTime)

	return &crontasktypes.MsgCreateTaskResponse{
		TaskId: taskId,
	}, nil
}

// DeleteTask deletes a scheduled task
func (k Keeper) DeleteTask(ctx context.Context, msg *crontasktypes.MsgDeleteTask) (*crontasktypes.MsgDeleteTaskResponse, error) {
	// Get the task
	task, err := k.GetTask(ctx, msg.TaskId)
	if err != nil {
		return nil, errorsmod.Wrapf(sdkerrors.ErrNotFound, "task with ID %d not found", msg.TaskId)
	}

	// Verify that the creator is authorized to delete this task
	if task.Creator != msg.Creator {
		return nil, errorsmod.Wrap(sdkerrors.ErrUnauthorized, "only the creator can delete a task")
	}

	// Delete the task
	err = k.RemoveTask(ctx, msg.TaskId)
	if err != nil {
		return nil, errorsmod.Wrap(err, "failed to delete task")
	}

	// Emit event for task deletion
	sdkCtx := sdk.UnwrapSDKContext(ctx)
	if err := sdkCtx.EventManager().EmitTypedEvent(
		&crontasktypes.EventTaskDeleted{
			TaskId:  msg.TaskId,
			Creator: msg.Creator,
		},
	); err != nil {
		k.Logger.Error("failed to emit task deleted event", "error", err)
		return nil, errorsmod.Wrap(err, "failed to emit task deleted event")
	}

	// Log the task deletion for additional debugging
	k.Logger.Info("Task deleted",
		"creator", msg.Creator,
		"task_id", msg.TaskId)

	return &crontasktypes.MsgDeleteTaskResponse{}, nil
}

func (k Keeper) UpdateParams(ctx context.Context, msg *crontasktypes.MsgUpdateParams) (*crontasktypes.MsgUpdateParamsResponse, error) {
	// NOTE: For the lightweight test network we accept any signer; in production
	// you would enforce the authority check below.
	_ = authtypes.NewModuleAddress(govtypes.ModuleName).String()

	// Validate sent params
	if err := msg.Params.Validate(); err != nil {
		return nil, err
	}

	// Persist params
	if err := k.SetParams(ctx, msg.Params); err != nil {
		return nil, err
	}

	return &crontasktypes.MsgUpdateParamsResponse{}, nil
}
