package keeper

import (
	"context"

	cosmossdkerrors "cosmossdk.io/errors"
	math "cosmossdk.io/math"
	sdk "github.com/cosmos/cosmos-sdk/types"
	sdkerrors "github.com/cosmos/cosmos-sdk/types/errors"

	nameservicev1 "dysonprotocol.com/x/nameservice/types"
)

// SetNFTClassValuationFeePct handles MsgSetNFTClassValuationFeePct
func (k Keeper) SetNFTClassValuationFeePct(ctx context.Context, msg *nameservicev1.MsgSetNFTClassValuationFeePct) (*nameservicev1.MsgSetNFTClassValuationFeePctResponse, error) {
	k.Logger.Info("SetNFTClassValuationFeePct: received",
		"class_id", msg.ClassId,
		"name_destination", msg.NameDestination,
		"valuation_fee_pct_raw", msg.ValuationFeePct,
	)
	if err := k.VerifyClassRootDestination(ctx, msg.ClassId, msg.NameDestination); err != nil {
		return nil, cosmossdkerrors.Wrapf(sdkerrors.ErrUnauthorized, "unauthorized to set valuation fee pct: %v", err)
	}

	// Validate bounds against Params and ensure provided pct within [min,max]
	params := k.GetParams(ctx)
	k.Logger.Info("SetNFTClassValuationFeePct: params bounds (raw)",
		"min_valuation_fee_pct", params.MinValuationFeePct,
		"max_valuation_fee_pct", params.MaxValuationFeePct,
	)
	minDec, err := math.LegacyNewDecFromStr(params.MinValuationFeePct)
	if err != nil {
		return nil, cosmossdkerrors.Wrap(err, "invalid min_valuation_fee_pct")
	}
	maxDec, err := math.LegacyNewDecFromStr(params.MaxValuationFeePct)
	if err != nil {
		return nil, cosmossdkerrors.Wrap(err, "invalid max_valuation_fee_pct")
	}
	k.Logger.Info("SetNFTClassValuationFeePct: params bounds (parsed)",
		"min_valuation_fee_pct_dec", minDec.String(),
		"max_valuation_fee_pct_dec", maxDec.String(),
	)

	valDec, err := math.LegacyNewDecFromStr(msg.ValuationFeePct)
	if err != nil {
		return nil, cosmossdkerrors.Wrap(err, "invalid valuation_fee_pct")
	}
	k.Logger.Info("SetNFTClassValuationFeePct: parsed valuation pct",
		"valuation_fee_pct_dec", valDec.String(),
	)
	if valDec.LT(minDec) || valDec.GT(maxDec) {
		return nil, cosmossdkerrors.Wrapf(sdkerrors.ErrInvalidRequest, "valuation_fee_pct %s out of bounds [%s,%s]", valDec.String(), minDec.String(), maxDec.String())
	}

	classData, err := k.GetNFTClassData(ctx, msg.ClassId)
	if err != nil {
		return nil, cosmossdkerrors.Wrapf(err, "NFT class not found: %s", msg.ClassId)
	}
	oldPct := classData.ValuationFeePct
	classData.ValuationFeePct = msg.ValuationFeePct
	if err := k.SetNFTClassData(ctx, msg.ClassId, classData); err != nil {
		return nil, cosmossdkerrors.Wrapf(err, "failed to update NFT class data for class %s", msg.ClassId)
	}
	k.Logger.Info("SetNFTClassValuationFeePct: updated class data",
		"class_id", msg.ClassId,
		"old_pct", oldPct,
		"new_pct", classData.ValuationFeePct,
	)

	sdkCtx := sdk.UnwrapSDKContext(ctx)
	if evErr := sdkCtx.EventManager().EmitTypedEvent(&nameservicev1.EventNFTClassDataUpdated{ClassId: msg.ClassId}); evErr != nil {
		return nil, cosmossdkerrors.Wrap(evErr, "failed to emit NFT class data updated event")
	}
	return &nameservicev1.MsgSetNFTClassValuationFeePctResponse{}, nil
}

// helper to ensure dec string v is within [min,max]
// (helper removed; inlined explicit checks in handlers)

// SetNFTClassValuationPeriod handles MsgSetNFTClassValuationPeriod
func (k Keeper) SetNFTClassValuationPeriod(ctx context.Context, msg *nameservicev1.MsgSetNFTClassValuationPeriod) (*nameservicev1.MsgSetNFTClassValuationPeriodResponse, error) {
	if err := k.VerifyClassRootDestination(ctx, msg.ClassId, msg.NameDestination); err != nil {
		return nil, cosmossdkerrors.Wrapf(sdkerrors.ErrUnauthorized, "unauthorized to set valuation period: %v", err)
	}
	params := k.GetParams(ctx)
	k.Logger.Info("SetNFTClassValuationPeriod: bounds and requested",
		"min_valuation_period", params.MinValuationPeriod.String(),
		"max_valuation_period", params.MaxValuationPeriod.String(),
		"requested", msg.ValuationPeriod.String(),
	)
	if msg.ValuationPeriod < params.MinValuationPeriod || msg.ValuationPeriod > params.MaxValuationPeriod {
		return nil, cosmossdkerrors.Wrapf(
			sdkerrors.ErrInvalidRequest,
			"valuation_period %s out of bounds [%s,%s]",
			msg.ValuationPeriod.String(),
			params.MinValuationPeriod.String(),
			params.MaxValuationPeriod.String(),
		)
	}
	classData, err := k.GetNFTClassData(ctx, msg.ClassId)
	if err != nil {
		return nil, cosmossdkerrors.Wrapf(err, "NFT class not found: %s", msg.ClassId)
	}
	oldPeriod := classData.ValuationPeriod
	classData.ValuationPeriod = msg.ValuationPeriod
	if err := k.SetNFTClassData(ctx, msg.ClassId, classData); err != nil {
		return nil, cosmossdkerrors.Wrapf(err, "failed to update NFT class data for class %s", msg.ClassId)
	}
	sdkCtx := sdk.UnwrapSDKContext(ctx)
	if evErr := sdkCtx.EventManager().EmitTypedEvent(&nameservicev1.EventNFTClassDataUpdated{ClassId: msg.ClassId}); evErr != nil {
		return nil, cosmossdkerrors.Wrap(evErr, "failed to emit NFT class data updated event")
	}
	k.Logger.Info("SetNFTClassValuationPeriod: updated class data",
		"class_id", msg.ClassId,
		"old_period", oldPeriod.String(),
		"new_period", classData.ValuationPeriod.String(),
	)
	return &nameservicev1.MsgSetNFTClassValuationPeriodResponse{}, nil
}
