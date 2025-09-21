package keeper

import (
	"context"

	"cosmossdk.io/collections"
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
	// single pool swap; enforce non-zero id
	if msg.PoolId == 0 {
		return nil, cosmossdkerrors.Wrap(sdkerrors.ErrInvalidRequest, "pool_id required")
	}

	if err := k.bank.SendCoinsFromAccountToModule(ctx, trader, whaleswap.ModuleName, sdk.NewCoins(msg.Input)); err != nil {
		return nil, cosmossdkerrors.Wrapf(err, "failed to escrow input %s for trader %s", msg.Input.String(), msg.Trader)
	}

	currentDenom := msg.Input.Denom
	currentAmount := msg.Input.Amount

	pool, gerr := k.PoolsMap.Get(ctx, msg.PoolId)
	if gerr != nil {
		return nil, cosmossdkerrors.Wrapf(gerr, "pool not found: %d", msg.PoolId)
	}

	if len(pool.Coins) != 2 {
		return nil, cosmossdkerrors.Wrap(sdkerrors.ErrInvalidRequest, "invalid pool reserves")
	}
	// two-coin pool in canonical order
	// reserves used inline below; avoid precomputing
	// legacy r1/r2 no longer used in v2 path; concentrated path recomputes from bands

	// Parse fee once; default 0
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

	if currentDenom != pool.Coins[0].Denom && currentDenom != pool.Coins[1].Denom {
		return nil, cosmossdkerrors.Wrapf(sdkerrors.ErrInvalidRequest, "input denom %s not in pool %d", currentDenom, msg.PoolId)
	}

	if len(pool.MinPrice) == 2 {
		// concentrated swap approximation using sqrt-price integration
		sa, sb, err := k.bandSqrt(pool)
		if err != nil {
			return nil, cosmossdkerrors.Wrap(err, "failed to compute band sqrt prices")
		}
		sp, err := k.poolSqrtPrice(pool, pool.Coins[0].Denom, pool.Coins[1].Denom)
		if err != nil {
			return nil, cosmossdkerrors.Wrap(err, "failed to compute current sqrt price")
		}
		Lcur, _, _, err := k.liquidityForReserves(pool)
		if err != nil {
			return nil, cosmossdkerrors.Wrap(err, "invalid pool liquidity")
		}
		if !Lcur.IsPositive() {
			return nil, cosmossdkerrors.Wrap(sdkerrors.ErrInvalidRequest, "invalid pool liquidity")
		}
		effIn := math.LegacyNewDecFromInt(currentAmount).Mul(one.Sub(fee))
		// track fees earned = input - effIn
		feeInt := currentAmount.Sub(effIn.TruncateInt())
		if feeInt.IsPositive() {
			fees := sdk.NewCoins(pool.FeesEarned...).Add(sdk.NewCoin(currentDenom, feeInt))
			pool.FeesEarned = fees
		}
		// use current liquidity Lcur directly
		L := Lcur
		if currentDenom == pool.Coins[0].Denom {
			// token0 (coin A) in: price moves DOWN within band
			// 1/sp' = 1/sp + dX/L  => sp' = 1 / (1/sp + dX/L)
			invSpPrime := math.LegacyOneDec().Quo(sp).Add(effIn.Quo(L))
			if invSpPrime.LTE(math.LegacyZeroDec()) {
				return nil, cosmossdkerrors.Wrap(sdkerrors.ErrInsufficientFunds, "insufficient liquidity")
			}
			spPrime, err := k.sqrtPrice(math.LegacyOneDec().Quo(invSpPrime))
			if err != nil {
				return nil, cosmossdkerrors.Wrap(err, "failed to compute next sqrt price")
			}
			if spPrime.LT(sa) {
				spPrime = sa
			}
			// out = L * (sp - sp')
			outDec := L.Mul(sp.Sub(spPrime))
			outAmt = outDec.TruncateInt()
		} else {
			// token1 (coin B) in: price moves UP within band
			// sp' = sp + dY/L
			spPrime := sp.Add(effIn.Quo(L))
			if spPrime.GT(sb) {
				spPrime = sb
			}
			// out = L * (1/sp - 1/sp')
			outDec := L.Mul(math.LegacyOneDec().Quo(sp).Sub(math.LegacyOneDec().Quo(spPrime)))
			outAmt = outDec.TruncateInt()
		}
		if !outAmt.IsPositive() {
			return nil, cosmossdkerrors.Wrap(sdkerrors.ErrInvalidRequest, "swap output too small")
		}
		// Update integer reserves approximately
		if currentDenom == pool.Coins[0].Denom {
			pool.Coins = sdk.NewCoins(sdk.NewCoin(pool.Coins[0].Denom, pool.Coins[0].Amount.Add(currentAmount)), sdk.NewCoin(pool.Coins[1].Denom, pool.Coins[1].Amount.Sub(outAmt)))
			outDenom = pool.Coins[1].Denom
		} else {
			pool.Coins = sdk.NewCoins(sdk.NewCoin(pool.Coins[0].Denom, pool.Coins[0].Amount.Sub(outAmt)), sdk.NewCoin(pool.Coins[1].Denom, pool.Coins[1].Amount.Add(currentAmount)))
			outDenom = pool.Coins[0].Denom
		}
		// Sanity band check post-swap
		// Cross-multiplication band checks: rQuote/rBase within [minQuote/minBase, maxQuote/maxBase]
		rBase := pool.Coins[0].Amount
		rQuote := pool.Coins[1].Amount
		denomA, denomB := pool.Coins[0].Denom, pool.Coins[1].Denom
		minBase := pool.MinPrice.AmountOf(denomA)
		minQuote := pool.MinPrice.AmountOf(denomB)
		maxBase := pool.MaxPrice.AmountOf(denomA)
		maxQuote := pool.MaxPrice.AmountOf(denomB)
		if rQuote.Mul(minBase).LT(rBase.Mul(minQuote)) {
			return nil, cosmossdkerrors.Wrapf(sdkerrors.ErrInvalidRequest, "resulting price below band after swap")
		}
		if rQuote.Mul(maxBase).GT(rBase.Mul(maxQuote)) {
			return nil, cosmossdkerrors.Wrapf(sdkerrors.ErrInvalidRequest, "resulting price above band after swap")
		}
	} else {
		// v2 constant product path
		inputIdx := 0
		if currentDenom != pool.Coins[0].Denom {
			inputIdx = 1
		}
		outputIdx := 1 - inputIdx

		rIn := math.LegacyNewDecFromInt(pool.Coins[inputIdx].Amount)
		rOut := math.LegacyNewDecFromInt(pool.Coins[outputIdx].Amount)

		effIn := math.LegacyNewDecFromInt(currentAmount).Mul(one.Sub(fee))
		feeInt := currentAmount.Sub(effIn.TruncateInt())
		if feeInt.IsPositive() {
			fees := sdk.NewCoins(pool.FeesEarned...).Add(sdk.NewCoin(currentDenom, feeInt))
			pool.FeesEarned = fees
		}
		// out = rOut - K / (rIn + effIn)
		kDec := rIn.Mul(rOut)
		q := kDec.Quo(rIn.Add(effIn)).Ceil()
		outDec := rOut.Sub(q)
		outAmt = outDec.TruncateInt()
		if !outAmt.IsPositive() {
			return nil, cosmossdkerrors.Wrap(sdkerrors.ErrInvalidRequest, "swap output too small")
		}
		// Update reserves: add input, subtract output
		newIn := pool.Coins[inputIdx].Amount.Add(currentAmount)
		newOut := pool.Coins[outputIdx].Amount.Sub(outAmt)
		if inputIdx == 0 {
			pool.Coins = sdk.NewCoins(
				sdk.NewCoin(pool.Coins[0].Denom, newIn),
				sdk.NewCoin(pool.Coins[1].Denom, newOut),
			)
		} else {
			pool.Coins = sdk.NewCoins(
				sdk.NewCoin(pool.Coins[0].Denom, newOut),
				sdk.NewCoin(pool.Coins[1].Denom, newIn),
			)
		}
		outDenom = pool.Coins[outputIdx].Denom
	}

	// persist and emit pool update
	pool.NumTrades += 1
	if err := k.updatePool(ctx, &pool); err != nil {
		return nil, cosmossdkerrors.Wrapf(err, "failed to update pool %d after swap", pool.PoolId)
	}
	sdkCtx := sdk.UnwrapSDKContext(ctx)
	if err := sdkCtx.EventManager().EmitTypedEvent(&whaleswapv1.EventPoolSwap{PoolId: pool.PoolId}); err != nil {
		return nil, cosmossdkerrors.Wrapf(err, "failed to emit EventPoolSwap")
	}

	currentDenom = outDenom
	currentAmount = outAmt

	// Validate minimum_output
	if msg.MinimumOutput.Denom == "" {
		return nil, cosmossdkerrors.Wrap(sdkerrors.ErrInvalidRequest, "minimum_output.denom required")
	}
	if currentDenom != msg.MinimumOutput.Denom {
		return nil, cosmossdkerrors.Wrapf(sdkerrors.ErrInvalidRequest, "output denom %s != expected %s", currentDenom, msg.MinimumOutput.Denom)
	}
	if msg.MinimumOutput.Amount.IsNegative() {
		return nil, cosmossdkerrors.Wrap(sdkerrors.ErrInvalidRequest, "minimum_output.amount must be >= 0")
	}
	if currentAmount.LT(msg.MinimumOutput.Amount) {
		return nil, cosmossdkerrors.Wrapf(sdkerrors.ErrInvalidRequest, "output %s below minimum %s", currentAmount.String(), msg.MinimumOutput.Amount.String())
	}

	if err := k.bank.SendCoinsFromModuleToAccount(ctx, whaleswap.ModuleName, trader, sdk.NewCoins(sdk.NewCoin(currentDenom, currentAmount))); err != nil {
		return nil, cosmossdkerrors.Wrapf(err, "failed to send output %s to trader %s", sdk.NewCoin(currentDenom, currentAmount).String(), msg.Trader)
	}
	if err := k.AssertAMMInvariants(ctx); err != nil {
		return nil, cosmossdkerrors.Wrapf(err,
			"AMM invariant after PoolSwap: pool_id=%d in=%s out=%s newR=(%s,%s)",
			pool.PoolId,
			sdk.NewCoin(msg.Input.Denom, msg.Input.Amount).String(),
			sdk.NewCoin(currentDenom, currentAmount).String(),
			sdk.NewCoin(pool.Coins[0].Denom, pool.Coins[0].Amount).String(),
			sdk.NewCoin(pool.Coins[1].Denom, pool.Coins[1].Amount).String(),
		)
	}
	// After successful settlement and invariants: record Trade and emit event
	tradeId, terr := k.tradeSeq.Next(ctx)
	if terr != nil {
		return nil, cosmossdkerrors.Wrap(terr, "failed to allocate trade id")
	}
	sdkCtx = sdk.UnwrapSDKContext(ctx)
	t := sdkCtx.BlockTime()
	trade := whaleswapv1.Trade{
		TradeId:   tradeId,
		OfferId:   0,
		Taker:     msg.Trader,
		Height:    uint64(sdkCtx.BlockHeight()),
		Timestamp: &t,
		Sent:      msg.Input,
		Received:  sdk.NewCoin(currentDenom, currentAmount),
		PoolId:    pool.PoolId,
		AuctionId: 0,
	}
	if err := k.TradesMap.Set(ctx, tradeId, trade); err != nil {
		return nil, cosmossdkerrors.Wrap(err, "failed to save trade")
	}
	if err := k.TradesByPoolIndex.Set(ctx, collections.Join(pool.PoolId, tradeId), tradeId); err != nil {
		return nil, cosmossdkerrors.Wrapf(err, "failed to index trade by pool")
	}
	if err := k.TradesByTakerIndex.Set(ctx, collections.Join(msg.Trader, tradeId), tradeId); err != nil {
		return nil, cosmossdkerrors.Wrapf(err, "failed to index trade by taker")
	}
	if err := sdkCtx.EventManager().EmitTypedEvent(&whaleswapv1.EventTradeRecorded{TradeId: tradeId, OfferId: 0, PoolId: pool.PoolId, AuctionId: 0}); err != nil {
		return nil, cosmossdkerrors.Wrapf(err, "failed to emit EventTradeRecorded")
	}
	return &whaleswapv1.MsgPoolSwapResponse{AmountOut: sdk.NewCoin(currentDenom, currentAmount)}, nil
}
