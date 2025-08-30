package keeper

import (
	"context"
	"strings"

	cosmossdkerrors "cosmossdk.io/errors"
	nameservicev1 "dysonprotocol.com/x/nameservice/types"
	"dysonprotocol.com/x/nft"
	sdk "github.com/cosmos/cosmos-sdk/types"
	sdkerrors "github.com/cosmos/cosmos-sdk/types/errors"
)

// SaveClass implements the MsgServer.SaveClass method
func (k Keeper) SaveClass(ctx context.Context, msg *nameservicev1.MsgSaveClass) (*nameservicev1.MsgSaveClassResponse, error) {
	// Verify destination-based authorization for root name of class ID
	if err := k.VerifyClassRootDestination(ctx, msg.ClassId, msg.NameDestination); err != nil {
		return nil, err
	}

	// If the class already exists we treat this call as an **update** (upsert behaviour).
	if k.nftKeeper.HasClass(ctx, msg.ClassId) {
		// Fetch existing class
		existing, found := k.nftKeeper.GetClass(ctx, msg.ClassId)
		if !found {
			// This should never happen because HasClass returned true, but guard anyway
			return nil, cosmossdkerrors.Wrapf(
				sdkerrors.ErrNotFound,
				"class not found after HasClass=true: %s",
				msg.ClassId,
			)
		}

		// Merge non-blank fields coming from the message
		updated := existing // copy
		if strings.TrimSpace(msg.Name) != "" {
			updated.Name = msg.Name
		}
		if strings.TrimSpace(msg.Symbol) != "" {
			updated.Symbol = msg.Symbol
		}
		if strings.TrimSpace(msg.Description) != "" {
			updated.Description = msg.Description
		}
		if strings.TrimSpace(msg.Uri) != "" {
			updated.Uri = msg.Uri
		}
		if strings.TrimSpace(msg.UriHash) != "" {
			updated.UriHash = msg.UriHash
		}

		// Persist update
		if err := k.nftKeeper.UpdateClass(ctx, updated); err != nil {
			return nil, cosmossdkerrors.Wrap(err, "failed to update NFT class")
		}

		// Maintain reverse index for this class under its root name
		root := extractRootName(msg.ClassId)
		if err := k.SetClassByRootName(ctx, root, msg.ClassId); err != nil {
			return nil, cosmossdkerrors.Wrap(err, "failed to update reverse index for class root name")
		}

		// Emit event
		sdkCtx := sdk.UnwrapSDKContext(ctx)
		if evErr := sdkCtx.EventManager().EmitTypedEvent(
			&nameservicev1.EventClassSaved{ // reuse same event structure
				ClassId: msg.ClassId,
			},
		); evErr != nil {
			k.Logger.Error("failed to emit class updated event", "error", evErr)
		}

		k.Logger.Info("Successfully updated NFT class",
			"class_id", msg.ClassId,
			"name_destination", msg.NameDestination)

		return &nameservicev1.MsgSaveClassResponse{}, nil
	}

	// ------------------------------
	// Class does NOT yet exist → create new as before

	// 1. Validate class ID already done by verifyClassIDOwner

	// 2. Create the NFT class from supplied fields
	class := nft.Class{
		Id:          msg.ClassId,
		Name:        msg.Name,
		Symbol:      msg.Symbol,
		Description: msg.Description,
		Uri:         msg.Uri,
		UriHash:     msg.UriHash,
	}

	if err := k.nftKeeper.SaveClass(ctx, class); err != nil {
		return nil, cosmossdkerrors.Wrap(err, "failed to save NFT class")
	}

	// Set default per-class bidding params by copying from nameservice.dys
	if !k.nftKeeper.HasClass(ctx, NamesClassID) {
		return nil, cosmossdkerrors.Wrapf(sdkerrors.ErrNotFound, "default class %s not found to seed params", NamesClassID)
	}

	// Set default per-class bidding params by copying from nameservice.dys, they can be updated later
	defaultData, err := k.GetNFTClassData(ctx, NamesClassID)
	if err != nil {
		return nil, cosmossdkerrors.Wrap(err, "failed to get default class params from nameservice.dys")
	}

	if err := k.SetNFTClassData(ctx, msg.ClassId, defaultData); err != nil {
		return nil, cosmossdkerrors.Wrap(err, "failed to set default class params")
	}

	// Maintain reverse index for this class under its root name
	root := extractRootName(msg.ClassId)
	if err := k.SetClassByRootName(ctx, root, msg.ClassId); err != nil {
		return nil, cosmossdkerrors.Wrap(err, "failed to set reverse index for class root name")
	}

	sdkCtx := sdk.UnwrapSDKContext(ctx)
	if evErr := sdkCtx.EventManager().EmitTypedEvent(
		&nameservicev1.EventClassSaved{ClassId: msg.ClassId},
	); evErr != nil {
		k.Logger.Error("failed to emit class saved event", "error", evErr)
	}

	k.Logger.Info("Successfully created NFT class",
		"class_id", msg.ClassId,
		"name_destination", msg.NameDestination)

	return &nameservicev1.MsgSaveClassResponse{}, nil
}

