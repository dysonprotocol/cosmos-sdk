package keeper

import (
	"context"
	"fmt"
	"strings"

	"cosmossdk.io/collections"
	cosmossdkerrors "cosmossdk.io/errors"
	"cosmossdk.io/math"
	nameservicev1 "dysonprotocol.com/x/nameservice/types"
	whaleswap "dysonprotocol.com/x/whaleswap"
	whaleswapv1 "dysonprotocol.com/x/whaleswap/types"
	sdk "github.com/cosmos/cosmos-sdk/types"
	sdkerrors "github.com/cosmos/cosmos-sdk/types/errors"
)

func (k Keeper) MakeOffer(ctx context.Context, msg *whaleswapv1.MsgMakeOffer) (*whaleswapv1.MsgMakeOfferResponse, error) {
	// Parse maker
	makerBz, err := k.accKeeper.AddressCodec().StringToBytes(msg.Maker)
	if err != nil {
		return nil, fmt.Errorf("invalid maker")
	}
	maker := sdk.AccAddress(makerBz)

	have := msg.Have
	want := msg.Want
	if have.Denom == want.Denom {
		return nil, cosmossdkerrors.Wrapf(sdkerrors.ErrInvalidRequest, "have and want denoms must differ: %s", have.Denom)
	}
	if !have.Amount.IsPositive() || !want.Amount.IsPositive() {
		return nil, cosmossdkerrors.Wrap(sdkerrors.ErrInvalidRequest, "amounts must be > 0")
	}
	if k.isLiquidDenom(want.Denom) {
		return nil, cosmossdkerrors.Wrapf(sdkerrors.ErrInvalidRequest, "want denom is liquid: %s", want.Denom)
	}

	pfandCoin := sdk.NewCoin(k.GetParams(ctx).PfandPerOffer.Denom, math.NewInt(0))
	if k.isLiquidDenom(have.Denom) {
		req := k.GetParams(ctx).PfandPerOffer
		if !req.Amount.IsZero() {
			bal := k.bank.GetBalance(ctx, maker, req.Denom).Amount
			if bal.LT(req.Amount) {
				return nil, cosmossdkerrors.Wrapf(sdkerrors.ErrInsufficientFunds, "insufficient pfand: %s < %s", bal.String(), req.Amount.String())
			}
			if err := k.bank.SendCoinsFromAccountToModule(ctx, maker, whaleswap.ModuleName, sdk.NewCoins(req)); err != nil {
				return nil, err
			}
		}
		pfandCoin = k.GetParams(ctx).PfandPerOffer
	} else {
		if err := k.bank.SendCoinsFromAccountToModule(ctx, maker, whaleswap.ModuleName, sdk.NewCoins(have)); err != nil {
			return nil, err
		}
	}

	lcm := k.lcmInt(have.Amount, want.Amount)
	if !lcm.IsPositive() {
		return nil, cosmossdkerrors.Wrap(sdkerrors.ErrInvalidRequest, "invalid lcm")
	}
	unitHave := lcm.Quo(want.Amount)
	unitWant := lcm.Quo(have.Amount)
	if unitHave.IsZero() || unitWant.IsZero() {
		return nil, cosmossdkerrors.Wrap(sdkerrors.ErrInvalidRequest, "invalid unit ints")
	}
	remainingUnits := have.Amount.Quo(unitHave)
	if remainingUnits.IsZero() {
		return nil, cosmossdkerrors.Wrap(sdkerrors.ErrInvalidRequest, "remaining units is zero")
	}

	id, err := k.offerSeq.Next(ctx)
	if err != nil {
		return nil, err
	}
	sdkCtx := sdk.UnwrapSDKContext(ctx)
	t := sdkCtx.BlockTime()
	offer := whaleswapv1.OfferData{
		OfferId:          id,
		Status:           "open",
		Maker:            msg.Maker,
		UpdatedHeight:    uint64(sdkCtx.BlockHeight()),
		UpdatedTimestamp: &t,
		InitialHave:      have,
		InitialWant:      want,
		RemainingHave:    have,
		RemainingWant:    want,
		UnitHaveInt:      unitHave.String(),
		UnitWantInt:      unitWant.String(),
		RemainingUnits:   remainingUnits.String(),
		PfandLocked:      pfandCoin,
	}
	if err := k.OffersMap.Set(ctx, id, offer); err != nil {
		return nil, err
	}
	// Reverse indexes
	// have, id -> id
	if err := k.OffersByHave.Set(ctx, collections.Join(offer.RemainingHave.Denom, offer.OfferId), offer.OfferId); err != nil {
		return nil, err
	}
	// want, id -> id
	if err := k.OffersByWant.Set(ctx, collections.Join(offer.RemainingWant.Denom, offer.OfferId), offer.OfferId); err != nil {
		return nil, err
	}
	// Price index normalized by sorted pair key: low|high, price = (high per low)
	haveDenom := offer.RemainingHave.Denom
	wantDenom := offer.RemainingWant.Denom
	low, high := haveDenom, wantDenom
	if low > high {
		low, high = high, low
	}
	pairKey := low + "|" + high
	priceHavePerWant := math.LegacyNewDecFromInt(offer.RemainingHave.Amount).Quo(math.LegacyNewDecFromInt(offer.RemainingWant.Amount))
	priceWantPerHave := math.LegacyNewDecFromInt(offer.RemainingWant.Amount).Quo(math.LegacyNewDecFromInt(offer.RemainingHave.Amount))
	priceDec := priceWantPerHave
	if low == wantDenom && high == haveDenom {
		priceDec = priceHavePerWant
	}
	if err := k.OffersByPairPrice.Set(ctx, collections.Join3(pairKey, priceDec.String(), offer.OfferId), offer.OfferId); err != nil {
		return nil, err
	}
	// owner+status index
	if err := k.OffersByOwnerStatus.Set(ctx, collections.Join3(offer.Maker, offer.Status, offer.OfferId), offer.OfferId); err != nil {
		return nil, err
	}
	_ = sdkCtx.EventManager().EmitTypedEvent(&whaleswapv1.EventOfferCreated{OfferId: id})
	if pfandCoin.Amount.IsPositive() {
		_ = sdkCtx.EventManager().EmitTypedEvent(&whaleswapv1.EventPfandLocked{Amount: pfandCoin})
	}
	return &whaleswapv1.MsgMakeOfferResponse{OfferId: id}, nil
}

