package keeper

import (
	"context"

	cosmossdkerrors "cosmossdk.io/errors"
	nameservicev1 "dysonprotocol.com/x/nameservice/types"
	sdkerrors "github.com/cosmos/cosmos-sdk/types/errors"
)

// SetDenomURI allows the root name destination to set bank metadata URI and URIHash.
func (k Keeper) SetDenomURI(ctx context.Context, msg *nameservicev1.MsgSetDenomURI) (*nameservicev1.MsgSetDenomURIResponse, error) {
	// Authorization: signer must control destination for denom root
	if err := k.VerifyDenomDestination(ctx, msg.Denom, msg.NameDestination); err != nil {
		return nil, err
	}

	// Ensure metadata exists (auto-create if missing)
	k.ensureDenomMetadata(ctx, msg.Denom)

	md, found := k.bankKeeper.GetDenomMetaData(ctx, msg.Denom)
	if !found {
		return nil, cosmossdkerrors.Wrapf(sdkerrors.ErrNotFound, "metadata not found for denom %s", msg.Denom)
	}

	// Apply optional fields
	md.URI = msg.Uri
	md.URIHash = msg.UriHash

	if err := md.Validate(); err != nil {
		return nil, cosmossdkerrors.Wrap(err, "invalid metadata after URI update")
	}

	k.bankKeeper.SetDenomMetaData(ctx, md)

	return &nameservicev1.MsgSetDenomURIResponse{}, nil
}
