package keeper

import (
	"context"

	cosmossdkerrors "cosmossdk.io/errors"
	"cosmossdk.io/math"
	whaleswapv1 "dysonprotocol.com/x/whaleswap/types"
	sdk "github.com/cosmos/cosmos-sdk/types"
)

func (k Keeper) UpdatePoolConfig(ctx context.Context, msg *whaleswapv1.MsgUpdatePoolConfig) (*whaleswapv1.MsgUpdatePoolConfigResponse, error) {
	// Load pool
	pool, err := k.PoolsMap.Get(ctx, msg.PoolId)
	if err != nil {
		return nil, cosmossdkerrors.Wrapf(err, "pool not found: %d", msg.PoolId)
	}
	// Check majority owner
	signer, err := k.addr(ctx, msg.Signer)
	if err != nil {
		return nil, cosmossdkerrors.Wrapf(err, "failed to get signer address: %s", msg.Signer)
	}
	if err := k.ensureMajorityOwner(ctx, pool, signer); err != nil {
		return nil, cosmossdkerrors.Wrapf(err, "signer is not majority owner of shares:%s", signer.String())
	}

	// Apply optional updates
	if msg.FeePct != "" {
		fee, ferr := math.LegacyNewDecFromStr(msg.FeePct)
		if ferr != nil || fee.IsNegative() || fee.GTE(math.LegacyNewDec(1)) {
			return nil, cosmossdkerrors.Wrapf(err, "invalid fee_pct: %s", msg.FeePct)
		}
		pool.FeePct = msg.FeePct
	}
	// Normalize bands
	if len(msg.MinPrice) > 0 || len(msg.MaxPrice) > 0 {
		minBand, merr := k.normalizeBand(msg.MinPrice, pool.CoinA.Denom, pool.CoinB.Denom)
		if merr != nil {
			return nil, cosmossdkerrors.Wrapf(err, "invalid min_price: %s", msg.MinPrice)
		}
		maxBand, xerr := k.normalizeBand(msg.MaxPrice, pool.CoinA.Denom, pool.CoinB.Denom)
		if xerr != nil {
			return nil, cosmossdkerrors.Wrapf(err, "invalid max_price: %s", msg.MaxPrice)
		}
		if len(minBand) == 0 || len(maxBand) == 0 {
			return nil, cosmossdkerrors.Wrapf(err, "must set both min_price and max_price or neither")
		}
		minRatio, err := k.bandRatio(minBand, pool.CoinA.Denom, pool.CoinB.Denom)
		if err != nil {
			return nil, cosmossdkerrors.Wrapf(err, "failed to compute min_price ratio")
		}
		maxRatio, err := k.bandRatio(maxBand, pool.CoinA.Denom, pool.CoinB.Denom)
		if err != nil {
			return nil, cosmossdkerrors.Wrapf(err, "failed to compute max_price ratio")
		}
		if maxRatio.LT(minRatio) {
			return nil, cosmossdkerrors.Wrapf(err, "max_price must be >= min_price")
		}
		// Current price must be within the new band
		p, err := k.currentPrice(pool)
		if err != nil {
			return nil, cosmossdkerrors.Wrapf(err, "failed to compute current price")
		}
		if p.LT(minRatio) || p.GT(maxRatio) {
			return nil, cosmossdkerrors.Wrapf(err, "current price outside new band")
		}
		pool.MinPrice = minBand
		pool.MaxPrice = maxBand
	}

	// Save and emit
	sdkCtx := sdk.UnwrapSDKContext(ctx)
	t := sdkCtx.BlockTime()
	pool.Updated = &t
	if err := k.PoolsMap.Set(ctx, pool.PoolId, pool); err != nil {
		return nil, cosmossdkerrors.Wrapf(err, "failed to set pool: %d", pool.PoolId)
	}
	_ = sdkCtx.EventManager().EmitTypedEvent(&whaleswapv1.EventPoolUpdate{PoolId: pool.PoolId})
	if err := k.AssertAMMInvariants(ctx); err != nil {
		return nil, cosmossdkerrors.Wrapf(err,
			"AMM invariant after UpdatePoolConfig: pool_id=%d fee_pct=%s min=%s max=%s",
			pool.PoolId,
			pool.FeePct,
			pool.MinPrice.String(),
			pool.MaxPrice.String(),
		)
	}
	return &whaleswapv1.MsgUpdatePoolConfigResponse{}, nil
}
