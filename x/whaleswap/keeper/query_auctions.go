package keeper

import (
	"context"

	"cosmossdk.io/collections"
	whaleswapv1 "dysonprotocol.com/x/whaleswap/types"
	"github.com/cosmos/cosmos-sdk/types/query"
)

func (k Keeper) Auction(ctx context.Context, req *whaleswapv1.QueryAuctionRequest) (*whaleswapv1.QueryAuctionResponse, error) {
	rec, err := k.AuctionsMap.Get(ctx, req.AuctionId)
	if err != nil {
		return nil, err
	}
	return &whaleswapv1.QueryAuctionResponse{Auction: &rec}, nil
}

func (k Keeper) Auctions(ctx context.Context, req *whaleswapv1.QueryAuctionsRequest) (*whaleswapv1.QueryAuctionsResponse, error) {
	if req == nil {
		req = &whaleswapv1.QueryAuctionsRequest{}
	}
	sell := req.SellDenom
	bid := req.BidDenom

	// Choose index based on provided filters
	switch {
	case sell != "" && bid != "":
		// Use (sell,bid,auction_id) index and paginate
		results, pageRes, err := query.CollectionPaginate(
			ctx,
			k.AuctionsBySellBid,
			req.Pagination,
			func(key collections.Triple[string, string, uint64], value uint64) (*whaleswapv1.AuctionRecord, error) {
				// filter by superprefix via key; CollectionPaginate already ranges over the map so we filter strictly
				if k1, k2, _ := key.K1(), key.K2(), key.K3(); k1 == sell && k2 == bid {
					rec, err := k.AuctionsMap.Get(ctx, value)
					if err != nil {
						return nil, err
					}
					return &rec, nil
				}
				return nil, nil
			},
		)
		if err != nil {
			return nil, err
		}
		return &whaleswapv1.QueryAuctionsResponse{Auctions: results, Pagination: pageRes}, nil

	case sell != "":
		// Use (sell,*,auction_id) scan
		results, pageRes, err := query.CollectionPaginate(
			ctx,
			k.AuctionsBySellBid,
			req.Pagination,
			func(key collections.Triple[string, string, uint64], value uint64) (*whaleswapv1.AuctionRecord, error) {
				if k1, _, _ := key.K1(), key.K2(), key.K3(); k1 == sell {
					rec, err := k.AuctionsMap.Get(ctx, value)
					if err != nil {
						return nil, err
					}
					if bid != "" && rec.BidDenom != bid {
						return nil, nil
					}
					return &rec, nil
				}
				return nil, nil
			},
		)
		if err != nil {
			return nil, err
		}
		return &whaleswapv1.QueryAuctionsResponse{Auctions: results, Pagination: pageRes}, nil

	case bid != "":
		// Use (bid,*,auction_id) index
		results, pageRes, err := query.CollectionPaginate(
			ctx,
			k.AuctionsByBidSell,
			req.Pagination,
			func(key collections.Triple[string, string, uint64], value uint64) (*whaleswapv1.AuctionRecord, error) {
				if k1, _, _ := key.K1(), key.K2(), key.K3(); k1 == bid {
					rec, err := k.AuctionsMap.Get(ctx, value)
					if err != nil {
						return nil, err
					}
					if sell != "" && rec.Sell.Denom != sell {
						return nil, nil
					}
					return &rec, nil
				}
				return nil, nil
			},
		)
		if err != nil {
			return nil, err
		}
		return &whaleswapv1.QueryAuctionsResponse{Auctions: results, Pagination: pageRes}, nil
	}

	// No filters: paginate primary map
	results, pageRes, err := query.CollectionPaginate(
		ctx,
		k.AuctionsMap,
		req.Pagination,
		func(key uint64, value whaleswapv1.AuctionRecord) (*whaleswapv1.AuctionRecord, error) {
			v := value
			return &v, nil
		},
	)
	if err != nil {
		return nil, err
	}
	return &whaleswapv1.QueryAuctionsResponse{Auctions: results, Pagination: pageRes}, nil
}
