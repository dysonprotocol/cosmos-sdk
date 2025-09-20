package keeper

import (
	"context"

	"cosmossdk.io/collections"
	cosmossdkerrors "cosmossdk.io/errors"
	cosmossdk_math "cosmossdk.io/math"
	whaleswapv1 "dysonprotocol.com/x/whaleswap/types"
	sdkerrors "github.com/cosmos/cosmos-sdk/types/errors"
	"github.com/cosmos/cosmos-sdk/types/query"
)

func (k Keeper) OffersByDenom(ctx context.Context, req *whaleswapv1.QueryOffersByDenomRequest) (*whaleswapv1.QueryOffersResponse, error) {
	if req == nil {
		req = &whaleswapv1.QueryOffersByDenomRequest{}
	}
	if req.Denom == "" {
		return nil, cosmossdkerrors.Wrap(sdkerrors.ErrInvalidRequest, "denom required")
	}
	role := req.Role
	if role == "have" {
		results, pageRes, err := query.CollectionPaginate(ctx, k.OffersByHave, req.Pagination, func(key collections.Pair[string, uint64], id uint64) (*whaleswapv1.OfferData, error) {
			if k1, _ := key.K1(), key.K2(); k1 != req.Denom {
				return nil, nil
			}
			v, err := k.OffersMap.Get(ctx, id)
			if err != nil {
				return nil, err
			}
			return &v, nil
		})
		if err != nil {
			return nil, cosmossdkerrors.Wrap(err, "paginate offers by have failed")
		}
		return &whaleswapv1.QueryOffersResponse{Offers: results, Pagination: pageRes}, nil
	}
	if role == "want" {
		results, pageRes, err := query.CollectionPaginate(ctx, k.OffersByWant, req.Pagination, func(key collections.Pair[string, uint64], id uint64) (*whaleswapv1.OfferData, error) {
			if k1, _ := key.K1(), key.K2(); k1 != req.Denom {
				return nil, nil
			}
			v, err := k.OffersMap.Get(ctx, id)
			if err != nil {
				return nil, err
			}
			return &v, nil
		})
		if err != nil {
			return nil, cosmossdkerrors.Wrap(err, "paginate offers by want failed")
		}
		return &whaleswapv1.QueryOffersResponse{Offers: results, Pagination: pageRes}, nil
	}
	// role empty -> either side: fallback to scan
	results, pageRes, err := query.CollectionPaginate(ctx, k.OffersMap, req.Pagination, func(key uint64, value whaleswapv1.OfferData) (*whaleswapv1.OfferData, error) {
		if value.RemainingHave.Denom != req.Denom && value.RemainingWant.Denom != req.Denom {
			return nil, nil
		}
		v := value
		return &v, nil
	})
	if err != nil {
		return nil, cosmossdkerrors.Wrap(err, "paginate offers by denom failed")
	}
	return &whaleswapv1.QueryOffersResponse{Offers: results, Pagination: pageRes}, nil
}

func (k Keeper) OffersByPairPriceRange(ctx context.Context, req *whaleswapv1.QueryOffersByPairPriceRangeRequest) (*whaleswapv1.QueryOffersResponse, error) {
	if req == nil {
		req = &whaleswapv1.QueryOffersByPairPriceRangeRequest{}
	}
	if req.HaveDenom == "" || req.WantDenom == "" {
		return nil, cosmossdkerrors.Wrap(sdkerrors.ErrInvalidRequest, "have_denom and want_denom required")
	}
	var minDec, maxDec cosmossdk_math.LegacyDec
	var err error
	if req.MinPrice != "" {
		minDec, err = cosmossdk_math.LegacyNewDecFromStr(req.MinPrice)
		if err != nil {
			return nil, cosmossdkerrors.Wrapf(sdkerrors.ErrInvalidRequest, "invalid min_price: %s", req.MinPrice)
		}
	}
	if req.MaxPrice != "" {
		maxDec, err = cosmossdk_math.LegacyNewDecFromStr(req.MaxPrice)
		if err != nil {
			return nil, cosmossdkerrors.Wrapf(sdkerrors.ErrInvalidRequest, "invalid max_price: %s", req.MaxPrice)
		}
	}
	// Scan using pair+price index for ordering, but filter by requested orientation (want-per-have)
	low, high := req.HaveDenom, req.WantDenom
	if low > high {
		low, high = high, low
	}
	pairKey := low + "|" + high
	results, pageRes, perr := query.CollectionPaginate(ctx, k.OffersByPairPrice, req.Pagination, func(key collections.Triple[string, string, uint64], id uint64) (*whaleswapv1.OfferData, error) {
		k1, _, _ := key.K1(), key.K2(), key.K3()
		if k1 != pairKey {
			return nil, nil
		}
		v, err := k.OffersMap.Get(ctx, id)
		if err != nil {
			return nil, err
		}
		// ensure exact direction match
		if v.RemainingHave.Denom != req.HaveDenom || v.RemainingWant.Denom != req.WantDenom {
			return nil, nil
		}
		price := cosmossdk_math.LegacyNewDecFromInt(v.RemainingWant.Amount).Quo(cosmossdk_math.LegacyNewDecFromInt(v.RemainingHave.Amount))
		if req.MinPrice != "" && price.LT(minDec) {
			return nil, nil
		}
		if req.MaxPrice != "" && price.GT(maxDec) {
			return nil, nil
		}
		vv := v
		return &vv, nil
	})
	if perr != nil {
		return nil, cosmossdkerrors.Wrap(perr, "OffersByPairPriceRange paginate failed")
	}
	return &whaleswapv1.QueryOffersResponse{Offers: results, Pagination: pageRes}, nil
}

func (k Keeper) OffersBest(ctx context.Context, req *whaleswapv1.QueryOffersBestRequest) (*whaleswapv1.QueryOffersResponse, error) {
	if req == nil {
		req = &whaleswapv1.QueryOffersBestRequest{}
	}
	if req.HaveDenom == "" || req.WantDenom == "" {
		return nil, cosmossdkerrors.Wrap(sdkerrors.ErrInvalidRequest, "have_denom and want_denom required")
	}
	limit := int(req.Limit)
	if limit <= 0 {
		limit = 10
	}
	low, high := req.HaveDenom, req.WantDenom
	if low > high {
		low, high = high, low
	}
	pairKey := low + "|" + high
	collected := make([]*whaleswapv1.OfferData, 0, limit)
	_, _, err := query.CollectionPaginate(ctx, k.OffersByPairPrice, nil, func(key collections.Triple[string, string, uint64], id uint64) (*whaleswapv1.OfferData, error) {
		k1, _, _ := key.K1(), key.K2(), key.K3()
		if k1 != pairKey {
			return nil, nil
		}
		v, err := k.OffersMap.Get(ctx, id)
		if err != nil {
			return nil, err
		}
		if v.RemainingHave.Denom != req.HaveDenom || v.RemainingWant.Denom != req.WantDenom {
			return nil, nil
		}
		if len(collected) < limit {
			vv := v
			collected = append(collected, &vv)
		}
		return nil, nil
	})
	if err != nil {
		return nil, cosmossdkerrors.Wrap(err, "OffersBest iteration failed")
	}
	return &whaleswapv1.QueryOffersResponse{Offers: collected}, nil
}
