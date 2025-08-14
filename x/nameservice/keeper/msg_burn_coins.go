package keeper

import (
	"context"

	cosmossdkerrors "cosmossdk.io/errors"
	nameservice "dysonprotocol.com/x/nameservice"
	nameservicev1 "dysonprotocol.com/x/nameservice/types"
	sdk "github.com/cosmos/cosmos-sdk/types"
	sdkerrors "github.com/cosmos/cosmos-sdk/types/errors"
	bankkeeper "github.com/cosmos/cosmos-sdk/x/bank/keeper"
)

// BurnCoins implements MsgServer.BurnCoins
func (k Keeper) BurnCoins(ctx context.Context, msg *nameservicev1.MsgBurnCoins) (*nameservicev1.MsgBurnCoinsResponse, error) {
	k.Logger.Info("BurnCoins: Processing", "name_destination", msg.NameDestination, "amount", msg.Amount)

	// Get SDK context from context.Context
	sdkCtx := sdk.UnwrapSDKContext(ctx)

	// Verify the address exists and is a valid address
	owner, err := sdk.AccAddressFromBech32(msg.NameDestination)
	if err != nil {
		k.Logger.Error("BurnCoins: Invalid name_destination address", "name_destination", msg.NameDestination, "error", err)
		return nil, cosmossdkerrors.Wrapf(sdkerrors.ErrInvalidAddress, "invalid name_destination address: %s", msg.NameDestination)
	}

	// Check that all coins are of valid denom format for burning
	for _, coin := range msg.Amount {
		// Verify destination authority for the denom
		if err := k.VerifyDenomDestination(ctx, coin.Denom, msg.NameDestination); err != nil {
			k.Logger.Error("BurnCoins: Invalid denom", "denom", coin.Denom, "name_destination", msg.NameDestination, "error", err)
			return nil, cosmossdkerrors.Wrapf(err, "cannot burn coin with denom %s, not controlled by destination %s", coin.Denom, msg.NameDestination)
		}
	}

	// Burn the coins by sending them to the module account
	if err := k.bankKeeper.SendCoinsFromAccountToModule(ctx, owner, nameservice.ModuleName, msg.Amount); err != nil {
		k.Logger.Error("BurnCoins: Failed to transfer coins to module", "error", err)
		return nil, cosmossdkerrors.Wrap(err, "failed to transfer coins to module")
	}

	// Burn the coins from the module account
	if err := k.bankKeeper.BurnCoins(ctx, nameservice.ModuleName, msg.Amount); err != nil {
		k.Logger.Error("BurnCoins: Failed to burn coins", "error", err)
		return nil, cosmossdkerrors.Wrap(err, "failed to burn coins")
	}

	// After burn, if supply is zero, remove from reverse index
	for _, coin := range msg.Amount {
		if !k.bankKeeper.HasSupply(ctx, coin.Denom) {
			if err := k.unsetDenomTracked(ctx, coin.Denom); err != nil {
				return nil, cosmossdkerrors.Wrapf(err, "failed to remove denom %s from index", coin.Denom)
			}

			// Remove metadata when last supply is gone by accessing the concrete bank keeper.
			concrete, ok := any(k.bankKeeper).(bankkeeper.BaseKeeper)
			if !ok {
				return nil, cosmossdkerrors.Wrapf(sdkerrors.ErrLogic, "bank keeper is not BaseKeeper; cannot remove metadata for %s", coin.Denom)
			}
			if err := concrete.BaseViewKeeper.DenomMetadata.Remove(ctx, coin.Denom); err != nil {
				return nil, cosmossdkerrors.Wrapf(err, "failed to remove metadata for denom %s", coin.Denom)
			}
		}
	}

	k.Logger.Info("BurnCoins: Successfully burned coins", "amount", msg.Amount, "name_destination", msg.NameDestination)

	// Emit event
	if err := sdkCtx.EventManager().EmitTypedEvent(
		&nameservicev1.EventCoinsBurned{
			Amount: msg.Amount,
		},
	); err != nil {
		k.Logger.Error("BurnCoins: Failed to emit event", "error", err)
		return nil, cosmossdkerrors.Wrap(err, "failed to emit event")
	}

	return &nameservicev1.MsgBurnCoinsResponse{}, nil
}
