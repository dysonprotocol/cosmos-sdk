package keeper

import (
	"context"
	"crypto/sha256"
	"encoding/base64"
	"fmt"
	"strings"
	"time"

	"cosmossdk.io/collections"
	errorsmod "cosmossdk.io/errors"
	storagetypes "dysonprotocol.com/x/storage/types"
	sdk "github.com/cosmos/cosmos-sdk/types"
	sdkerrors "github.com/cosmos/cosmos-sdk/types/errors"
	"github.com/tidwall/gjson"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

// We assume your keeper implements storagetypes.MsgServer
var _ storagetypes.MsgServer = Keeper{}

func (k Keeper) StorageSet(ctx context.Context, msg *storagetypes.MsgStorageSet) (*storagetypes.MsgStorageSetResponse, error) {
	// Validate the owner address is properly formatted
	if _, err := sdk.AccAddressFromBech32(msg.Owner); err != nil {
		return nil, err
	}

	// Create the key directly using strings
	key := collections.Join(msg.Owner, msg.Index)

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

	// Validate mutual exclusivity - either indexes OR (index_prefix with optional filter)
	hasIndexes := len(msg.Indexes) > 0
	hasIndexPrefix := msg.IndexPrefix != ""
	hasFilter := msg.Filter != ""

	// Check mutual exclusivity
	if hasIndexes && hasIndexPrefix {
		return nil, status.Errorf(codes.InvalidArgument, "cannot specify both indexes and index_prefix")
	}
	if !hasIndexes && !hasIndexPrefix {
		return nil, status.Errorf(codes.InvalidArgument, "must specify either indexes or index_prefix")
	}
	if hasFilter && !hasIndexPrefix {
		return nil, status.Errorf(codes.InvalidArgument, "filter can only be used with index_prefix")
	}

	// Track the indexes that were deleted
	var deletedIndexes []string

	if hasIndexes {
		// OPTION 1: Delete specific indexes
		for _, index := range msg.Indexes {
			// Create the key for this index
			key := collections.Join(msg.Owner, index)

			// Check if the entry exists first
			exists, err := k.StorageMap.Has(ctx, key)
			if err != nil {
				return nil, err
			}

			// Only try to delete if it exists
			if exists {
				if err := k.StorageMap.Remove(ctx, key); err != nil {
					return nil, err
				}
				deletedIndexes = append(deletedIndexes, index)
			}
		}
	} else {
		// OPTION 2: Delete by prefix with optional filter
		// We need to iterate through all entries for this owner and match by prefix
		iterator, err := k.StorageMap.Iterate(ctx, collections.NewPrefixedPairRange[string, string](msg.Owner))
		if err != nil {
			return nil, err
		}
		defer iterator.Close()

		// Collect keys to delete (we collect first to avoid iterator invalidation)
		var keysToDelete []collections.Pair[string, string]

		for ; iterator.Valid(); iterator.Next() {
			kv, err := iterator.KeyValue()
			if err != nil {
				return nil, err
			}
			key := kv.Key
			value := kv.Value

			// Check if index starts with the prefix
			if !strings.HasPrefix(value.Index, msg.IndexPrefix) {
				continue
			}

			// Apply optional filter if provided
			if hasFilter {
				// Wrap the data in an array to use GJSON's query functionality
				// This allows us to use all GJSON query operators: ==, !=, <, <=, >, >=, %, !%
				wrappedData := "[" + value.Data + "]"

				// Apply the filter as a GJSON array query
				// If the filter matches, it returns the item; if not, it returns empty array
				result := gjson.Get(wrappedData, "#("+msg.Filter+")")

				// Skip if no match (empty result)
				if !result.Exists() || len(result.Array()) == 0 {
					continue
				}
			}

			// Mark for deletion
			keysToDelete = append(keysToDelete, key)
			deletedIndexes = append(deletedIndexes, value.Index)
		}

		// Now delete all marked entries
		for _, key := range keysToDelete {
			if err := k.StorageMap.Remove(ctx, key); err != nil {
				return nil, err
			}
		}
	}

	if len(deletedIndexes) == 0 {
		return nil, errorsmod.Wrap(sdkerrors.ErrNotFound, "no entries were deleted")
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
