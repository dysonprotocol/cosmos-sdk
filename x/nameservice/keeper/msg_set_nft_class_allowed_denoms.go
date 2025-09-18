package keeper

import (
	"context"

	cosmossdkerrors "cosmossdk.io/errors"
	nameservicev1 "dysonprotocol.com/x/nameservice/types"
	sdk "github.com/cosmos/cosmos-sdk/types"
	sdkerrors "github.com/cosmos/cosmos-sdk/types/errors"
)

// SetNFTClassAllowedDenoms handles MsgSetNFTClassAllowedDenoms
func (k Keeper) SetNFTClassAllowedDenoms(ctx context.Context, msg *nameservicev1.MsgSetNFTClassAllowedDenoms) (*nameservicev1.MsgSetNFTClassAllowedDenomsResponse, error) {
	if err := k.VerifyClassRootDestination(ctx, msg.ClassId, msg.NameDestination); err != nil {
		return nil, cosmossdkerrors.Wrap(err, "unauthorized to set allowed_denoms")
	}

	classData, err := k.GetNFTClassData(ctx, msg.ClassId)
	if err != nil {
		return nil, err
	}

	// Basic validation: no empty denoms and must include udys (policy consistent with module default validator)
	if len(msg.AllowedDenoms) == 0 {
		return nil, cosmossdkerrors.Wrap(sdkerrors.ErrInvalidRequest, "allowed_denoms list cannot be empty")
	}
	for _, d := range msg.AllowedDenoms {
		// Ensure denom currently exists on-chain (has supply record)
		if !k.bankKeeper.HasSupply(ctx, d) {
			return nil, cosmossdkerrors.Wrapf(sdkerrors.ErrInvalidRequest, "denom has no current supply: %s", d)
		}

	}

	classData.AllowedDenoms = msg.AllowedDenoms

	if err := k.SetNFTClassData(ctx, msg.ClassId, classData); err != nil {
		return nil, err
	}

	sdkCtx := sdk.UnwrapSDKContext(ctx)
	if evErr := sdkCtx.EventManager().EmitTypedEvent(&nameservicev1.EventNFTClassDataUpdated{ClassId: msg.ClassId}); evErr != nil {
		return nil, cosmossdkerrors.Wrap(evErr, "failed to emit NFT class data updated event")
	}

	return &nameservicev1.MsgSetNFTClassAllowedDenomsResponse{}, nil
}
