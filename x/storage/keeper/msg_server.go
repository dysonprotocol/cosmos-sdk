package keeper

import (
	"context"
	"crypto/sha256"
	"encoding/base64"
	"fmt"
	"time"

	storagetypes "dysonprotocol.com/x/storage/types"
	sdk "github.com/cosmos/cosmos-sdk/types"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

// We assume your keeper implements storagetypes.MsgServer
var _ storagetypes.MsgServer = Keeper{}

func isPrintableASCII(s string) bool {
	for _, r := range s {
		if r < 32 || r > 126 {
			return false
		}
	}
	return true
}

func (k Keeper) StorageSet(ctx context.Context, msg *storagetypes.MsgStorageSet) (*storagetypes.MsgStorageSetResponse, error) {
	// Validate the owner address is properly formatted
	if _, err := sdk.AccAddressFromBech32(msg.Owner); err != nil {
		return nil, err
	}

	if !isPrintableASCII(msg.Index) {
		return nil, status.Errorf(codes.InvalidArgument, "Invalid index, must be printable ASCII")
	}

	// Create the combined key
	key := msg.Owner + "/" + msg.Index

	blockHeight := uint64(sdk.UnwrapSDKContext(ctx).BlockHeight())
	blockTime := sdk.UnwrapSDKContext(ctx).BlockTime()
	hashBytes := sha256.Sum256([]byte(msg.Data))
	hashB64 := base64.StdEncoding.EncodeToString(hashBytes[:])
	entry := storagetypes.Storage{
		Owner:            msg.Owner,
		Data:             msg.Data,
		Index:            msg.Index,
		UpdatedHeight:    blockHeight,
		UpdatedTimestamp: blockTime.UTC().Format(time.RFC3339),
		Hash:             fmt.Sprintf("sha256-%s", hashB64),
	}

	if err := k.StorageMap.Set(ctx, key, entry); err != nil {
		return nil, err
	}

	// Emit the StorageUpdated event
	sdkCtx := sdk.UnwrapSDKContext(ctx)
	event := storagetypes.EventStorageUpdated{
		Address: msg.Owner,
		Index:   msg.Index,
	}
	if err := sdkCtx.EventManager().EmitTypedEvent(&event); err != nil {
		return nil, err
	}

	return &storagetypes.MsgStorageSetResponse{}, nil
}

func (k Keeper) StorageDelete(ctx context.Context, msg *storagetypes.MsgStorageDelete) (*storagetypes.MsgStorageDeleteResponse, error) {
	// Validate the owner address is properly formatted
	if _, err := sdk.AccAddressFromBech32(msg.Owner); err != nil {
		return nil, err
	}

	// Validate that indexes are provided
	if len(msg.Indexes) == 0 {
		return nil, status.Errorf(codes.InvalidArgument, "must specify at least one index to delete")
	}

	// Track the indexes that were deleted
	var deletedIndexes []string

	// Delete specific indexes
	for _, index := range msg.Indexes {
		// Create the key for this index
		key := msg.Owner + "/" + index

		// Check if the entry exists first
		exists, err := k.StorageMap.Has(ctx, key)
		if err != nil {
			return nil, err
		}

		// Only try to delete if it exists AND belongs to the requesting user
		if exists {
			// Double-check ownership by reading the entry
			entry, err := k.StorageMap.Get(ctx, key)
			if err != nil {
				return nil, err
			}

			// Verify the entry owner matches the message sender
			if entry.Owner != msg.Owner {
				return nil, status.Errorf(codes.PermissionDenied, "cannot delete index [%s] owned by [%s]", index, entry.Owner)
			}

			if err := k.StorageMap.Remove(ctx, key); err != nil {
				return nil, err
			}
			deletedIndexes = append(deletedIndexes, index)
		}
	}

	// Check if any entries were actually deleted
	if len(deletedIndexes) == 0 {
		return nil, status.Errorf(codes.NotFound, "no entries were deleted")
	}

	// Emit the StorageDelete event
	sdkCtx := sdk.UnwrapSDKContext(ctx)
	event := storagetypes.EventStorageDelete{
		Owner:          msg.Owner,
		DeletedIndexes: deletedIndexes,
	}
	if err := sdkCtx.EventManager().EmitTypedEvent(&event); err != nil {
		return nil, err
	}
	return &storagetypes.MsgStorageDeleteResponse{
		DeletedIndexes: deletedIndexes,
	}, nil
}
