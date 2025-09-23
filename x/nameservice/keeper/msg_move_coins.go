package keeper

import (
	"context"

	cosmossdkerrors "cosmossdk.io/errors"
	nameservicev1 "dysonprotocol.com/x/nameservice/types"
	sdk "github.com/cosmos/cosmos-sdk/types"
	sdkerrors "github.com/cosmos/cosmos-sdk/types/errors"
)

// MoveCoins transfers custom coins between two accounts if the signer owns the root denom
func (k Keeper) MoveCoins(ctx context.Context, msg *nameservicev1.MsgMoveCoins) (*nameservicev1.MsgMoveCoinsResponse, error) {
	if len(msg.Inputs) == 0 || len(msg.Outputs) == 0 {
		return nil, cosmossdkerrors.Wrap(sdkerrors.ErrInvalidRequest, "inputs and outputs cannot be empty")
	}

	// Validate inputs and collect names
	nameSet := make(map[string]struct{})
	for _, in := range msg.Inputs {
		if addr, err := sdk.AccAddressFromBech32(in.Address); err == nil {
			if acc := k.accountKeeper.GetAccount(sdk.UnwrapSDKContext(ctx), addr); acc != nil {
				if _, ok := acc.(sdk.ModuleAccountI); ok {
					// Allow module input only if signer (name_destination) equals that module address
					if addr.String() != msg.NameDestination {
						return nil, cosmossdkerrors.Wrap(sdkerrors.ErrInvalidAddress, "input address is a module account")
					}
				}
			}
		} else {
			return nil, cosmossdkerrors.Wrapf(sdkerrors.ErrInvalidAddress, "invalid address: %s", in.Address)
		}
		for _, coin := range in.Coins {
			if _, root, err := k.GetDenomOwner(sdk.UnwrapSDKContext(ctx), coin.Denom); err != nil {
				return nil, err
			} else {
				nameSet[root] = struct{}{}
				if err := k.VerifyDenomDestination(ctx, coin.Denom, msg.NameDestination); err != nil {
					return nil, err
				}
			}
		}
	}

	// Validate outputs
	for _, out := range msg.Outputs {
		if addr, err := sdk.AccAddressFromBech32(out.Address); err == nil {
			if acc := k.accountKeeper.GetAccount(sdk.UnwrapSDKContext(ctx), addr); acc != nil {
				if _, ok := acc.(sdk.ModuleAccountI); ok {
					// Allow module output only if signer (name_destination) equals that module address
					if addr.String() != msg.NameDestination {
						return nil, cosmossdkerrors.Wrap(sdkerrors.ErrInvalidAddress, "output address is a module account")
					}
				}
			}
		} else {
			return nil, cosmossdkerrors.Wrapf(sdkerrors.ErrInvalidAddress, "invalid address: %s", out.Address)
		}
	}

	if err := k.moveCoins(ctx, msg.Inputs, msg.Outputs); err != nil {
		return nil, cosmossdkerrors.Wrap(err, "failed to move coins")
	}

	var names []string
	for n := range nameSet {
		names = append(names, n)
	}

	if evErr := sdk.UnwrapSDKContext(ctx).EventManager().EmitTypedEvent(
		&nameservicev1.EventCoinsMoved{
			Names: names,
		},
	); evErr != nil {
		k.Logger.Error("failed to emit coins moved event", "error", evErr)
	}

	k.Logger.Info("MoveCoins: moved coins", "name_destination", msg.NameDestination)
	return &nameservicev1.MsgMoveCoinsResponse{}, nil
}
