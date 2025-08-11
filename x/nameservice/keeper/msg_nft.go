package keeper

import (
	"context"
	"regexp"
	"strings"
	"time"

	cosmossdkerrors "cosmossdk.io/errors"
	nameservicev1 "dysonprotocol.com/x/nameservice/types"
	"dysonprotocol.com/x/nft"
	sdk "github.com/cosmos/cosmos-sdk/types"
	sdkerrors "github.com/cosmos/cosmos-sdk/types/errors"
)

var (
	// validClassIDPattern defines the regex for valid NFT class ID strings
	// Must match the same pattern used for coin denominations
	validClassIDPattern = regexp.MustCompile(`^[A-Za-z0-9.\-_]+\.dys(?:/[0-9A-Za-z:\-_]+)*$`)

	// validNFTIDPattern defines the regex for valid NFT ID strings
	// Must be printable ASCII characters
	validNFTIDPattern = regexp.MustCompile(`^[\x20-\x7E]+$`)
)

// Helper function to get the root name of a class ID
func getClassIDRootName(classID string) string {
	parts := strings.Split(classID, "/")
	return parts[0]
}

// verifyClassIDOwner checks if the provided owner is the owner of the root name in the class ID
func (k Keeper) verifyClassIDOwner(ctx context.Context, classID string, owner string) error {
	// 1. Validate the class ID format
	if !validClassIDPattern.MatchString(classID) {
		return cosmossdkerrors.Wrapf(
			sdkerrors.ErrInvalidRequest,
			"invalid class ID format: %s (must be alphanumeric with optional hyphens/underscores, ending in .dys, optionally followed by /path)",
			classID,
		)
	}

	// 2. Extract the root name from the class ID
	rootName := getClassIDRootName(classID)

	// 3. Verify the owner owns the root name
	rootOwner, found := k.GetNameOwner(ctx, rootName)
	if !found {
		return cosmossdkerrors.Wrapf(
			sdkerrors.ErrNotFound,
			"root name not found: %s",
			rootName,
		)
	}

	// 4. Check if the owner matches
	if rootOwner != owner {
		return cosmossdkerrors.Wrapf(
			sdkerrors.ErrUnauthorized,
			"only the owner of the root name (%s) can perform this action on class %s",
			rootOwner,
			classID,
		)
	}

	return nil
}

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
	nftData := nameservicev1.NFTData{
		Listed:          false,
		Valuation:       sdk.Coin{},
		ValuationExpiry: sdkCtx.BlockTime().Add(time.Hour * 24 * 365),
		CurrentBidder:   "",
		CurrentBid:      sdk.Coin{},
		BidTimestamp:    nil,
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
