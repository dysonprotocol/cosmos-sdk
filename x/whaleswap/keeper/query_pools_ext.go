package keeper

import (
	"context"

	cosmossdkerrors "cosmossdk.io/errors"
	cosmossdk_math "cosmossdk.io/math"
	whaleswapv1 "dysonprotocol.com/x/whaleswap/types"
	sdkerrors "github.com/cosmos/cosmos-sdk/types/errors"
	"github.com/cosmos/cosmos-sdk/types/query"
)

func (k Keeper) PoolByPair(ctx context.Context, req *whaleswapv1.QueryPoolByPairRequest) (*whaleswapv1.QueryPoolResponse, error) {
	if req == nil {
		req = &whaleswapv1.QueryPoolByPairRequest{}
	}
	if req.HaveDenom == "" || req.WantDenom == "" {
		return nil, cosmossdkerrors.Wrap(sdkerrors.ErrInvalidRequest, "have_denom and want_denom required")
	}
	have, want := req.HaveDenom, req.WantDenom
	var matched *whaleswapv1.Pool
	_, _, err := query.CollectionPaginate(ctx, k.PoolsMap, nil, func(key uint64, value whaleswapv1.Pool) (*whaleswapv1.Pool, error) {
		// match regardless of order
		if (value.CoinA.Denom == have && value.CoinB.Denom == want) || (value.CoinA.Denom == want && value.CoinB.Denom == have) {
			v := value
			matched = &v
			return &v, nil
		}
		return nil, nil
	})
	if err != nil {
		return nil, cosmossdkerrors.Wrap(err, "PoolByPair paginate failed")
	}
	if matched == nil {
		return nil, cosmossdkerrors.Wrapf(sdkerrors.ErrNotFound, "pool not found for pair %s/%s", have, want)
	}
	return &whaleswapv1.QueryPoolResponse{Pool: matched}, nil
}

func (k Keeper) PoolsByDenom(ctx context.Context, req *whaleswapv1.QueryPoolsByDenomRequest) (*whaleswapv1.QueryPoolsResponse, error) {
	if req == nil {
		req = &whaleswapv1.QueryPoolsByDenomRequest{}
	}
	if req.Denom == "" {
		return nil, cosmossdkerrors.Wrap(sdkerrors.ErrInvalidRequest, "denom required")
	}
	results, pageRes, err := query.CollectionPaginate(ctx, k.PoolsMap, req.Pagination, func(key uint64, value whaleswapv1.Pool) (*whaleswapv1.Pool, error) {
		if value.CoinA.Denom != req.Denom && value.CoinB.Denom != req.Denom {
			return nil, nil
		}
		v := value
		return &v, nil
	})
	if err != nil {
		return nil, cosmossdkerrors.Wrap(err, "PoolsByDenom paginate failed")
	}
	return &whaleswapv1.QueryPoolsResponse{Pools: results, Pagination: pageRes}, nil
}

func (k Keeper) PoolBySharesDenom(ctx context.Context, req *whaleswapv1.QueryPoolBySharesDenomRequest) (*whaleswapv1.QueryPoolResponse, error) {
	if req == nil {
		req = &whaleswapv1.QueryPoolBySharesDenomRequest{}
	}
	if req.SharesDenom == "" {
		return nil, cosmossdkerrors.Wrap(sdkerrors.ErrInvalidRequest, "shares_denom required")
	}
	var matched *whaleswapv1.Pool
	_, _, err := query.CollectionPaginate(ctx, k.PoolsMap, nil, func(key uint64, value whaleswapv1.Pool) (*whaleswapv1.Pool, error) {
		if value.SharesDenom == req.SharesDenom {
			v := value
			matched = &v
			return &v, nil
		}
		return nil, nil
	})
	if err != nil {
		return nil, cosmossdkerrors.Wrap(err, "PoolBySharesDenom paginate failed")
	}
	if matched == nil {
		return nil, cosmossdkerrors.Wrapf(sdkerrors.ErrNotFound, "pool not found for shares denom %s", req.SharesDenom)
	}
	return &whaleswapv1.QueryPoolResponse{Pool: matched}, nil
}

func (k Keeper) PoolsByPairPriceRange(ctx context.Context, req *whaleswapv1.QueryPoolsByPairPriceRangeRequest) (*whaleswapv1.QueryPoolsResponse, error) {
	if req == nil {
		req = &whaleswapv1.QueryPoolsByPairPriceRangeRequest{}
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
	low, high := req.HaveDenom, req.WantDenom
	if low > high {
		low, high = high, low
	}
	results, pageRes, perr := query.CollectionPaginate(ctx, k.PoolsMap, req.Pagination, func(key uint64, value whaleswapv1.Pool) (*whaleswapv1.Pool, error) {
		// match pair
		if !((value.CoinA.Denom == low && value.CoinB.Denom == high) || (value.CoinA.Denom == high && value.CoinB.Denom == low)) {
			return nil, nil
		}
		// compute price P = coin_b / coin_a (keeper.currentPrice uses canonical order)
		p, err := k.currentPrice(value)
		if err != nil {
			return nil, nil
		}
		if req.MinPrice != "" && p.LT(minDec) {
			return nil, nil
		}
		if req.MaxPrice != "" && p.GT(maxDec) {
			return nil, nil
		}
		v := value
		return &v, nil
	})
	if perr != nil {
		return nil, cosmossdkerrors.Wrap(perr, "PoolsByPairPriceRange paginate failed")
	}
	return &whaleswapv1.QueryPoolsResponse{Pools: results, Pagination: pageRes}, nil
}

func (k Keeper) PoolsByOwner(ctx context.Context, req *whaleswapv1.QueryPoolsByOwnerRequest) (*whaleswapv1.QueryPoolsResponse, error) {
	if req == nil {
		req = &whaleswapv1.QueryPoolsByOwnerRequest{}
	}
	if req.Owner == "" {
		return nil, cosmossdkerrors.Wrap(sdkerrors.ErrInvalidRequest, "owner required")
	}
	addrBz, err := k.accKeeper.AddressCodec().StringToBytes(req.Owner)
	if err != nil {
		return nil, cosmossdkerrors.Wrapf(sdkerrors.ErrInvalidAddress, "invalid owner: %s", req.Owner)
	}
	results, pageRes, perr := query.CollectionPaginate(ctx, k.PoolsMap, req.Pagination, func(key uint64, value whaleswapv1.Pool) (*whaleswapv1.Pool, error) {
		bal := k.bank.GetBalance(ctx, addrBz, value.SharesDenom).Amount
		if !bal.IsPositive() {
			return nil, nil
		}
		v := value
		return &v, nil
	})
	if perr != nil {
		return nil, cosmossdkerrors.Wrap(perr, "PoolsByOwner paginate failed")
	}
	return &whaleswapv1.QueryPoolsResponse{Pools: results, Pagination: pageRes}, nil
}
