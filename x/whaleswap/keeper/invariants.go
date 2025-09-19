package keeper

import (
	"context"

	cosmossdkerrors "cosmossdk.io/errors"
	"cosmossdk.io/math"
	whaleswap "dysonprotocol.com/x/whaleswap"
	whaleswapv1 "dysonprotocol.com/x/whaleswap/types"
	sdkerrors "github.com/cosmos/cosmos-sdk/types/errors"
)

// AssertInvariants checks orderbook escrow and pfand invariants.
// - Sum(escrowed have by open normal offers) == module balances per denom
// - Sum(pfand_locked by open liquid offers) == module pfand balance (per denom)
func (k Keeper) AssertInvariants(ctx context.Context) error {
	if err := k.checkEscrowInvariant(ctx); err != nil {
		return err
	}
	if err := k.checkPfandInvariant(ctx); err != nil {
		return err
	}
	return nil
}

func (k Keeper) checkEscrowInvariant(ctx context.Context) error {
	// Tally required escrow by denom from open normal offers
	required := map[string]math.Int{}
	_ = k.OffersMap.Walk(ctx, nil, func(_ uint64, o whaleswapv1.OfferData) (bool, error) {
		if o.Status != "open" {
			return false, nil
		}
		// Only normal offers escrow base have in module
		if k.isLiquidDenom(o.RemainingHave.Denom) {
			return false, nil
		}
		if !o.RemainingHave.Amount.IsPositive() {
			return false, nil
		}
		denom := o.RemainingHave.Denom
		if cur, ok := required[denom]; ok {
			required[denom] = cur.Add(o.RemainingHave.Amount)
		} else {
			required[denom] = o.RemainingHave.Amount
		}
		return false, nil
	})

	moduleAddr := k.accKeeper.GetModuleAddress(whaleswap.ModuleName)
	for denom, need := range required {
		bal := k.bank.GetBalance(ctx, moduleAddr, denom).Amount
		if !bal.Equal(need) {
			return cosmossdkerrors.Wrapf(
				sdkerrors.ErrLogic,
				"escrow invariant failed for %s: module=%s required=%s",
				denom, bal.String(), need.String(),
			)
		}
	}
	return nil
}

func (k Keeper) checkPfandInvariant(ctx context.Context) error {
	// Tally pfand_locked across open liquid offers (per denom)
	required := map[string]math.Int{}
	_ = k.OffersMap.Walk(ctx, nil, func(_ uint64, o whaleswapv1.OfferData) (bool, error) {
		if o.Status != "open" {
			return false, nil
		}
		if !k.isLiquidDenom(o.RemainingHave.Denom) {
			return false, nil
		}
		if !o.PfandLocked.Amount.IsPositive() {
			return false, nil
		}
		denom := o.PfandLocked.Denom
		if cur, ok := required[denom]; ok {
			required[denom] = cur.Add(o.PfandLocked.Amount)
		} else {
			required[denom] = o.PfandLocked.Amount
		}
		return false, nil
	})

	moduleAddr := k.accKeeper.GetModuleAddress(whaleswap.ModuleName)
	for denom, need := range required {
		bal := k.bank.GetBalance(ctx, moduleAddr, denom).Amount
		if !bal.Equal(need) {
			return cosmossdkerrors.Wrapf(
				sdkerrors.ErrLogic,
				"pfand invariant failed for %s: module=%s required=%s",
				denom, bal.String(), need.String(),
			)
		}
	}
	return nil
}

// AssertAMMInvariants checks AMM-related invariants across all pools:
// - Module balance per denom must cover the sum of all pool reserves for that denom
// - Shares supply must be > 0 for existing pools; if band set then Lcur > 0
// - Shares denom uniqueness across all pools
func (k Keeper) AssertAMMInvariants(ctx context.Context) error {
	required := map[string]math.Int{}
	shareDenoms := map[string]struct{}{}
	poolCount := 0

	// Accumulate requirements and per-pool sanity
	if err := k.PoolsMap.Walk(ctx, nil, func(_ uint64, p whaleswapv1.Pool) (bool, error) {
		poolCount++
		// Sum reserves by denom
		if cur, ok := required[p.CoinA.Denom]; ok {
			required[p.CoinA.Denom] = cur.Add(p.CoinA.Amount)
		} else {
			required[p.CoinA.Denom] = p.CoinA.Amount
		}
		if cur, ok := required[p.CoinB.Denom]; ok {
			required[p.CoinB.Denom] = cur.Add(p.CoinB.Amount)
		} else {
			required[p.CoinB.Denom] = p.CoinB.Amount
		}

		// Shares supply must be positive
		supply := k.bank.GetSupply(ctx, p.SharesDenom).Amount
		if !supply.IsPositive() {
			return true, cosmossdkerrors.Wrapf(sdkerrors.ErrLogic, "shares supply must be > 0: pool_id=%d denom=%s", p.PoolId, p.SharesDenom)
		}
		// If band set, liquidity must be positive
		if len(p.MinPrice) == 2 {
			Lcur, _, _, err := k.liquidityForReserves(p)
			if err != nil {
				return true, cosmossdkerrors.Wrapf(err, "failed liquidity calc: pool_id=%d", p.PoolId)
			}
			if !Lcur.IsPositive() {
				return true, cosmossdkerrors.Wrapf(sdkerrors.ErrLogic, "invalid pool liquidity: pool_id=%d", p.PoolId)
			}
		}

		// Shares denom uniqueness
		if _, dup := shareDenoms[p.SharesDenom]; dup {
			return true, cosmossdkerrors.Wrapf(sdkerrors.ErrLogic, "duplicate shares denom: %s (pool_id=%d)", p.SharesDenom, p.PoolId)
		}
		shareDenoms[p.SharesDenom] = struct{}{}
		return false, nil
	}); err != nil {
		return err
	}

	if len(shareDenoms) != poolCount {
		return cosmossdkerrors.Wrapf(sdkerrors.ErrLogic, "shares denom uniqueness failed: unique=%d pools=%d", len(shareDenoms), poolCount)
	}

	// Coverage by module balances
	moduleAddr := k.accKeeper.GetModuleAddress(whaleswap.ModuleName)
	for denom, need := range required {
		have := k.bank.GetBalance(ctx, moduleAddr, denom).Amount
		if have.LT(need) {
			return cosmossdkerrors.Wrapf(sdkerrors.ErrLogic, "module balance below AMM reserves for %s: have=%s need=%s", denom, have.String(), need.String())
		}
	}
	return nil
}
