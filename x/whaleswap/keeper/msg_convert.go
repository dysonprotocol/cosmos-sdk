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

func (k Keeper) ConvertToLiquid(ctx context.Context, msg *whaleswapv1.MsgConvertToLiquid) (*whaleswapv1.MsgConvertToLiquidResponse, error) {
	callerBz, err := k.accKeeper.AddressCodec().StringToBytes(msg.Caller)
	if err != nil {
		return nil, fmt.Errorf("invalid caller")
	}
	caller := sdk.AccAddress(callerBz)
	if strings.TrimSpace(msg.Denom) == "" {
		return nil, cosmossdkerrors.Wrap(sdkerrors.ErrInvalidRequest, "denom required")
	}
	amt, ok := math.NewIntFromString(msg.Amount)
	if !ok || !amt.IsPositive() {
		return nil, cosmossdkerrors.Wrap(sdkerrors.ErrInvalidRequest, "invalid amount")
	}
	if err := k.bank.SendCoinsFromAccountToModule(ctx, caller, whaleswap.ModuleName, sdk.NewCoins(sdk.NewCoin(msg.Denom, amt))); err != nil {
		return nil, err
	}
	liquidDenom := liquidPrefix + msg.Denom
	mintMsg := &nameservicev1.MsgMintCoins{
		NameDestination: k.accKeeper.GetModuleAddress(whaleswap.ModuleName).String(),
		Amount:          sdk.NewCoins(sdk.NewCoin(liquidDenom, amt)),
		MintFee:         sdk.NewCoin("udys", math.NewInt(0)),
	}
	if _, err := k.nameSvc.MintCoins(ctx, mintMsg); err != nil {
		return nil, err
	}
	if err := k.bank.SendCoinsFromModuleToAccount(ctx, whaleswap.ModuleName, caller, sdk.NewCoins(sdk.NewCoin(liquidDenom, amt))); err != nil {
		return nil, err
	}
	return &whaleswapv1.MsgConvertToLiquidResponse{LiquidDenom: liquidDenom, Amount: amt.String()}, nil
}

func (k Keeper) ConvertToSolid(ctx context.Context, msg *whaleswapv1.MsgConvertToSolid) (*whaleswapv1.MsgConvertToSolidResponse, error) {
	callerBz, err := k.accKeeper.AddressCodec().StringToBytes(msg.Caller)
	if err != nil {
		return nil, fmt.Errorf("invalid caller")
	}
	caller := sdk.AccAddress(callerBz)
	if strings.TrimSpace(msg.LiquidDenom) == "" {
		return nil, cosmossdkerrors.Wrap(sdkerrors.ErrInvalidRequest, "liquid_denom required")
	}
	amt, ok := math.NewIntFromString(msg.Amount)
	if !ok || !amt.IsPositive() {
		return nil, cosmossdkerrors.Wrap(sdkerrors.ErrInvalidRequest, "invalid amount")
	}
	solid, err := k.decodeLiquidDenom(msg.LiquidDenom)
	if err != nil {
		return nil, err
	}
	if err := k.bank.SendCoinsFromAccountToModule(ctx, caller, whaleswap.ModuleName, sdk.NewCoins(sdk.NewCoin(msg.LiquidDenom, amt))); err != nil {
		return nil, err
	}
	if _, err := k.nameSvc.BurnCoins(ctx, &nameservicev1.MsgBurnCoins{
		NameDestination: k.accKeeper.GetModuleAddress(whaleswap.ModuleName).String(),
		Amount:          sdk.NewCoins(sdk.NewCoin(msg.LiquidDenom, amt)),
	}); err != nil {
		return nil, err
	}
	backing := k.bank.GetBalance(ctx, k.accKeeper.GetModuleAddress(whaleswap.ModuleName), solid).Amount
	if backing.LT(amt) {
		return nil, fmt.Errorf("insufficient escrow backing")
	}
	if err := k.bank.SendCoinsFromModuleToAccount(ctx, whaleswap.ModuleName, caller, sdk.NewCoins(sdk.NewCoin(solid, amt))); err != nil {
		return nil, err
	}
	return &whaleswapv1.MsgConvertToSolidResponse{AmountOut: sdk.NewCoin(solid, amt)}, nil
}
