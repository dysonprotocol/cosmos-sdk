package keeper

import (
	"context"

	cosmossdkerrors "cosmossdk.io/errors"
	nameservicev1 "dysonprotocol.com/x/nameservice/types"
	sdk "github.com/cosmos/cosmos-sdk/types"
	sdkerrors "github.com/cosmos/cosmos-sdk/types/errors"
)

// MoveNft transfers an NFT if signer owns the class and current owner is non-module
func (k Keeper) MoveNft(ctx context.Context, msg *nameservicev1.MsgMoveNft) (*nameservicev1.MsgMoveNftResponse, error) {
	// validate addresses
	sdkCtx := sdk.UnwrapSDKContext(ctx)
	if _, err := sdk.AccAddressFromBech32(msg.NameDestination); err != nil {
		return nil, cosmossdkerrors.Wrapf(sdkerrors.ErrInvalidAddress, "invalid name_destination address: %s", msg.NameDestination)
	}
	toAddr, err := sdk.AccAddressFromBech32(msg.ToAddress)
	if err != nil {
		return nil, cosmossdkerrors.Wrapf(sdkerrors.ErrInvalidAddress, "invalid to address: %s", msg.ToAddress)
	}

	// Get the current owner of the NFT
	fromAddr := k.nftKeeper.GetOwner(ctx, msg.ClassId, msg.NftId)
	if fromAddr.Empty() {
		return nil, cosmossdkerrors.Wrapf(sdkerrors.ErrNotFound, "NFT not found: class %s, id %s", msg.ClassId, msg.NftId)
	}

	// Verify current owner is not a module account, unless signer is that module (bootstrap case)
	if fromAcc := k.accountKeeper.GetAccount(sdkCtx, fromAddr); fromAcc != nil {
		if _, ok := fromAcc.(sdk.ModuleAccountI); ok {
			// Allow transfer only when the signer (name_destination) is exactly the current owner module account
			if fromAddr.String() != msg.NameDestination {
				return nil, cosmossdkerrors.Wrap(sdkerrors.ErrInvalidAddress, "current NFT owner is a module account")
			}
		}
	}

	// Verify destination is not a module account unless the signer is the module account
	if acc := k.accountKeeper.GetAccount(sdkCtx, toAddr); acc != nil {
		if _, ok := acc.(sdk.ModuleAccountI); ok {
			if fromAddr.String() != msg.NameDestination {
				return nil, cosmossdkerrors.Wrap(sdkerrors.ErrInvalidAddress, "to_address is a module account")
			}
		}
	}

	// verify owner owns the root name of the class
	if err := k.VerifyClassRootDestination(sdkCtx, msg.ClassId, msg.NameDestination); err != nil {
		return nil, err
	}

	// perform transfer via nftKeeper (class_id, nft_id)
	if err := k.nftKeeper.Transfer(sdkCtx, msg.ClassId, msg.NftId, toAddr); err != nil {
		k.Logger.Error("MoveNft: Failed to transfer NFT", "error", err)
		return nil, cosmossdkerrors.Wrap(err, "failed to move nft")
	}

	// emit event
	if evErr := sdkCtx.EventManager().EmitTypedEvent(
		&nameservicev1.EventNftMoved{
			ClassId:     msg.ClassId,
			NftId:       msg.NftId,
			FromAddress: fromAddr.String(),
			ToAddress:   msg.ToAddress,
		},
	); evErr != nil {
		k.Logger.Error("failed to emit nft moved event", "error", evErr)
	}

	k.Logger.Info("MoveNft: moved nft", "class", msg.ClassId, "id", msg.NftId)
	return &nameservicev1.MsgMoveNftResponse{}, nil
}
