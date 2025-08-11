package keeper

import (
	"context"

	cosmossdkerrors "cosmossdk.io/errors"
	sdk "github.com/cosmos/cosmos-sdk/types"
	sdkerrors "github.com/cosmos/cosmos-sdk/types/errors"

	nameservicev1 "dysonprotocol.com/x/nameservice/types"
)

// SetNFTClassExtraData handles a MsgSetNFTClassExtraData message
func (k Keeper) SetNFTClassExtraData(ctx context.Context, msg *nameservicev1.MsgSetNFTClassExtraData) (*nameservicev1.MsgSetNFTClassExtraDataResponse, error) {
	// Verify authorization: signer must match resolved destination of class root name
	if err := k.VerifyClassRootDestination(ctx, msg.ClassId, msg.NameDestination); err != nil {
		return nil, cosmossdkerrors.Wrapf(sdkerrors.ErrUnauthorized, "unauthorized to set class extra data: %v", err)
	}

	// Get current NFT class data
	classData, err := k.GetNFTClassData(ctx, msg.ClassId)
	if err != nil {
		k.Logger.Error("SetNFTClassExtraData: Failed to get NFT class data",
			"class_id", msg.ClassId,
			"error", err)
		return nil, cosmossdkerrors.Wrapf(
			err,
			"NFT class not found: %s",
			msg.ClassId,
		)
	}

	// Update the extra_data field
	classData.ExtraData = msg.ExtraData

	// Set the updated NFT class data
	if err := k.SetNFTClassData(ctx, msg.ClassId, classData); err != nil {
		return nil, cosmossdkerrors.Wrapf(err, "failed to update NFT class data for class %s", msg.ClassId)
	}

	// Emit event
	sdkCtx := sdk.UnwrapSDKContext(ctx)
	if evErr := sdkCtx.EventManager().EmitTypedEvent(
		&nameservicev1.EventNFTClassExtraDataUpdated{
			ClassId: msg.ClassId,
		},
	); evErr != nil {
		k.Logger.Error("failed to emit NFT class extra data updated event", "error", evErr)
		return nil, cosmossdkerrors.Wrap(evErr, "failed to emit NFT class extra data updated event")
	}

	k.Logger.Info("Successfully updated NFT class extra data",
		"class_id", msg.ClassId,
		"name_destination", msg.NameDestination)

	return &nameservicev1.MsgSetNFTClassExtraDataResponse{}, nil
}
