package keeper

import (
	"context"

	cosmossdkerrors "cosmossdk.io/errors"
	"cosmossdk.io/math"
	nameservicev1 "dysonprotocol.com/x/nameservice/types"
	sdk "github.com/cosmos/cosmos-sdk/types"
	sdkerrors "github.com/cosmos/cosmos-sdk/types/errors"
)

// SetNFTClassMinimumBidPercentIncrease handles MsgSetNFTClassMinimumBidPercentIncrease
func (k Keeper) SetNFTClassMinimumBidPercentIncrease(ctx context.Context, msg *nameservicev1.MsgSetNFTClassMinimumBidPercentIncrease) (*nameservicev1.MsgSetNFTClassMinimumBidPercentIncreaseResponse, error) {
	if err := k.VerifyClassRootDestination(ctx, msg.ClassId, msg.NameDestination); err != nil {
		return nil, cosmossdkerrors.Wrap(err, "unauthorized to set minimum bid percent increase")
	}

	classData, err := k.GetNFTClassData(ctx, msg.ClassId)
	if err != nil {
		return nil, err
	}

	// Validate against params bounds
	params := k.GetParams(ctx)
	value, err := math.LegacyNewDecFromStr(msg.MinimumBidPercentIncrease)
	if err != nil {
		return nil, cosmossdkerrors.Wrapf(sdkerrors.ErrInvalidRequest, "invalid minimum bid percent increase: %s", msg.MinimumBidPercentIncrease)
	}
	minBound, err := math.LegacyNewDecFromStr(params.MinMinimumBidPercentIncrease)
	if err != nil {
		return nil, err
	}
	maxBound, err := math.LegacyNewDecFromStr(params.MaxMinimumBidPercentIncrease)
	if err != nil {
		return nil, err
	}
	if value.LT(minBound) || value.GT(maxBound) {
		return nil, cosmossdkerrors.Wrapf(sdkerrors.ErrInvalidRequest, "minimum bid percent increase %s out of bounds [%s,%s]", value.String(), params.MinMinimumBidPercentIncrease, params.MaxMinimumBidPercentIncrease)
	}

	classData.MinimumBidPercentIncrease = msg.MinimumBidPercentIncrease

	if err := k.SetNFTClassData(ctx, msg.ClassId, classData); err != nil {
		return nil, err
	}

	sdkCtx := sdk.UnwrapSDKContext(ctx)
	if evErr := sdkCtx.EventManager().EmitTypedEvent(&nameservicev1.EventNFTClassDataUpdated{ClassId: msg.ClassId}); evErr != nil {
		return nil, cosmossdkerrors.Wrap(evErr, "failed to emit NFT class data updated event")
	}

	return &nameservicev1.MsgSetNFTClassMinimumBidPercentIncreaseResponse{}, nil
}
