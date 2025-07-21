package keeper

import (
	"context"
	"crypto/sha256"
	"encoding/base64"
	"fmt"
	"time"

	cosmossdkerrors "cosmossdk.io/errors"
	storagetypes "dysonprotocol.com/x/storage/types"
	sdk "github.com/cosmos/cosmos-sdk/types"
	sdkerrors "github.com/cosmos/cosmos-sdk/types/errors"
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

	// Get current parameters to check max storage size
	params := k.GetParams(ctx)
	dataSize := uint64(len(msg.Data))

	if dataSize > params.MaxStorageSize {
		return nil, status.Errorf(codes.InvalidArgument, "data size %d bytes exceeds maximum allowed size %d bytes", dataSize, params.MaxStorageSize)
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

// UpdateParams updates the module parameters
func (k Keeper) UpdateParams(ctx context.Context, msg *storagetypes.MsgUpdateParams) (*storagetypes.MsgUpdateParamsResponse, error) {
	// Check authority - this should be the governance module account or a dedicated module admin
	if msg.Authority != k.GetAuthority() {
		return nil, cosmossdkerrors.Wrapf(
			sdkerrors.ErrUnauthorized,
			"invalid authority; expected %s, got %s",
			k.GetAuthority(),
			msg.Authority,
		)
	}

	// Validate the parameters
	if err := msg.Params.Validate(); err != nil {
		return nil, cosmossdkerrors.Wrap(err, "invalid parameters")
	}

	// Set the parameters
	if err := k.SetParams(ctx, msg.Params); err != nil {
		return nil, cosmossdkerrors.Wrap(err, "failed to update parameters")
	}

	return &storagetypes.MsgUpdateParamsResponse{}, nil
}
