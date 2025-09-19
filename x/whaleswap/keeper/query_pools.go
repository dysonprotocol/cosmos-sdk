package keeper

import (
	"context"

	whaleswapv1 "dysonprotocol.com/x/whaleswap/types"
	"github.com/cosmos/cosmos-sdk/types/query"
)

func (k Keeper) Params(ctx context.Context, _ *whaleswapv1.QueryParamsRequest) (*whaleswapv1.QueryParamsResponse, error) {
	p := k.GetParams(ctx)
	return &whaleswapv1.QueryParamsResponse{Params: p}, nil
}

func (k Keeper) Pool(ctx context.Context, req *whaleswapv1.QueryPoolRequest) (*whaleswapv1.QueryPoolResponse, error) {
	pool, err := k.PoolsMap.Get(ctx, req.PoolId)
	if err != nil {
		return nil, err
	}
	return &whaleswapv1.QueryPoolResponse{Pool: &pool}, nil
}

func (k Keeper) Pools(ctx context.Context, req *whaleswapv1.QueryPoolsRequest) (*whaleswapv1.QueryPoolsResponse, error) {
	if req == nil {
		req = &whaleswapv1.QueryPoolsRequest{}
	}
	results, pageRes, err := query.CollectionPaginate(
		ctx,
		k.PoolsMap,
		req.Pagination,
		func(key uint64, value whaleswapv1.Pool) (*whaleswapv1.Pool, error) { v := value; return &v, nil },
	)
	if err != nil {
		return nil, err
	}
	if results == nil {
		results = make([]*whaleswapv1.Pool, 0)
	}
	return &whaleswapv1.QueryPoolsResponse{Pools: results, Pagination: pageRes}, nil
}
