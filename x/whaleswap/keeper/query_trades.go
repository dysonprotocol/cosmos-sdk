package keeper

import (
	"context"

	whaleswapv1 "dysonprotocol.com/x/whaleswap/types"
	"github.com/cosmos/cosmos-sdk/types/query"
)

func (k Keeper) TradesByOffer(ctx context.Context, req *whaleswapv1.QueryTradesByOfferRequest) (*whaleswapv1.QueryTradesByOfferResponse, error) {
	if req == nil {
		req = &whaleswapv1.QueryTradesByOfferRequest{}
	}
	offerID := req.OfferId
	var trades []*whaleswapv1.Trade
	results, pageRes, err := query.CollectionPaginate(
		ctx,
		k.TradesMap,
		req.Pagination,
		func(key uint64, value whaleswapv1.Trade) (*whaleswapv1.Trade, error) {
			if offerID != 0 && value.OfferId != offerID {
				return nil, nil
			}
			v := value
			return &v, nil
		},
	)
	if err != nil {
		return nil, err
	}
	trades = results
	return &whaleswapv1.QueryTradesByOfferResponse{Trades: trades, Pagination: pageRes}, nil
}

func (k Keeper) TradesByTaker(ctx context.Context, req *whaleswapv1.QueryTradesByTakerRequest) (*whaleswapv1.QueryTradesByTakerResponse, error) {
	if req == nil {
		req = &whaleswapv1.QueryTradesByTakerRequest{}
	}
	taker := req.Taker
	var trades []*whaleswapv1.Trade
	results, pageRes, err := query.CollectionPaginate(
		ctx,
		k.TradesMap,
		req.Pagination,
		func(key uint64, value whaleswapv1.Trade) (*whaleswapv1.Trade, error) {
			if taker != "" && value.Taker != taker {
				return nil, nil
			}
			v := value
			return &v, nil
		},
	)
	if err != nil {
		return nil, err
	}
	trades = results
	return &whaleswapv1.QueryTradesByTakerResponse{Trades: trades, Pagination: pageRes}, nil
}