// MintNFT implements the MsgServer.MintNFT method
func (k Keeper) MintNFT(ctx context.Context, msg *nameservicev1.MsgMintNFT) (*nameservicev1.MsgMintNFTResponse, error) {
	// Verify destination-based authorization for root name of class ID
	if err := k.VerifyClassRootDestination(ctx, msg.ClassId, msg.NameDestination); err != nil {
		return nil, err
	}

	// Check if the class exists
	if !k.nftKeeper.HasClass(ctx, msg.ClassId) {
		return nil, cosmossdkerrors.Wrapf(
			sdkerrors.ErrNotFound,
			"class not found: %s",
			msg.ClassId,
		)
	}

	// Check if NFT already exists
	if k.nftKeeper.HasNFT(ctx, msg.ClassId, msg.NftId) {
		return nil, cosmossdkerrors.Wrapf(
			sdkerrors.ErrInvalidRequest,
			"NFT already exists in class %s with ID %s",
			msg.ClassId,
			msg.NftId,
		)
	}

	// Convert signer to account address
	ownerAddr, err := sdk.AccAddressFromBech32(msg.NameDestination)
	if err != nil {
		return nil, cosmossdkerrors.Wrapf(sdkerrors.ErrInvalidAddress, "invalid name_destination address: %s", msg.NameDestination)
	}

	// Create the NFT
	token := nft.NFT{
		ClassId: msg.ClassId,
		Id:      msg.NftId,
		Uri:     msg.Uri,
		UriHash: msg.UriHash,
	}

	// Mint the NFT first
	if err := k.nftKeeper.Mint(ctx, token, ownerAddr); err != nil {
		return nil, cosmossdkerrors.Wrap(err, "failed to mint NFT")
	}
	sdkCtx := sdk.UnwrapSDKContext(ctx)

	// Now set the NFT data after the NFT exists
	// Default ValuationExpiry to now + class valuation_period
	classData, err := k.GetNFTClassData(ctx, msg.ClassId)
	if err != nil {
		return nil, cosmossdkerrors.Wrap(err, "failed to get class data for valuation expiry")
	}
	period := classData.ValuationPeriod
	if period <= 0 {
		return nil, cosmossdkerrors.Wrapf(sdkerrors.ErrInvalidRequest, "valuation_period not set for class %s", msg.ClassId)
	}
	nftData := nameservicev1.NFTData{
		Listed:          false,
		Valuation:       sdk.Coin{},
		ValuationExpiry: sdkCtx.BlockTime().Add(period),
		CurrentBidder:   "",
		CurrentBid:      sdk.Coin{},
		BidTimestamp:    nil,
		BidHeight:       0,
		Metadata:        "",
	}
	if err := k.SetNFTData(ctx, token.ClassId, token.Id, nftData); err != nil {
		return nil, cosmossdkerrors.Wrapf(err, "failed to set NFT data for class %s, id %s", token.ClassId, token.Id)
	}

	// Emit event using SDK context
	if evErr := sdkCtx.EventManager().EmitTypedEvent(
		&nameservicev1.EventNFTMinted{
			ClassId: msg.ClassId,
			NftId:   msg.NftId,
		},
	); evErr != nil {
		k.Logger.Error("failed to emit NFT minted event", "error", evErr)
		return nil, cosmossdkerrors.Wrap(evErr, "failed to emit NFT minted event")
	}

	k.Logger.Info("Successfully minted NFT",
		"class_id", msg.ClassId,
		"id", msg.NftId,
		"name_destination", msg.NameDestination)

	return &nameservicev1.MsgMintNFTResponse{}, nil
}

