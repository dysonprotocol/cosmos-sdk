package keeper

import (
	"context"
	"fmt"

	"cosmossdk.io/collections"
	whaleswapv1 "dysonprotocol.com/x/whaleswap/types"
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
	// If status provided, use owner+status index; else fall back to filtered scan
	if owner != "" && status != "" {
		results, pageRes, err := query.CollectionPaginate(
			ctx,
			k.OffersByOwnerStatus,
			req.Pagination,
			func(key collections.Triple[string, string, uint64], value uint64) (*whaleswapv1.OfferData, error) {
				if k1, k2, _ := key.K1(), key.K2(), key.K3(); k1 == owner && k2 == status {
					v, err := k.OffersMap.Get(ctx, value)
					if err != nil {
						return nil, err
					}
					return &v, nil
				}
				return nil, nil
			},
		)
		if err != nil {
			return nil, err
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
		return nil, err
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
					return nil, err
				}
				if v.RemainingHave.Denom != have || v.RemainingWant.Denom != want {
					return nil, nil
				}
				return &v, nil
			},
		)
		if err != nil {
			return nil, err
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
					return nil, err
				}
				if want != "" && v.RemainingWant.Denom != want {
					return nil, nil
				}
				return &v, nil
			},
		)
		if err != nil {
			return nil, err
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
					return nil, err
				}
				if have != "" && v.RemainingHave.Denom != have {
					return nil, nil
				}
				return &v, nil
			},
		)
		if err != nil {
			return nil, err
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
		return nil, err
	}
	return &whaleswapv1.QueryOffersResponse{Offers: offers, Pagination: pageRes}, nil
}
