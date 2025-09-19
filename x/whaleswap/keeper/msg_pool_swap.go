package keeper

import (
	"context"

	cosmossdkerrors "cosmossdk.io/errors"
	"cosmossdk.io/math"
	whaleswap "dysonprotocol.com/x/whaleswap"
	whaleswapv1 "dysonprotocol.com/x/whaleswap/types"
	sdk "github.com/cosmos/cosmos-sdk/types"
	sdkerrors "github.com/cosmos/cosmos-sdk/types/errors"
)

func (k Keeper) PoolSwap(ctx context.Context, msg *whaleswapv1.MsgPoolSwap) (*whaleswapv1.MsgPoolSwapResponse, error) {
	accCodec := k.accKeeper.AddressCodec()
	traderBz, err := accCodec.StringToBytes(msg.Trader)
	if err != nil {
		return nil, cosmossdkerrors.Wrapf(sdkerrors.ErrInvalidAddress, "invalid trader: %s", err.Error())
	}
	trader := sdk.AccAddress(traderBz)

	if !msg.Input.Amount.IsPositive() {
		return nil, cosmossdkerrors.Wrap(sdkerrors.ErrInvalidRequest, "input amount must be > 0")
	}
	// single pool swap
	if msg.PoolId == 0 {
		return nil, cosmossdkerrors.Wrap(sdkerrors.ErrInvalidRequest, "pool_id required")
	}

	if err := k.bank.SendCoinsFromAccountToModule(ctx, trader, whaleswap.ModuleName, sdk.NewCoins(msg.Input)); err != nil {
		return nil, err
	}

	currentDenom := msg.Input.Denom
	currentAmount := msg.Input.Amount

	pool, gerr := k.PoolsMap.Get(ctx, msg.PoolId)
	if gerr != nil {
		return nil, gerr
	}

	r1Int := pool.CoinA.Amount
	r2Int := pool.CoinB.Amount
	r1 := math.LegacyNewDecFromInt(r1Int)
	r2 := math.LegacyNewDecFromInt(r2Int)

	fee := math.LegacyNewDec(0)
	if pool.FeePct != "" {
		f, ferr := math.LegacyNewDecFromStr(pool.FeePct)
		if ferr != nil {
			return nil, cosmossdkerrors.Wrap(sdkerrors.ErrInvalidRequest, "invalid pool fee_pct: "+ferr.Error())
		}
		fee = f
	}
	one := math.LegacyNewDec(1)

	var outAmt math.Int
	var outDenom string

	if currentDenom != pool.CoinA.Denom && currentDenom != pool.CoinB.Denom {
		return nil, cosmossdkerrors.Wrapf(sdkerrors.ErrInvalidRequest, "input denom %s not in pool %d", currentDenom, msg.PoolId)
	}

	if len(pool.MinPrice) == 2 {
		// concentrated swap approximation using sqrt-price integration
		sa, sb, err := k.bandSqrt(pool)
		if err != nil {
			return nil, err
		}
		sp, err := k.poolSqrtPrice(pool)
		if err != nil {
			return nil, err
		}
		effIn := math.LegacyNewDecFromInt(currentAmount).Mul(one.Sub(fee))
		if currentDenom == pool.CoinA.Denom {
			// token1 -> token2: move price up: dxe = L*(1/sp - 1/sp')
			L, _, _, err := k.liquidityForReserves(pool)
			if err != nil {
				return nil, err
			}
			// solve for sp': 1/sp' = 1/sp - dxe/L
			invSpPrime := math.LegacyOneDec().Quo(sp).Sub(effIn.Quo(L))
			if invSpPrime.LTE(math.LegacyZeroDec()) {
				return nil, cosmossdkerrors.Wrap(sdkerrors.ErrInsufficientFunds, "insufficient liquidity")
			}
			spPrime, err := k.sqrtPrice(math.LegacyOneDec().Quo(invSpPrime))
			if err != nil {
				return nil, err
			}
			if spPrime.GT(sb) {
				spPrime = sb
			}
			outDec := L.Mul(spPrime.Sub(sp))
			outAmt = outDec.TruncateInt()
		} else {
			// token2 -> token1: move price down: dye = L*(sp' - sp)
			L, _, _, err := k.liquidityForReserves(pool)
			if err != nil {
				return nil, err
			}
			spPrime := sp.Sub(effIn.Quo(L))
			if spPrime.LT(sa) {
				spPrime = sa
			}
			outDec := L.Mul(sp.Sub(spPrime))
			outAmt = outDec.TruncateInt()
		}
		if !outAmt.IsPositive() {
			return nil, cosmossdkerrors.Wrap(sdkerrors.ErrInvalidRequest, "swap output too small")
		}
		// Update integer reserves approximately
		if currentDenom == pool.CoinA.Denom {
			pool.CoinA.Amount = pool.CoinA.Amount.Add(currentAmount)
			pool.CoinB.Amount = pool.CoinB.Amount.Sub(outAmt)
			outDenom = pool.CoinB.Denom
		} else {
			pool.CoinB.Amount = pool.CoinB.Amount.Add(currentAmount)
			pool.CoinA.Amount = pool.CoinA.Amount.Sub(outAmt)
			outDenom = pool.CoinA.Denom
		}
		// Sanity band check post-swap
		newR1 := math.LegacyNewDecFromInt(pool.CoinA.Amount)
		newR2 := math.LegacyNewDecFromInt(pool.CoinB.Amount)
		p := newR2.Quo(newR1)
		minRatio := math.LegacyNewDecFromInt(pool.MinPrice.AmountOf(pool.CoinB.Denom)).Quo(math.LegacyNewDecFromInt(pool.MinPrice.AmountOf(pool.CoinA.Denom)))
		maxRatio := math.LegacyNewDecFromInt(pool.MaxPrice.AmountOf(pool.CoinB.Denom)).Quo(math.LegacyNewDecFromInt(pool.MaxPrice.AmountOf(pool.CoinA.Denom)))
		if p.LT(minRatio) {
			return nil, cosmossdkerrors.Wrapf(sdkerrors.ErrInvalidRequest, "resulting price [%s] below band after swap: minRatio [%s]", p.String(), minRatio.String())
		}
		if p.GT(maxRatio) {
			return nil, cosmossdkerrors.Wrapf(sdkerrors.ErrInvalidRequest, "resulting price [%s] above band after swap: maxRatio [%s]", p.String(), maxRatio.String())
		}
	} else {
		// v2 constant product path
		if currentDenom == pool.CoinA.Denom {
			effIn := math.LegacyNewDecFromInt(currentAmount).Mul(one.Sub(fee))
			kDec := r1.Mul(r2)
			q := kDec.Quo(r1.Add(effIn)).Ceil()
			outDec := r2.Sub(q)
			outAmt = outDec.TruncateInt()
			if !outAmt.IsPositive() {
				return nil, cosmossdkerrors.Wrap(sdkerrors.ErrInvalidRequest, "swap output too small")
			}
			pool.CoinA.Amount = pool.CoinA.Amount.Add(currentAmount)
			pool.CoinB.Amount = pool.CoinB.Amount.Sub(outAmt)
			outDenom = pool.CoinB.Denom
		} else {
			effIn := math.LegacyNewDecFromInt(currentAmount).Mul(one.Sub(fee))
			kDec := r1.Mul(r2)
			q := kDec.Quo(r2.Add(effIn)).Ceil()
			outDec := r1.Sub(q)
			outAmt = outDec.TruncateInt()
			if !outAmt.IsPositive() {
				return nil, cosmossdkerrors.Wrap(sdkerrors.ErrInvalidRequest, "swap output too small")
			}
			pool.CoinB.Amount = pool.CoinB.Amount.Add(currentAmount)
			pool.CoinA.Amount = pool.CoinA.Amount.Sub(outAmt)
			outDenom = pool.CoinA.Denom
		}
	}

	// persist and emit pool update
	pool.NumTrades += 1
	if err := k.updatePool(ctx, &pool); err != nil {
		return nil, err
	}
	sdkCtx := sdk.UnwrapSDKContext(ctx)
	_ = sdkCtx.EventManager().EmitTypedEvent(&whaleswapv1.EventPoolSwap{PoolId: pool.PoolId})

	currentDenom = outDenom
	currentAmount = outAmt

	if currentDenom != msg.OutDenom {
		return nil, cosmossdkerrors.Wrapf(sdkerrors.ErrInvalidRequest, "output denom %s != expected %s", currentDenom, msg.OutDenom)
	}
	minOut, ok := math.NewIntFromString(msg.MinimumOutAmount)
	if !ok {
		return nil, cosmossdkerrors.Wrap(sdkerrors.ErrInvalidRequest, "invalid minimum_out_amount")
	}
	if currentAmount.LT(minOut) {
		return nil, cosmossdkerrors.Wrapf(sdkerrors.ErrInvalidRequest, "output %s below minimum %s", currentAmount.String(), minOut.String())
	}

	if err := k.bank.SendCoinsFromModuleToAccount(ctx, whaleswap.ModuleName, trader, sdk.NewCoins(sdk.NewCoin(currentDenom, currentAmount))); err != nil {
		return nil, err
	}
	return &whaleswapv1.MsgPoolSwapResponse{AmountOut: sdk.NewCoin(currentDenom, currentAmount)}, nil
}