func (k Keeper) TakeOffer(ctx context.Context, msg *whaleswapv1.MsgTakeOffer) (*whaleswapv1.MsgTakeOfferResponse, error) {
	takerBz, err := k.accKeeper.AddressCodec().StringToBytes(msg.Taker)
	if err != nil {
		return nil, fmt.Errorf("invalid taker")
	}
	taker := sdk.AccAddress(takerBz)
	if len(msg.Trades) == 0 {
		return nil, fmt.Errorf("trades list must be non-empty")
	}
	seen := map[uint64]struct{}{}
	sdkCtx := sdk.UnwrapSDKContext(ctx)
	t := sdkCtx.BlockTime()

	for _, it := range msg.Trades {
		if _, dup := seen[it.OfferId]; dup {
			return nil, cosmossdkerrors.Wrapf(sdkerrors.ErrInvalidRequest, "duplicate offer_id %d", it.OfferId)
		}
		seen[it.OfferId] = struct{}{}

		offer, err := k.OffersMap.Get(ctx, it.OfferId)
		if err != nil {
			return nil, cosmossdkerrors.Wrapf(sdkerrors.ErrNotFound, "offer not found: %d", it.OfferId)
		}
		if offer.Status != "open" {
			return nil, cosmossdkerrors.Wrapf(sdkerrors.ErrInvalidRequest, "offer %d not open", it.OfferId)
		}
		remainingUnits, ok := math.NewIntFromString(offer.RemainingUnits)
		if !ok || remainingUnits.IsZero() {
			return nil, fmt.Errorf("invalid remaining units")
		}
		takeUnits := remainingUnits
		if strings.TrimSpace(it.TakeUnits) != "" {
			u, ok := math.NewIntFromString(it.TakeUnits)
			if !ok || !u.IsPositive() {
				return nil, cosmossdkerrors.Wrap(sdkerrors.ErrInvalidRequest, "invalid take_units")
			}
			takeUnits = u
		}
		if takeUnits.GT(remainingUnits) {
			return nil, cosmossdkerrors.Wrapf(sdkerrors.ErrInvalidRequest, "take_units exceeds remaining: %s > %s", takeUnits.String(), remainingUnits.String())
		}

		unitWant, _ := math.NewIntFromString(offer.UnitWantInt)
		unitHave, _ := math.NewIntFromString(offer.UnitHaveInt)
		requiredWant := takeUnits.Mul(unitWant)
		deliverHave := takeUnits.Mul(unitHave)

		wantDenom := offer.RemainingWant.Denom
		haveDenom := offer.RemainingHave.Denom
		makerBz, err := k.accKeeper.AddressCodec().StringToBytes(offer.Maker)
		if err != nil {
			return nil, cosmossdkerrors.Wrapf(sdkerrors.ErrInvalidAddress, "invalid maker address: %s %s", offer.Maker, err.Error())
		}
		maker := sdk.AccAddress(makerBz)

		baseBal := k.bank.GetBalance(ctx, taker, wantDenom).Amount
		basePay := requiredWant
		if baseBal.LT(basePay) {
			basePay = baseBal
		}
		remainder := requiredWant.Sub(basePay)
		if basePay.IsPositive() {
			if err := k.bank.SendCoinsFromAccountToModule(ctx, taker, whaleswap.ModuleName, sdk.NewCoins(sdk.NewCoin(wantDenom, basePay))); err != nil {
				return nil, err
			}
		}
		if remainder.IsPositive() {
			liquidWant := liquidPrefix + wantDenom
			liqBal := k.bank.GetBalance(ctx, taker, liquidWant).Amount
			if liqBal.LT(remainder) {
				return nil, cosmossdkerrors.Wrapf(sdkerrors.ErrInsufficientFunds, "insufficient liquid remainder: %s < %s", liqBal.String(), remainder.String())
			}
			if err := k.bank.SendCoinsFromAccountToModule(ctx, taker, whaleswap.ModuleName, sdk.NewCoins(sdk.NewCoin(liquidWant, remainder))); err != nil {
				return nil, err
			}
			if _, err := k.nameSvc.BurnCoins(ctx, &nameservicev1.MsgBurnCoins{
				NameDestination: k.accKeeper.GetModuleAddress(whaleswap.ModuleName).String(),
				Amount:          sdk.NewCoins(sdk.NewCoin(liquidWant, remainder)),
			}); err != nil {
				return nil, err
			}
		}
		if err := k.bank.SendCoinsFromModuleToAccount(ctx, whaleswap.ModuleName, maker, sdk.NewCoins(sdk.NewCoin(wantDenom, requiredWant))); err != nil {
			return nil, err
		}

		if k.isLiquidDenom(haveDenom) {
			makerBal := k.bank.GetBalance(ctx, maker, haveDenom).Amount
			if makerBal.LT(deliverHave) {
				return nil, cosmossdkerrors.Wrapf(sdkerrors.ErrInsufficientFunds, "maker insufficient liquid have: %s < %s", makerBal.String(), deliverHave.String())
			}
			if err := k.bank.SendCoinsFromAccountToModule(ctx, maker, whaleswap.ModuleName, sdk.NewCoins(sdk.NewCoin(haveDenom, deliverHave))); err != nil {
				return nil, err
			}
			if _, err := k.nameSvc.BurnCoins(ctx, &nameservicev1.MsgBurnCoins{
				NameDestination: k.accKeeper.GetModuleAddress(whaleswap.ModuleName).String(),
				Amount:          sdk.NewCoins(sdk.NewCoin(haveDenom, deliverHave)),
			}); err != nil {
				return nil, err
			}
			baseHave, err := k.decodeLiquidDenom(haveDenom)
			if err != nil {
				return nil, err
			}
			backing := k.bank.GetBalance(ctx, k.accKeeper.GetModuleAddress(whaleswap.ModuleName), baseHave).Amount
			if backing.LT(deliverHave) {
				return nil, cosmossdkerrors.Wrapf(sdkerrors.ErrInsufficientFunds, "insufficient backing for have: %s < %s", backing.String(), deliverHave.String())
			}
			if err := k.bank.SendCoinsFromModuleToAccount(ctx, whaleswap.ModuleName, taker, sdk.NewCoins(sdk.NewCoin(baseHave, deliverHave))); err != nil {
				return nil, err
			}
		} else {
			if err := k.bank.SendCoinsFromModuleToAccount(ctx, whaleswap.ModuleName, taker, sdk.NewCoins(sdk.NewCoin(haveDenom, deliverHave))); err != nil {
				return nil, err
			}
		}

		tradeId, err := k.tradeSeq.Next(ctx)
		if err != nil {
			return nil, err
		}
		trade := whaleswapv1.Trade{
			TradeId:   tradeId,
			OfferId:   offer.OfferId,
			Taker:     msg.Taker,
			Height:    uint64(sdkCtx.BlockHeight()),
			Timestamp: &t,
			Sent:      sdk.NewCoin(wantDenom, requiredWant),
			Received:  sdk.NewCoin(haveDenom, deliverHave),
		}
		if err := k.TradesMap.Set(ctx, tradeId, trade); err != nil {
			return nil, err
		}

		newUnits := remainingUnits.Sub(takeUnits)
		offer.UpdatedHeight = uint64(sdkCtx.BlockHeight())
		offer.UpdatedTimestamp = &t
		if newUnits.IsZero() {
			offer.Status = "closed"
			offer.RemainingUnits = newUnits.String()
			offer.RemainingHave.Amount = math.NewInt(0)
			offer.RemainingWant.Amount = math.NewInt(0)
			// Remove reverse index entries on close
			_ = k.OffersByHave.Remove(ctx, collections.Join(offer.RemainingHave.Denom, offer.OfferId))
			_ = k.OffersByWant.Remove(ctx, collections.Join(offer.RemainingWant.Denom, offer.OfferId))
			uh, _ := math.NewIntFromString(offer.UnitHaveInt)
			uw, _ := math.NewIntFromString(offer.UnitWantInt)
			if uh.IsPositive() && uw.IsPositive() {
				haveDenom := offer.RemainingHave.Denom
				wantDenom := offer.RemainingWant.Denom
				low, high := haveDenom, wantDenom
				if low > high {
					low, high = high, low
				}
				pairKey := low + "|" + high
				priceHavePerWant := math.LegacyNewDecFromInt(uh).Quo(math.LegacyNewDecFromInt(uw))
				priceWantPerHave := math.LegacyNewDecFromInt(uw).Quo(math.LegacyNewDecFromInt(uh))
				priceDec := priceWantPerHave
				if low == wantDenom && high == haveDenom {
					priceDec = priceHavePerWant
				}
				_ = k.OffersByPairPrice.Remove(ctx, collections.Join3(pairKey, priceDec.String(), offer.OfferId))
			}
			_ = k.OffersByOwnerStatus.Remove(ctx, collections.Join3(offer.Maker, "open", offer.OfferId))
			_ = k.OffersByOwnerStatus.Set(ctx, collections.Join3(offer.Maker, offer.Status, offer.OfferId), offer.OfferId)
			if offer.PfandLocked.Amount.IsPositive() {
				if err := k.bank.SendCoinsFromModuleToAccount(ctx, whaleswap.ModuleName, taker, sdk.NewCoins(offer.PfandLocked)); err != nil {
					return nil, err
				}
				_ = sdkCtx.EventManager().EmitTypedEvent(&whaleswapv1.EventPfandReleased{Amount: offer.PfandLocked})
			}
		} else {
			offer.RemainingUnits = newUnits.String()
			offer.RemainingHave.Amount = newUnits.Mul(unitHave)
			offer.RemainingWant.Amount = newUnits.Mul(unitWant)
		}
		if err := k.OffersMap.Set(ctx, offer.OfferId, offer); err != nil {
			return nil, err
		}

		_ = sdkCtx.EventManager().EmitTypedEvent(&whaleswapv1.EventOfferTaken{OfferId: offer.OfferId, TradeId: tradeId})
	}
	return &whaleswapv1.MsgTakeOfferResponse{Ok: true}, nil
}

