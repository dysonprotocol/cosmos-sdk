package keeper

import (
	"context"
	"fmt"
	"strings"

	cosmossdkerrors "cosmossdk.io/errors"
	"cosmossdk.io/math"
	nameservicev1 "dysonprotocol.com/x/nameservice/types"
	whaleswap "dysonprotocol.com/x/whaleswap"
	whaleswapv1 "dysonprotocol.com/x/whaleswap/types"
	sdk "github.com/cosmos/cosmos-sdk/types"
	sdkerrors "github.com/cosmos/cosmos-sdk/types/errors"
)

func (k Keeper) CreatePool(ctx context.Context, msg *whaleswapv1.MsgCreatePool) (*whaleswapv1.MsgCreatePoolResponse, error) {
	// Canonical denom ordering (coin1 < coin2 lexicographically)
	coinA := msg.CoinA
	coinB := msg.CoinB
	if strings.Compare(coinA.Denom, coinB.Denom) > 0 {
		coinA, coinB = coinB, coinA
	}

	if msg.FeePct != "" {
		fee, err := math.LegacyNewDecFromStr(msg.FeePct)
		if err != nil {
			return nil, cosmossdkerrors.Wrapf(sdkerrors.ErrInvalidRequest, "invalid fee_pct: %v", err)
		}
		if fee.IsNegative() || fee.GTE(math.LegacyNewDec(1)) {
			return nil, cosmossdkerrors.Wrapf(sdkerrors.ErrInvalidRequest, "fee_pct must satisfy 0 <= fee < 1: %s", fee.String())
		}
	}

	// Normalize bands against canonical denom order
	minBand, err := k.normalizeBand(msg.MinPrice, coinA.Denom, coinB.Denom)
	if err != nil {
		return nil, fmt.Errorf("invalid min_price: %w", err)
	}
	maxBand, err := k.normalizeBand(msg.MaxPrice, coinA.Denom, coinB.Denom)
	if err != nil {
		return nil, fmt.Errorf("invalid max_price: %w", err)
	}

	if len(minBand) == 2 && len(maxBand) == 2 {
		// Ensure max >= min
		minRatio := math.LegacyNewDecFromInt(minBand.AmountOf(coinB.Denom)).Quo(math.LegacyNewDecFromInt(minBand.AmountOf(coinA.Denom)))
		maxRatio := math.LegacyNewDecFromInt(maxBand.AmountOf(coinB.Denom)).Quo(math.LegacyNewDecFromInt(maxBand.AmountOf(coinA.Denom)))
		if maxRatio.LT(minRatio) {
			return nil, fmt.Errorf("max_price must be >= min_price")
		}
	} else if len(minBand) != 0 || len(maxBand) != 0 {
		return nil, fmt.Errorf("min_price [%s] and max_price [%s] must be both set or both unset", minBand.String(), maxBand.String())
	}

	// Move funds from creator to module
	from, err := k.addr(ctx, msg.Creator)
	if err != nil {
		return nil, cosmossdkerrors.Wrapf(err, "failed to get creator address: %s", msg.Creator)
	}

	coins := sdk.NewCoins(coinA, coinB)
	if err := k.sendToModule(ctx, from, coins); err != nil {
		return nil, cosmossdkerrors.Wrapf(err, "failed to send funds to module: %s", from.String())
	}

	// Allocate new pool id and construct pool (we'll compute initial shares proportionally)
	id, err := k.poolSeq.Next(ctx)
	if err != nil {
		return nil, cosmossdkerrors.Wrapf(err, "failed to allocate new pool id")
	}
	sharesDenom := fmt.Sprintf("whaleswap.dys/pools/%d", id)

	sdkCtx := sdk.UnwrapSDKContext(ctx)
	// Enforce initial price within band if band is set
	if len(minBand) == 2 {
		// P = reserve2/reserve1 using initial reserves
		if coinA.Amount.IsZero() || coinB.Amount.IsZero() {
			return nil, fmt.Errorf("initial reserves must be > 0")
		}
		p := math.LegacyNewDecFromInt(coinB.Amount).Quo(math.LegacyNewDecFromInt(coinA.Amount))
		minRatio := math.LegacyNewDecFromInt(minBand.AmountOf(coinB.Denom)).Quo(math.LegacyNewDecFromInt(minBand.AmountOf(coinA.Denom)))
		maxRatio := math.LegacyNewDecFromInt(maxBand.AmountOf(coinB.Denom)).Quo(math.LegacyNewDecFromInt(maxBand.AmountOf(coinA.Denom)))
		if p.LT(minRatio) || p.GT(maxRatio) {
			return nil, fmt.Errorf("initial price %s outside band [%s, %s]", p.String(), minRatio.String(), maxRatio.String())
		}
	}

	t := sdkCtx.BlockTime()
	pool := whaleswapv1.Pool{
		PoolId:      id,
		CoinA:       coinA,
		CoinB:       coinB,
		SharesDenom: sharesDenom,
		FeePct:      msg.FeePct,
		MinPrice:    minBand,
		MaxPrice:    maxBand,
		BlockHeight: uint64(sdkCtx.BlockHeight()),
		Created:     &t,
		Updated:     &t,
		NumTrades:   0,
	}
	// Compute initial shares proportional to liquidity
	var initialShares math.Int
	if len(minBand) == 2 {
		L, _, _, err := k.liquidityForReserves(pool)
		if err != nil {
			return nil, cosmossdkerrors.Wrap(err, "failed to compute initial liquidity")
		}
		initialShares = L.TruncateInt()
	} else {
		// v2: initial shares = floor(sqrt(R1*R2))
		prod := math.LegacyNewDecFromInt(coinA.Amount).Mul(math.LegacyNewDecFromInt(coinB.Amount))
		sqrt, err := prod.ApproxSqrt()
		if err != nil {
			return nil, cosmossdkerrors.Wrap(err, "failed to sqrt initial product")
		}
		initialShares = sqrt.TruncateInt()
	}
	if !initialShares.IsPositive() {
		initialShares = math.NewInt(1)
	}
	if err := k.PoolsMap.Set(ctx, id, pool); err != nil {
		return nil, cosmossdkerrors.Wrap(err, "failed to set pool")
	}

	// Mint initial shares to creator via nameservice (no fee when destination is module)
	// Ensure whaleswap root name exists and resolves to the module address so nameservice
	// mint verification passes for shares denom whaleswap.dys/pools/<id>.
	if err := k.ensureWhaleswapRootName(ctx); err != nil {
		return nil, cosmossdkerrors.Wrapf(err, "failed ensuring whaleswap.dys root before minting shares for pool %d", id)
	}

	// Build mint request with zero udys fee; nameservice skips fee for module destinations
	mintMsg := &nameservicev1.MsgMintCoins{
		NameDestination: k.accKeeper.GetModuleAddress(whaleswap.ModuleName).String(),
		Amount:          sdk.NewCoins(sdk.NewCoin(sharesDenom, initialShares)),
		MintFee:         sdk.NewCoin("udys", math.NewInt(0)),
	}
	if _, err := k.nameSvc.MintCoins(ctx, mintMsg); err != nil {
		return nil, cosmossdkerrors.Wrap(err, "mint shares failed")
	}
	if err := k.sendFromModule(ctx, from, sdk.NewCoins(sdk.NewCoin(sharesDenom, initialShares))); err != nil {
		return nil, cosmossdkerrors.Wrap(err, "send minted shares failed")
	}

	// Emit events
	_ = sdkCtx.EventManager().EmitTypedEvent(&whaleswapv1.EventPoolCreated{PoolId: id})
	_ = sdkCtx.EventManager().EmitTypedEvent(&whaleswapv1.EventPoolUpdate{PoolId: id})
	if err := k.AssertAMMInvariants(ctx); err != nil {
		return nil, cosmossdkerrors.Wrapf(err,
			"AMM invariant after CreatePool: pool_id=%d coinA=%s coinB=%s shares_denom=%s",
			id, coinA.String(), coinB.String(), sharesDenom,
		)
	}
	return &whaleswapv1.MsgCreatePoolResponse{PoolId: id}, nil
}
