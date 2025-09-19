package keeper

import (
	"cosmossdk.io/collections"
	cosmossdk_math "cosmossdk.io/math"
	"dysonprotocol.com/x/whaleswap/types"
	sdk "github.com/cosmos/cosmos-sdk/types"
)

// InitGenesis initializes state from genesis
func (k Keeper) InitGenesis(ctx sdk.Context, gs *types.GenesisState) {
	// params
	_ = k.SetParams(ctx, gs.Params)

	// Pools
	var maxPoolID uint64
	for _, p := range gs.Pools {
		if p.PoolId > maxPoolID {
			maxPoolID = p.PoolId
		}
		if err := k.PoolsMap.Set(ctx, p.PoolId, *p); err != nil {
			panic(err)
		}
	}
	if maxPoolID > 0 {
		if err := k.poolSeq.Set(ctx, maxPoolID); err != nil {
			panic(err)
		}
	}

	// Offers
	var maxOfferID uint64
	for _, o := range gs.Offers {
		if o.OfferId > maxOfferID {
			maxOfferID = o.OfferId
		}
		if err := k.OffersMap.Set(ctx, o.OfferId, *o); err != nil {
			panic(err)
		}
		// rebuild indexes
		// have, id
		_ = k.OffersByHave.Set(ctx, collections.Join(o.RemainingHave.Denom, o.OfferId), o.OfferId)
		// want, id
		_ = k.OffersByWant.Set(ctx, collections.Join(o.RemainingWant.Denom, o.OfferId), o.OfferId)
		// owner+status
		_ = k.OffersByOwnerStatus.Set(ctx, collections.Join3(o.Maker, o.Status, o.OfferId), o.OfferId)
		// price index only for open offers
		if o.Status == "open" {
			haveDenom := o.RemainingHave.Denom
			wantDenom := o.RemainingWant.Denom
			low, high := haveDenom, wantDenom
			if low > high {
				low, high = high, low
			}
			pairKey := low + "|" + high
			priceHavePerWant := cosmossdk_math.LegacyNewDecFromInt(o.RemainingHave.Amount).Quo(cosmossdk_math.LegacyNewDecFromInt(o.RemainingWant.Amount))
			priceWantPerHave := cosmossdk_math.LegacyNewDecFromInt(o.RemainingWant.Amount).Quo(cosmossdk_math.LegacyNewDecFromInt(o.RemainingHave.Amount))
			priceDec := priceWantPerHave
			if low == wantDenom && high == haveDenom {
				priceDec = priceHavePerWant
			}
			_ = k.OffersByPairPrice.Set(ctx, collections.Join3(pairKey, priceDec.String(), o.OfferId), o.OfferId)
		}
	}
	if maxOfferID > 0 {
		if err := k.offerSeq.Set(ctx, maxOfferID); err != nil {
			panic(err)
		}
	}

	// Trades
	var maxTradeID uint64
	for _, t := range gs.Trades {
		if t.TradeId > maxTradeID {
			maxTradeID = t.TradeId
		}
		if err := k.TradesMap.Set(ctx, t.TradeId, *t); err != nil {
			panic(err)
		}
	}
	if maxTradeID > 0 {
		if err := k.tradeSeq.Set(ctx, maxTradeID); err != nil {
			panic(err)
		}
	}

	// Auctions
	var maxAuctionID uint64
	for _, a := range gs.Auctions {
		if a.AuctionId > maxAuctionID {
			maxAuctionID = a.AuctionId
		}
		if err := k.AuctionsMap.Set(ctx, a.AuctionId, *a); err != nil {
			panic(err)
		}
		// Reverse indexes
		_ = k.AuctionsBySellBid.Set(ctx, collections.Join3(a.Sell.Denom, a.BidDenom, a.AuctionId), a.AuctionId)
		_ = k.AuctionsByBidSell.Set(ctx, collections.Join3(a.BidDenom, a.Sell.Denom, a.AuctionId), a.AuctionId)
	}
	if maxAuctionID > 0 {
		if err := k.auctionSeq.Set(ctx, maxAuctionID); err != nil {
			panic(err)
		}
	}
}

// ExportGenesis exports current module state
func (k Keeper) ExportGenesis(ctx sdk.Context) *types.GenesisState {
	p := k.GetParams(ctx)
	// Collect pools
	var pools []*types.Pool
	_ = k.PoolsMap.Walk(ctx, nil, func(key uint64, value types.Pool) (bool, error) {
		v := value
		pools = append(pools, &v)
		return false, nil
	})
	// Collect offers
	var offers []*types.OfferData
	_ = k.OffersMap.Walk(ctx, nil, func(key uint64, value types.OfferData) (bool, error) {
		v := value
		offers = append(offers, &v)
		return false, nil
	})
	// Collect trades
	var trades []*types.Trade
	_ = k.TradesMap.Walk(ctx, nil, func(key uint64, value types.Trade) (bool, error) {
		v := value
		trades = append(trades, &v)
		return false, nil
	})
	// Collect auctions
	var auctions []*types.AuctionRecord
	_ = k.AuctionsMap.Walk(ctx, nil, func(key uint64, value types.AuctionRecord) (bool, error) {
		v := value
		auctions = append(auctions, &v)
		return false, nil
	})

	return &types.GenesisState{Params: p, Pools: pools, Offers: offers, Trades: trades, Auctions: auctions}
}