func (k Keeper) CancelOffer(ctx context.Context, msg *whaleswapv1.MsgCancelOffer) (*whaleswapv1.MsgCancelOfferResponse, error) {
	offer, err := k.OffersMap.Get(ctx, msg.OfferId)
	if err != nil {
		return nil, fmt.Errorf("offer not found")
	}
	if offer.Status != "open" {
		return nil, fmt.Errorf("offer not open: %s", offer.Status)
	}
	closerBz, err := k.accKeeper.AddressCodec().StringToBytes(msg.Closer)
	if err != nil {
		return nil, fmt.Errorf("invalid closer")
	}
	closer := sdk.AccAddress(closerBz)
	makerBz, err := k.accKeeper.AddressCodec().StringToBytes(offer.Maker)
	if err != nil {
		return nil, fmt.Errorf("invalid maker")
	}
	maker := sdk.AccAddress(makerBz)

	eligible := closer.Equals(maker)
	pfandLocked := offer.PfandLocked
	if !eligible && pfandLocked.Amount.IsPositive() {
		haveDenom := offer.RemainingHave.Denom
		unitHave := offer.UnitHaveInt
		unit, ok := math.NewIntFromString(unitHave)
		if !ok || !unit.IsPositive() {
			return nil, fmt.Errorf("invalid unit_have_int")
		}
		makerBal := k.bank.GetBalance(ctx, maker, haveDenom).Amount
		if makerBal.LT(unit) {
			eligible = true
		}
	}
	if !eligible {
		return nil, fmt.Errorf("not eligible to cancel offer")
	}

	offer.Status = "cancelled"
	if err := k.OffersMap.Set(ctx, offer.OfferId, offer); err != nil {
		return nil, err
	}
	// Remove reverse index entries on cancel
	_ = k.OffersByHave.Remove(ctx, collections.Join(offer.RemainingHave.Denom, offer.OfferId))
	_ = k.OffersByWant.Remove(ctx, collections.Join(offer.RemainingWant.Denom, offer.OfferId))
	uh, _ := math.NewIntFromString(offer.UnitHaveInt)
	uw, _ := math.NewIntFromString(offer.UnitWantInt)
	if uh.IsPositive() && uw.IsPositive() {
		haveDenom := offer.RemainingHave.Denom
		wantDenom := offer.RemainingWant.Denom
		low, high := haveDenom, wantDenom
		if low > high {
			low, high = high, low
		}
		pairKey := low + "|" + high
		priceHavePerWant := math.LegacyNewDecFromInt(uh).Quo(math.LegacyNewDecFromInt(uw))
		priceWantPerHave := math.LegacyNewDecFromInt(uw).Quo(math.LegacyNewDecFromInt(uh))
		priceDec := priceWantPerHave
		if low == wantDenom && high == haveDenom {
			priceDec = priceHavePerWant
		}
		_ = k.OffersByPairPrice.Remove(ctx, collections.Join3(pairKey, priceDec.String(), offer.OfferId))
	}
	_ = k.OffersByOwnerStatus.Remove(ctx, collections.Join3(offer.Maker, "open", offer.OfferId))
	_ = k.OffersByOwnerStatus.Set(ctx, collections.Join3(offer.Maker, offer.Status, offer.OfferId), offer.OfferId)
	if pfandLocked.Amount.IsPositive() {
		if err := k.bank.SendCoinsFromModuleToAccount(ctx, whaleswap.ModuleName, closer, sdk.NewCoins(pfandLocked)); err != nil {
			return nil, err
		}
	}

	// Emit events
	sdkCtx := sdk.UnwrapSDKContext(ctx)
	_ = sdkCtx.EventManager().EmitTypedEvent(&whaleswapv1.EventOfferCancelled{OfferId: offer.OfferId})
	if pfandLocked.Amount.IsPositive() {
		_ = sdkCtx.EventManager().EmitTypedEvent(&whaleswapv1.EventPfandReleased{Amount: pfandLocked})
	}
	return &whaleswapv1.MsgCancelOfferResponse{}, nil
}
