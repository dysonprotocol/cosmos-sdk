package keeper

import (
	"context"

	cosmossdkerrors "cosmossdk.io/errors"
	"cosmossdk.io/math"
	nameservicev1 "dysonprotocol.com/x/nameservice/types"
	sdk "github.com/cosmos/cosmos-sdk/types"
	sdkerrors "github.com/cosmos/cosmos-sdk/types/errors"
)

// SetNFTClassRejectBidValuationFeePercent handles MsgSetNFTClassRejectBidValuationFeePercent
func (k Keeper) SetNFTClassRejectBidValuationFeePercent(ctx context.Context, msg *nameservicev1.MsgSetNFTClassRejectBidValuationFeePercent) (*nameservicev1.MsgSetNFTClassRejectBidValuationFeePercentResponse, error) {
	if err := k.VerifyClassRootDestination(ctx, msg.ClassId, msg.NameDestination); err != nil {
		return nil, cosmossdkerrors.Wrap(err, "unauthorized to set reject fee percent")
	}

	classData, err := k.GetNFTClassData(ctx, msg.ClassId)
	if err != nil {
		return nil, err
	}

	// Validate against params bounds
	params := k.GetParams(ctx)
	value, err := math.LegacyNewDecFromStr(msg.RejectBidValuationFeePercent)
	if err != nil {
		return nil, cosmossdkerrors.Wrapf(sdkerrors.ErrInvalidRequest, "invalid reject fee percent: %s", msg.RejectBidValuationFeePercent)
	}
	minBound, err := math.LegacyNewDecFromStr(params.MinRejectBidValuationFeePercent)
	if err != nil {
		return nil, err
	}
	maxBound, err := math.LegacyNewDecFromStr(params.MaxRejectBidValuationFeePercent)
	if err != nil {
		return nil, err
	}
	if value.LT(minBound) || value.GT(maxBound) {
		return nil, cosmossdkerrors.Wrapf(sdkerrors.ErrInvalidRequest, "reject fee percent %s out of bounds [%s,%s]", value.String(), params.MinRejectBidValuationFeePercent, params.MaxRejectBidValuationFeePercent)
	}

	classData.RejectBidValuationFeePercent = msg.RejectBidValuationFeePercent

	if err := k.SetNFTClassData(ctx, msg.ClassId, classData); err != nil {
		return nil, err
	}

	sdkCtx := sdk.UnwrapSDKContext(ctx)
	if evErr := sdkCtx.EventManager().EmitTypedEvent(&nameservicev1.EventNFTClassDataUpdated{ClassId: msg.ClassId}); evErr != nil {
		return nil, cosmossdkerrors.Wrap(evErr, "failed to emit NFT class data updated event")
	}

	return &nameservicev1.MsgSetNFTClassRejectBidValuationFeePercentResponse{}, nil
}
