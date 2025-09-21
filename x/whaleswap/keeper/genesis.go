package keeper

import (
	"fmt"

	"cosmossdk.io/collections"
	cosmossdk_math "cosmossdk.io/math"
	whaleswap "dysonprotocol.com/x/whaleswap"
	"dysonprotocol.com/x/whaleswap/types"
	sdk "github.com/cosmos/cosmos-sdk/types"
)

// InitGenesis initializes state from genesis
func (k Keeper) InitGenesis(ctx sdk.Context, gs *types.GenesisState) {
	// params
	if err := k.SetParams(ctx, gs.Params); err != nil {
		panic(err)
	}

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
		if err := k.poolSeq.Set(ctx, maxPoolID+1); err != nil {
			panic(err)
		}
	} else {
		if err := k.poolSeq.Set(ctx, 1); err != nil {
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
		if err := k.OffersByHave.Set(ctx, collections.Join(o.RemainingHave.Denom, o.OfferId), o.OfferId); err != nil {
			panic(err)
		}
		// want, id
		if err := k.OffersByWant.Set(ctx, collections.Join(o.RemainingWant.Denom, o.OfferId), o.OfferId); err != nil {
			panic(err)
		}
		// owner+status
		if err := k.OffersByOwnerStatus.Set(ctx, collections.Join3(o.Maker, o.Status, o.OfferId), o.OfferId); err != nil {
			panic(err)
		}
		// price index only for open offers
		if o.Status == types.OfferStatusOpen {
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
			if err := k.OffersByPairPrice.Set(ctx, collections.Join3(pairKey, priceDec.String(), o.OfferId), o.OfferId); err != nil {
				panic(err)
			}
		}
	}
	if maxOfferID > 0 {
		if err := k.offerSeq.Set(ctx, maxOfferID+1); err != nil {
			panic(err)
		}
	} else {
		if err := k.offerSeq.Set(ctx, 1); err != nil {
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
		// rebuild reverse indexes
		if t.PoolId > 0 {
			if err := k.TradesByPoolIndex.Set(ctx, collections.Join(t.PoolId, t.TradeId), t.TradeId); err != nil {
				panic(err)
			}
		}
		if t.Taker != "" {
			if err := k.TradesByTakerIndex.Set(ctx, collections.Join(t.Taker, t.TradeId), t.TradeId); err != nil {
				panic(err)
			}
		}
	}
	if maxTradeID > 0 {
		if err := k.tradeSeq.Set(ctx, maxTradeID+1); err != nil {
			panic(err)
		}
	} else {
		if err := k.tradeSeq.Set(ctx, 1); err != nil {
			panic(err)
		}
	}

	// Auctions
	var maxAuctionID uint64
	// Optional sanity: aggregate required escrow per denom
	requiredEscrow := map[string]sdk.Coin{}
	for _, a := range gs.Auctions {
		if a.AuctionId > maxAuctionID {
			maxAuctionID = a.AuctionId
		}
		if err := k.AuctionsMap.Set(ctx, a.AuctionId, *a); err != nil {
			panic(err)
		}
		// Reverse indexes
		if err := k.AuctionsBySellBid.Set(ctx, collections.Join3(a.Sell.Denom, a.BidDenom, a.AuctionId), a.AuctionId); err != nil {
			panic(err)
		}
		if err := k.AuctionsByBidSell.Set(ctx, collections.Join3(a.BidDenom, a.Sell.Denom, a.AuctionId), a.AuctionId); err != nil {
			panic(err)
		}
		// Tally escrow requirement
		if ex, ok := requiredEscrow[a.Sell.Denom]; ok {
			sum := ex
			sum.Amount = sum.Amount.Add(a.Sell.Amount)
			requiredEscrow[a.Sell.Denom] = sum
		} else {
			requiredEscrow[a.Sell.Denom] = a.Sell
		}
	}
	if maxAuctionID > 0 {
		if err := k.auctionSeq.Set(ctx, maxAuctionID+1); err != nil {
			panic(err)
		}
	} else {
		if err := k.auctionSeq.Set(ctx, 1); err != nil {
			panic(err)
		}
	}
	// Validate module escrow balances cover required sums (best-effort; panic on deficit)
	moduleAddr := k.accKeeper.GetModuleAddress(whaleswap.ModuleName)
	for denom, need := range requiredEscrow {
		bal := k.bank.GetBalance(ctx, moduleAddr, denom)
		if !bal.IsGTE(need) {
			panic(fmt.Sprintf("genesis escrow deficit for denom %s: have=%s need=%s", denom, bal.String(), need.String()))
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
