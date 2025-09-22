package keeper

import (
	"context"

	crontasktypes "dysonprotocol.com/x/crontask/types"
)

// InitGenesis initializes the module's state from a genesis state.
func (k Keeper) InitGenesis(ctx context.Context, genState *crontasktypes.GenesisState) error {
	// Validate the genesis state
	if err := crontasktypes.ValidateGenesis(genState); err != nil {
		return err
	}

	// Set module parameters - always set them regardless of genesis state
	var moduleParams crontasktypes.Params
	if genState.Params == nil {
		// Use default params if not provided
		moduleParams = crontasktypes.DefaultParams()
	} else {
		moduleParams = *genState.Params
	}

	// Set the parameters
	if err := k.Params.Set(ctx, moduleParams); err != nil {
		return err
	}

	// Determine the next task ID. If not provided (0) or stale (<= max task id),
	// default to max(existing tasks)+1 (or 1 if no tasks).
	var maxTaskID uint64
	for _, task := range genState.Tasks {
		if task.TaskId > maxTaskID {
			maxTaskID = task.TaskId
		}
	}
	nextTaskIDToSet := genState.NextTaskId
	if nextTaskIDToSet == 0 {
		if maxTaskID == 0 {
			nextTaskIDToSet = 1
		} else {
			nextTaskIDToSet = maxTaskID + 1
		}
	} else if nextTaskIDToSet <= maxTaskID {
		nextTaskIDToSet = maxTaskID + 1
	}
	if err := k.NextTaskID.Set(ctx, nextTaskIDToSet); err != nil {
		return err
	}

	// Import all tasks
	for _, task := range genState.Tasks {
		if err := k.Tasks.Set(ctx, task.TaskId, *task); err != nil {
			return err
		}
	}

	// Initialize subscription ID sequence. If not provided (0), default to 1.
	nextSubID := genState.NextSubscriptionId
	if nextSubID == 0 {
		nextSubID = 1
	}
	if err := k.NextSubscriptionID.Set(ctx, nextSubID); err != nil {
		return err
	}

	return nil
}

// ExportGenesis exports the module's state to a genesis state.
func (k Keeper) ExportGenesis(ctx context.Context) (*crontasktypes.GenesisState, error) {
	// Get params - simple error handling following SDK pattern
	params, err := k.Params.Get(ctx)
	if err != nil {
		return nil, err
	}

	// Get next task ID
	nextTaskID, err := k.NextTaskID.Peek(ctx)
	if err != nil {
		return nil, err // Direct error propagation
	}

	// Get next subscription ID
	nextSubscriptionID, err := k.NextSubscriptionID.Peek(ctx)
	if err != nil {
		return nil, err
	}

	// Get all tasks
	var tasks []*crontasktypes.Task
	if err := k.Tasks.Walk(ctx, nil, func(taskID uint64, task crontasktypes.Task) (bool, error) {
		taskCopy := task // Create a copy to avoid modifying the same memory
		tasks = append(tasks, &taskCopy)
		return false, nil
	}); err != nil {
		return nil, err // Direct error propagation
	}

	return &crontasktypes.GenesisState{
		Tasks:              tasks,
		NextTaskId:         nextTaskID,
		Params:             &params,
		NextSubscriptionId: nextSubscriptionID,
	}, nil
}
