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
	// Bands: compare prices using cross-multiplication on ints; avoid Decs
	if len(msg.MinPrice) > 0 || len(msg.MaxPrice) > 0 {
		if len(pool.Coins) != 2 {
			return nil, cosmossdkerrors.Wrapf(err, "invalid pool coins")
		}
		baseDenom, quoteDenom := pool.Coins[0].Denom, pool.Coins[1].Denom
		// Require both bands set
		if len(msg.MinPrice) == 0 || len(msg.MaxPrice) == 0 {
			return nil, cosmossdkerrors.Wrapf(err, "must set both min_price and max_price or neither")
		}
		// Sort for canonical order then extract amounts for pool pair
		msg.MinPrice.Sort()
		msg.MaxPrice.Sort()
		minBase := msg.MinPrice.AmountOf(baseDenom)
		minQuote := msg.MinPrice.AmountOf(quoteDenom)
		maxBase := msg.MaxPrice.AmountOf(baseDenom)
		maxQuote := msg.MaxPrice.AmountOf(quoteDenom)
		if !minBase.IsPositive() || !minQuote.IsPositive() || !maxBase.IsPositive() || !maxQuote.IsPositive() {
			return nil, cosmossdkerrors.Wrapf(err, "band amounts must be > 0 for both denoms")
		}
		// Enforce max >= min: maxQuote/maxBase >= minQuote/minBase => maxQuote*minBase >= minQuote*maxBase
		if maxQuote.Mul(minBase).LT(minQuote.Mul(maxBase)) {
			return nil, cosmossdkerrors.Wrapf(err, "max_price must be >= min_price")
		}
		// Current price within [min, max]
		rBase := pool.Coins[0].Amount
		rQuote := pool.Coins[1].Amount
		// P >= min => rQuote*minBase >= rBase*minQuote
		if rQuote.Mul(minBase).LT(rBase.Mul(minQuote)) {
			return nil, cosmossdkerrors.Wrapf(err, "current price below min band")
		}
		// P <= max => rQuote*maxBase <= rBase*maxQuote
		if rQuote.Mul(maxBase).GT(rBase.Mul(maxQuote)) {
			return nil, cosmossdkerrors.Wrapf(err, "current price above max band")
		}
		// Store only the two relevant coins in canonical pool order
		pool.MinPrice = sdk.NewCoins(sdk.NewCoin(baseDenom, minBase), sdk.NewCoin(quoteDenom, minQuote))
		pool.MaxPrice = sdk.NewCoins(sdk.NewCoin(baseDenom, maxBase), sdk.NewCoin(quoteDenom, maxQuote))
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
