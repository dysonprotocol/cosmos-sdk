package keeper

import (
	"context"

	whaleswapv1 "dysonprotocol.com/x/whaleswap/types"
)

var _ whaleswapv1.QueryServer = Keeper{}

func (k Keeper) Offer(ctx context.Context, req *whaleswapv1.QueryOfferRequest) (*whaleswapv1.QueryOfferResponse, error) {
	offer, err := k.OffersMap.Get(ctx, req.OfferId)
	if err != nil {
		return nil, err
	}
	return &whaleswapv1.QueryOfferResponse{Offer: &offer}, nil
}
