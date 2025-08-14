package keeper

import (
	"context"

	cosmossdkerrors "cosmossdk.io/errors"
	nameservicev1 "dysonprotocol.com/x/nameservice/types"
	sdk "github.com/cosmos/cosmos-sdk/types"
	sdkerrors "github.com/cosmos/cosmos-sdk/types/errors"
)

// Commit implements the MsgServer.Commit method
func (k Keeper) Commit(ctx context.Context, msg *nameservicev1.MsgCommit) (*nameservicev1.MsgCommitResponse, error) {
	// Validate addresses
	_, err := sdk.AccAddressFromBech32(msg.Committer)
	if err != nil {
		return nil, cosmossdkerrors.Wrapf(sdkerrors.ErrInvalidAddress, "invalid committer address: %s", msg.Committer)
	}

	// Validate hash is not empty
	if msg.Hexhash == "" {
		return nil, cosmossdkerrors.Wrap(sdkerrors.ErrInvalidRequest, "commitment hash cannot be empty")
	}

	// Check if commitment already exists
	_, err = k.GetCommitment(ctx, msg.Hexhash)
	if err == nil {
		return nil, cosmossdkerrors.Wrap(sdkerrors.ErrInvalidRequest, "commitment already exists")
	}

	// Ensure the default nameservice class exists so valuation rules can be resolved
	if err := k.EnsureNamesClassExists(ctx); err != nil {
		return nil, err
	}

	// Validate the valuation
	err = k.ValidateValuation(ctx, NamesClassID, msg.Valuation)
	if err != nil {
		return nil, err
	}
	sdkCtx := sdk.UnwrapSDKContext(ctx)

	// Create and save the commitment
	commitment := nameservicev1.Commitment{
		Hexhash:   msg.Hexhash,
		Owner:     msg.Committer,
		Timestamp: sdkCtx.BlockTime(),
		Valuation: msg.Valuation,
	}

	err = k.SetCommitment(ctx, commitment)
	if err != nil {
		return nil, cosmossdkerrors.Wrap(err, "failed to save commitment")
	}

	// Emit event
	err = sdkCtx.EventManager().EmitTypedEvent(
		&nameservicev1.EventCommitmentCreated{
			Hexhash: msg.Hexhash,
		})
	if err != nil {
		k.Logger.Error("failed to emit commitment created event", "error", err)
		return nil, cosmossdkerrors.Wrap(err, "failed to emit commitment created event")
	}

	return &nameservicev1.MsgCommitResponse{}, nil
}
