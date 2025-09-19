package keeper

import (
	"context"
	"fmt"

	"cosmossdk.io/math"
	whaleswapv1 "dysonprotocol.com/x/whaleswap/types"
	sdk "github.com/cosmos/cosmos-sdk/types"
)

func (k Keeper) UpdatePoolConfig(ctx context.Context, msg *whaleswapv1.MsgUpdatePoolConfig) (*whaleswapv1.MsgUpdatePoolConfigResponse, error) {
	// Load pool
	pool, err := k.PoolsMap.Get(ctx, msg.PoolId)
	if err != nil {
		return nil, err
	}
	// Check majority owner
	signer, err := k.addr(ctx, msg.Signer)
	if err != nil {
		return nil, err
	}
	if err := k.ensureMajorityOwner(ctx, pool, signer); err != nil {
		return nil, err
	}

	// Apply optional updates
	if msg.FeePct != "" {
		fee, ferr := math.LegacyNewDecFromStr(msg.FeePct)
		if ferr != nil || fee.IsNegative() || fee.GTE(math.LegacyNewDec(1)) {
			return nil, fmt.Errorf("invalid fee_pct")
		}
		pool.FeePct = msg.FeePct
	}
	// Normalize bands
	if len(msg.MinPrice) > 0 || len(msg.MaxPrice) > 0 {
		minBand, merr := k.normalizeBand(msg.MinPrice, pool.CoinA.Denom, pool.CoinB.Denom)
		if merr != nil {
			return nil, fmt.Errorf("invalid min_price: %w", merr)
		}
		maxBand, xerr := k.normalizeBand(msg.MaxPrice, pool.CoinA.Denom, pool.CoinB.Denom)
		if xerr != nil {
			return nil, fmt.Errorf("invalid max_price: %w", xerr)
		}
		if len(minBand) == 0 || len(maxBand) == 0 {
			return nil, fmt.Errorf("must set both min_price and max_price or neither")
		}
		minRatio, err := k.bandRatio(minBand, pool.CoinA.Denom, pool.CoinB.Denom)
		if err != nil {
			return nil, err
		}
		maxRatio, err := k.bandRatio(maxBand, pool.CoinA.Denom, pool.CoinB.Denom)
		if err != nil {
			return nil, err
		}
		if maxRatio.LT(minRatio) {
			return nil, fmt.Errorf("max_price must be >= min_price")
		}
		// Current price must be within the new band
		p, err := k.currentPrice(pool)
		if err != nil {
			return nil, err
		}
		if p.LT(minRatio) || p.GT(maxRatio) {
			return nil, fmt.Errorf("current price outside new band")
		}
		pool.MinPrice = minBand
		pool.MaxPrice = maxBand
	}

	// Save and emit
	sdkCtx := sdk.UnwrapSDKContext(ctx)
	t := sdkCtx.BlockTime()
	pool.Updated = &t
	if err := k.PoolsMap.Set(ctx, pool.PoolId, pool); err != nil {
		return nil, err
	}
	_ = sdkCtx.EventManager().EmitTypedEvent(&whaleswapv1.EventPoolUpdate{PoolId: pool.PoolId})
	return &whaleswapv1.MsgUpdatePoolConfigResponse{}, nil
}
