package keeper

import (
	"context"
	"fmt"

	"cosmossdk.io/collections"
	cosmossdkerrors "cosmossdk.io/errors"
	whaleswapv1 "dysonprotocol.com/x/whaleswap/types"
	sdkerrors "github.com/cosmos/cosmos-sdk/types/errors"
	"github.com/cosmos/cosmos-sdk/types/query"
)

func (k Keeper) OffersByOwner(ctx context.Context, req *whaleswapv1.QueryOffersByOwnerRequest) (*whaleswapv1.QueryOffersByOwnerResponse, error) {
	if req == nil {
		req = &whaleswapv1.QueryOffersByOwnerRequest{}
	}
	owner := req.Owner
	status := req.Status
	if owner == "" {
		return nil, fmt.Errorf("owner required")
	}
	// If status provided, validate it and use owner+status index; else fall back to filtered scan
	if owner != "" && status != "" {
		if status != whaleswapv1.OfferStatusOpen && status != whaleswapv1.OfferStatusClosed && status != whaleswapv1.OfferStatusCancelled {
			return nil, cosmossdkerrors.Wrapf(sdkerrors.ErrInvalidRequest, "invalid status: %s", status)
		}
		results, pageRes, err := query.CollectionPaginate(
			ctx,
			k.OffersByOwnerStatus,
			req.Pagination,
			func(key collections.Triple[string, string, uint64], value uint64) (*whaleswapv1.OfferData, error) {
				if k1, k2, _ := key.K1(), key.K2(), key.K3(); k1 == owner && k2 == status {
					v, err := k.OffersMap.Get(ctx, value)
					if err != nil {
						return nil, cosmossdkerrors.Wrapf(err, "offer not found: %d", value)
					}
					return &v, nil
				}
				return nil, nil
			},
		)
		if err != nil {
			return nil, cosmossdkerrors.Wrapf(err, "paginate offers by owner/status failed: %s/%s", owner, status)
		}
		return &whaleswapv1.QueryOffersByOwnerResponse{Offers: results, Pagination: pageRes}, nil
	}
	// filtered scan fallback
	results, pageRes, err := query.CollectionPaginate(
		ctx,
		k.OffersMap,
		req.Pagination,
		func(key uint64, value whaleswapv1.OfferData) (*whaleswapv1.OfferData, error) {
			if owner != "" && value.Maker != owner {
				return nil, nil
			}
			if status != "" && value.Status != status {
				return nil, nil
			}
			v := value
			return &v, nil
		},
	)
	if err != nil {
		return nil, cosmossdkerrors.Wrap(err, "paginate offers failed")
	}
	return &whaleswapv1.QueryOffersByOwnerResponse{Offers: results, Pagination: pageRes}, nil
}

func (k Keeper) Offers(ctx context.Context, req *whaleswapv1.QueryOffersRequest) (*whaleswapv1.QueryOffersResponse, error) {
	if req == nil {
		req = &whaleswapv1.QueryOffersRequest{}
	}
	have := req.HaveDenom
	want := req.WantDenom

	// Case 1: both filters → pair+price index (pair key only; price ignored by predicate)
	if have != "" && want != "" {
		low, high := have, want
		if low > high {
			low, high = high, low
		}
		pairKey := low + "|" + high
		offers, pageRes, err := query.CollectionPaginate(
			ctx,
			k.OffersByPairPrice,
			req.Pagination,
			func(key collections.Triple[string, string, uint64], id uint64) (*whaleswapv1.OfferData, error) {
				k1, _, _ := key.K1(), key.K2(), key.K3()
				if k1 != pairKey {
					return nil, nil
				}
				v, err := k.OffersMap.Get(ctx, id)
				if err != nil {
					return nil, cosmossdkerrors.Wrapf(err, "offer not found: %d", id)
				}
				if v.RemainingHave.Denom != have || v.RemainingWant.Denom != want {
					return nil, nil
				}
				return &v, nil
			},
		)
		if err != nil {
			return nil, cosmossdkerrors.Wrapf(err, "paginate offers by pair failed: %s", pairKey)
		}
		return &whaleswapv1.QueryOffersResponse{Offers: offers, Pagination: pageRes}, nil
	}

	// Case 2: single filter by have
	if have != "" {
		offers, pageRes, err := query.CollectionPaginate(
			ctx,
			k.OffersByHave,
			req.Pagination,
			func(key collections.Pair[string, uint64], id uint64) (*whaleswapv1.OfferData, error) {
				if k1, _ := key.K1(), key.K2(); k1 != have {
					return nil, nil
				}
				v, err := k.OffersMap.Get(ctx, id)
				if err != nil {
					return nil, cosmossdkerrors.Wrapf(err, "offer not found: %d", id)
				}
				if want != "" && v.RemainingWant.Denom != want {
					return nil, nil
				}
				return &v, nil
			},
		)
		if err != nil {
			return nil, cosmossdkerrors.Wrapf(err, "paginate offers by have failed: %s", have)
		}
		return &whaleswapv1.QueryOffersResponse{Offers: offers, Pagination: pageRes}, nil
	}

	// Case 3: single filter by want
	if want != "" {
		offers, pageRes, err := query.CollectionPaginate(
			ctx,
			k.OffersByWant,
			req.Pagination,
			func(key collections.Pair[string, uint64], id uint64) (*whaleswapv1.OfferData, error) {
				if k1, _ := key.K1(), key.K2(); k1 != want {
					return nil, nil
				}
				v, err := k.OffersMap.Get(ctx, id)
				if err != nil {
					return nil, cosmossdkerrors.Wrapf(err, "offer not found: %d", id)
				}
				if have != "" && v.RemainingHave.Denom != have {
					return nil, nil
				}
				return &v, nil
			},
		)
		if err != nil {
			return nil, cosmossdkerrors.Wrapf(err, "paginate offers by want failed: %s", want)
		}
		return &whaleswapv1.QueryOffersResponse{Offers: offers, Pagination: pageRes}, nil
	}

	// Case 4: no filters → full scan
	offers, pageRes, err := query.CollectionPaginate(
		ctx,
		k.OffersMap,
		req.Pagination,
		func(key uint64, value whaleswapv1.OfferData) (*whaleswapv1.OfferData, error) {
			v := value
			return &v, nil
		},
	)
	if err != nil {
		return nil, cosmossdkerrors.Wrap(err, "paginate offers failed")
	}
	return &whaleswapv1.QueryOffersResponse{Offers: offers, Pagination: pageRes}, nil
}
