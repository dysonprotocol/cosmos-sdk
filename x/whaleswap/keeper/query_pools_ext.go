package keeper

import (
	"context"

	cosmossdkerrors "cosmossdk.io/errors"
	cosmossdk_math "cosmossdk.io/math"
	whaleswapv1 "dysonprotocol.com/x/whaleswap/types"
	sdkerrors "github.com/cosmos/cosmos-sdk/types/errors"
	"github.com/cosmos/cosmos-sdk/types/query"
)

func (k Keeper) PoolsByPair(ctx context.Context, req *whaleswapv1.QueryPoolsByPairRequest) (*whaleswapv1.QueryPoolsResponse, error) {
	if req == nil {
		req = &whaleswapv1.QueryPoolsByPairRequest{}
	}
	if req.BaseDenom == "" || req.QuoteDenom == "" {
		return nil, cosmossdkerrors.Wrap(sdkerrors.ErrInvalidRequest, "base_denom and quote_denom required")
	}
	base, quote := req.BaseDenom, req.QuoteDenom
	results, pageRes, err := query.CollectionPaginate(ctx, k.PoolsMap, req.Pagination, func(key uint64, value whaleswapv1.Pool) (*whaleswapv1.Pool, error) {
		if len(value.Coins) == 2 && ((value.Coins[0].Denom == base && value.Coins[1].Denom == quote) || (value.Coins[0].Denom == quote && value.Coins[1].Denom == base)) {
			v := value
			return &v, nil
		}
		return nil, nil
	})
	if err != nil {
		return nil, cosmossdkerrors.Wrap(err, "PoolsByPair paginate failed")
	}
	return &whaleswapv1.QueryPoolsResponse{Pools: results, Pagination: pageRes}, nil
}

func (k Keeper) PoolsByDenom(ctx context.Context, req *whaleswapv1.QueryPoolsByDenomRequest) (*whaleswapv1.QueryPoolsResponse, error) {
	if req == nil {
		req = &whaleswapv1.QueryPoolsByDenomRequest{}
	}
	if req.Denom == "" {
		return nil, cosmossdkerrors.Wrap(sdkerrors.ErrInvalidRequest, "denom required")
	}
	results, pageRes, err := query.CollectionPaginate(ctx, k.PoolsMap, req.Pagination, func(key uint64, value whaleswapv1.Pool) (*whaleswapv1.Pool, error) {
		if len(value.Coins) != 2 || (value.Coins[0].Denom != req.Denom && value.Coins[1].Denom != req.Denom) {
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
	if req.BaseDenom == "" || req.QuoteDenom == "" {
		return nil, cosmossdkerrors.Wrap(sdkerrors.ErrInvalidRequest, "base_denom and quote_denom required")
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
	results, pageRes, perr := query.CollectionPaginate(ctx, k.PoolsMap, req.Pagination, func(key uint64, value whaleswapv1.Pool) (*whaleswapv1.Pool, error) {
		// match pair using denom presence regardless of order
		if len(value.Coins) != 2 {
			return nil, nil
		}
		rBase := value.Coins.AmountOf(req.BaseDenom)
		rQuote := value.Coins.AmountOf(req.QuoteDenom)
		if rBase.IsZero() || rQuote.IsZero() {
			return nil, nil
		}
		// price = quote/base; compare via cross-multiplication with Dec*Int
		if req.MinPrice != "" {
			// require rQuote >= ceil(minDec * rBase)
			minThresh := minDec.MulInt(rBase).Ceil().TruncateInt()
			if rQuote.LT(minThresh) {
				return nil, nil
			}
		}
		if req.MaxPrice != "" {
			// require rQuote <= floor(maxDec * rBase)
			maxThresh := maxDec.MulInt(rBase).TruncateInt()
			if rQuote.GT(maxThresh) {
				return nil, nil
			}
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
