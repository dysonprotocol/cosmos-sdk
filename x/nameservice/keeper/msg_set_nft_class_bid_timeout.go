package keeper

import (
	"context"

	cosmossdkerrors "cosmossdk.io/errors"
	nameservicev1 "dysonprotocol.com/x/nameservice/types"
	sdk "github.com/cosmos/cosmos-sdk/types"
	sdkerrors "github.com/cosmos/cosmos-sdk/types/errors"
)

// SetNFTClassBidTimeout handles MsgSetNFTClassBidTimeout
func (k Keeper) SetNFTClassBidTimeout(ctx context.Context, msg *nameservicev1.MsgSetNFTClassBidTimeout) (*nameservicev1.MsgSetNFTClassBidTimeoutResponse, error) {
	if err := k.VerifyClassRootDestination(ctx, msg.ClassId, msg.NameDestination); err != nil {
		return nil, cosmossdkerrors.Wrap(err, "unauthorized to set bid_timeout")
	}

	classData, err := k.GetNFTClassData(ctx, msg.ClassId)
	if err != nil {
		return nil, err
	}

	// Validate against params bounds
	params := k.GetParams(ctx)
	if msg.BidTimeout < params.MinBidTimeoutClass || msg.BidTimeout > params.MaxBidTimeoutClass {
		return nil, cosmossdkerrors.Wrapf(sdkerrors.ErrInvalidRequest, "bid_timeout must be within class bounds [%s,%s]", params.MinBidTimeoutClass, params.MaxBidTimeoutClass)
	}

	// Assign new duration
	classData.BidTimeout = msg.BidTimeout

	if err := k.SetNFTClassData(ctx, msg.ClassId, classData); err != nil {
		return nil, err
	}

	// Emit event
	sdkCtx := sdk.UnwrapSDKContext(ctx)
	if evErr := sdkCtx.EventManager().EmitTypedEvent(&nameservicev1.EventNFTClassDataUpdated{ClassId: msg.ClassId}); evErr != nil {
		return nil, cosmossdkerrors.Wrap(evErr, "failed to emit NFT class data updated event")
	}

	return &nameservicev1.MsgSetNFTClassBidTimeoutResponse{}, nil
}