// BurnNFT implements the MsgServer.BurnNFT method
func (k Keeper) BurnNFT(ctx context.Context, msg *nameservicev1.MsgBurnNFT) (*nameservicev1.MsgBurnNFTResponse, error) {
	// Verify destination-based authorization for root name of class ID
	if err := k.VerifyClassRootDestination(ctx, msg.ClassId, msg.NameDestination); err != nil {
		return nil, err
	}

	// Check if the NFT exists
	if !k.nftKeeper.HasNFT(ctx, msg.ClassId, msg.NftId) {
		return nil, cosmossdkerrors.Wrapf(
			sdkerrors.ErrNotFound,
			"NFT not found: %s/%s",
			msg.ClassId,
			msg.NftId,
		)
	}

	// Burn the NFT
	if err := k.nftKeeper.Burn(ctx, msg.ClassId, msg.NftId); err != nil {
		return nil, cosmossdkerrors.Wrap(err, "failed to burn NFT")
	}

	// Emit event using SDK context
	sdkCtx := sdk.UnwrapSDKContext(ctx)
	if evErr := sdkCtx.EventManager().EmitTypedEvent(
		&nameservicev1.EventNFTBurned{
			ClassId: msg.ClassId,
			NftId:   msg.NftId,
		},
	); evErr != nil {
		k.Logger.Error("failed to emit NFT burned event", "error", evErr)
		return nil, cosmossdkerrors.Wrap(evErr, "failed to emit NFT burned event")
	}

	k.Logger.Info("Successfully burned NFT",
		"class_id", msg.ClassId,
		"id", msg.NftId,
		"name_destination", msg.NameDestination)

	return &nameservicev1.MsgBurnNFTResponse{}, nil
}

// DeleteClass implements the MsgServer.DeleteClass method
func (k Keeper) DeleteClass(ctx context.Context, msg *nameservicev1.MsgDeleteClass) (*nameservicev1.MsgDeleteClassResponse, error) {
	// Verify destination-based authorization for root name of class ID
	if err := k.VerifyClassRootDestination(ctx, msg.ClassId, msg.NameDestination); err != nil {
		return nil, cosmossdkerrors.Wrapf(err, "authorization failed for class %s", msg.ClassId)
	}

	// Ensure class exists
	if !k.nftKeeper.HasClass(ctx, msg.ClassId) {
		return nil, cosmossdkerrors.Wrapf(sdkerrors.ErrNotFound, "cannot delete: class not found: %s", msg.ClassId)
	}

	// Ensure the class has no NFTs
	if total := k.nftKeeper.GetTotalSupply(ctx, msg.ClassId); total != 0 {
		return nil, cosmossdkerrors.Wrapf(sdkerrors.ErrInvalidRequest, "cannot delete non-empty class %s: %d NFTs exist", msg.ClassId, total)
	}

	// Remove class from NFT module
	if err := k.nftKeeper.RemoveClass(ctx, msg.ClassId); err != nil {
		return nil, cosmossdkerrors.Wrapf(err, "failed to delete NFT class: %s", msg.ClassId)
	}

	// Remove reverse index mapping for this class under its root name
	root := extractRootName(msg.ClassId)
	if err := k.RemoveClassByRootName(ctx, root, msg.ClassId); err != nil {
		return nil, cosmossdkerrors.Wrapf(err, "failed to remove reverse index for class root name %s", root)
	}

	// Emit event
	sdkCtx := sdk.UnwrapSDKContext(ctx)
	if evErr := sdkCtx.EventManager().EmitTypedEvent(
		&nameservicev1.EventClassDeleted{ClassId: msg.ClassId},
	); evErr != nil {
		k.Logger.Error("failed to emit class deleted event", "error", evErr)
	}

	k.Logger.Info("Successfully deleted NFT class",
		"class_id", msg.ClassId,
		"name_destination", msg.NameDestination)

	return &nameservicev1.MsgDeleteClassResponse{}, nil
}
