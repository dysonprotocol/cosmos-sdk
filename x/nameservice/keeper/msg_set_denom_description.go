package keeper

import (
	"context"

	cosmossdkerrors "cosmossdk.io/errors"
	nameservicev1 "dysonprotocol.com/x/nameservice/types"
	sdk "github.com/cosmos/cosmos-sdk/types"
	sdkerrors "github.com/cosmos/cosmos-sdk/types/errors"
)

// SetDenomDescription allows the root name destination to set the bank metadata description field.
func (k Keeper) SetDenomDescription(ctx context.Context, msg *nameservicev1.MsgSetDenomDescription) (*nameservicev1.MsgSetDenomDescriptionResponse, error) {
	// Authorization: signer must control destination for denom root
	if err := k.VerifyDenomDestination(ctx, msg.Denom, msg.NameDestination); err != nil {
		return nil, err
	}

	// Ensure metadata exists (auto-create if missing)
	k.ensureDenomMetadata(ctx, msg.Denom)

	// Fetch, update, validate, save
	md, found := k.bankKeeper.GetDenomMetaData(ctx, msg.Denom)
	if !found {
		return nil, cosmossdkerrors.Wrapf(sdkerrors.ErrNotFound, "metadata not found for denom %s", msg.Denom)
	}

	md.Description = msg.Description
	if err := md.Validate(); err != nil {
		return nil, cosmossdkerrors.Wrap(err, "invalid metadata after description update")
	}

	k.bankKeeper.SetDenomMetaData(ctx, md)

	// Emit event for consistency with SetDenomMetadata
	if err := sdk.UnwrapSDKContext(ctx).EventManager().EmitTypedEvent(&nameservicev1.EventDenomMetadataSet{Denom: msg.Denom}); err != nil {
		return nil, cosmossdkerrors.Wrap(err, "failed to emit event")
	}

	return &nameservicev1.MsgSetDenomDescriptionResponse{}, nil
}
