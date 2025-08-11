package keeper

import (
	"context"
	"strconv"

	cosmossdkerrors "cosmossdk.io/errors"
	sdk "github.com/cosmos/cosmos-sdk/types"
	sdkerrors "github.com/cosmos/cosmos-sdk/types/errors"

	nameservicev1 "dysonprotocol.com/x/nameservice/types"
)

// SetNFTClassAnnualPct handles a MsgSetNFTClassAnnualPct message
func (k Keeper) SetNFTClassAnnualPct(ctx context.Context, msg *nameservicev1.MsgSetNFTClassAnnualPct) (*nameservicev1.MsgSetNFTClassAnnualPctResponse, error) {
    // Verify authorization: signer must match resolved destination of class root name
    if err := k.VerifyClassRootDestination(ctx, msg.ClassId, msg.NameDestination); err != nil {
        return nil, cosmossdkerrors.Wrapf(sdkerrors.ErrUnauthorized, "unauthorized to set annual_pct: %v", err)
    }

	// Parse and validate annual_pct range (0.0 to 1.0)
	annualPctFloat, err := strconv.ParseFloat(msg.AnnualPct, 64)
	if err != nil {
		return nil, cosmossdkerrors.Wrapf(
			sdkerrors.ErrInvalidRequest,
			"invalid annual_pct format: %s",
			msg.AnnualPct,
		)
	}

	if annualPctFloat < 0.0 || annualPctFloat > 1.0 {
		return nil, cosmossdkerrors.Wrapf(
			sdkerrors.ErrInvalidRequest,
			"annual_pct must be between 0.0 and 1.0, got: %s",
			msg.AnnualPct,
		)
	}

	// Get current NFT class data
	classData, err := k.GetNFTClassData(ctx, msg.ClassId)
	if err != nil {
		k.Logger.Error("SetNFTClassAnnualPct: Failed to get NFT class data",
			"class_id", msg.ClassId,
			"error", err)
		return nil, cosmossdkerrors.Wrapf(
			err,
			"NFT class not found: %s",
			msg.ClassId,
		)
	}

	// Update the annual_pct field (store as string directly)
	classData.AnnualPct = msg.AnnualPct

	// Set the updated NFT class data
	if err := k.SetNFTClassData(ctx, msg.ClassId, classData); err != nil {
		return nil, cosmossdkerrors.Wrapf(err, "failed to update NFT class data for class %s", msg.ClassId)
	}

	// Emit event
	sdkCtx := sdk.UnwrapSDKContext(ctx)
	if evErr := sdkCtx.EventManager().EmitTypedEvent(
		&nameservicev1.EventNFTClassAnnualPctUpdated{
			ClassId: msg.ClassId,
		},
	); evErr != nil {
		k.Logger.Error("failed to emit NFT class annual pct updated event", "error", evErr)
		return nil, cosmossdkerrors.Wrap(evErr, "failed to emit NFT class annual pct updated event")
	}

    k.Logger.Info("Successfully updated NFT class annual pct",
        "class_id", msg.ClassId,
        "name_destination", msg.NameDestination,
        "annual_pct", msg.AnnualPct)

	return &nameservicev1.MsgSetNFTClassAnnualPctResponse{}, nil
}
