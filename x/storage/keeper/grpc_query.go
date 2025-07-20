package keeper

import (
	"context"
	"strings"

	"cosmossdk.io/collections"
	"cosmossdk.io/errors"
	storagetypes "dysonprotocol.com/x/storage/types"
	sdk "github.com/cosmos/cosmos-sdk/types"
	"github.com/cosmos/cosmos-sdk/types/query"
	"github.com/tidwall/gjson"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

// Ensure Keeper implements the gRPC interface
var _ storagetypes.QueryServer = Keeper{}

func (k Keeper) StorageGet(ctx context.Context, req *storagetypes.QueryStorageGetRequest) (*storagetypes.QueryStorageGetResponse, error) {
	// Validate the owner address is properly formatted
	if _, err := sdk.AccAddressFromBech32(req.Owner); err != nil {
		return nil, status.Errorf(codes.InvalidArgument, "invalid owner address: %v", err)
	}

	if len(req.Extract) > 100 {
		return nil, status.Errorf(codes.InvalidArgument, "extract path too long: max 100 characters")
	}

	// Create the combined key
	combinedKey := req.Owner + "/" + req.Index
	record, err := k.StorageMap.Get(ctx, combinedKey)
	if err == nil {
		// Apply optional GJSON extract if provided
		if req.Extract != "" {
			res := gjson.Get(record.Data, req.Extract)
			if res.Exists() {
				record.Data = res.Raw
			} else {
				// If extraction path not found, return not found error for clarity
				return nil, status.Errorf(codes.NotFound, "extract path '%s' not found in storage entry", req.Extract)
			}
		}
		return &storagetypes.QueryStorageGetResponse{
			Entry: &record, // single struct
		}, nil
	}
	if errors.IsOf(err, collections.ErrNotFound) {
		return nil, status.Errorf(codes.NotFound, "storage entry for (owner=%s,index=%s) doesn't exist", req.Owner, req.Index)
	}
	return nil, status.Error(codes.Internal, err.Error())
}

func (k Keeper) StorageList(ctx context.Context, req *storagetypes.QueryStorageListRequest) (*storagetypes.QueryStorageListResponse, error) {
	// Validate the owner address is properly formatted
	sdkCtx := sdk.UnwrapSDKContext(ctx)
	k.Logger(sdkCtx).Info("StorageList", "req", req)
	if _, err := sdk.AccAddressFromBech32(req.Owner); err != nil {
		return nil, status.Errorf(codes.InvalidArgument, "invalid owner address: %v", err)
	}

	if len(req.Filter) > 100 {
		return nil, status.Errorf(codes.InvalidArgument, "filter path too long: max 100 characters")
	}
	if len(req.Extract) > 100 {
		return nil, status.Errorf(codes.InvalidArgument, "extract path too long: max 100 characters")
	}

	// Initialize pagination defaults
	if req.Pagination == nil {
		req.Pagination = &query.PageRequest{}
	}
	if req.Pagination.Limit == 0 {
		req.Pagination.Limit = 100
	}

	offset := req.Pagination.Offset
	pagKey := req.Pagination.Key
	limit := req.Pagination.Limit
	countTotal := req.Pagination.CountTotal
	reverse := req.Pagination.Reverse

	if offset > 0 && len(pagKey) > 0 {
		return nil, status.Errorf(codes.InvalidArgument, "invalid request, either offset or key is expected, got both")
	}

	ownerPrefix := req.Owner + "/"
	fullPrefix := ownerPrefix + req.IndexPrefix
	endKey := fullPrefix + "\xff"

	// Create range for iteration
	var rng collections.Ranger[string]

	if len(pagKey) > 0 {
		// When pagination key is provided, start FROM that key (the pagination key represents the next item to return)
		// The pagination key should be the raw storage index key
		startKey := ownerPrefix + string(pagKey)

		if reverse {
			// For reverse iteration, we want to start from the pagination key and go backwards
			// The range should be from fullPrefix up to (and including) the startKey
			rng = (&collections.Range[string]{}).StartInclusive(fullPrefix).EndInclusive(startKey).Descending()
		} else {
			// For forward iteration, start from the pagination key (inclusive) and go forward
			rng = (&collections.Range[string]{}).StartInclusive(startKey).EndInclusive(endKey)
		}
	} else {
		// No pagination key provided - start from the beginning/end
		if reverse {
			rng = (&collections.Range[string]{}).StartInclusive(fullPrefix).EndInclusive(endKey).Descending()
		} else {
			rng = (&collections.Range[string]{}).StartInclusive(fullPrefix).EndInclusive(endKey)
		}
	}

	iter, err := k.StorageMap.Iterate(ctx, rng)
	if err != nil {
		return nil, status.Error(codes.Internal, err.Error())
	}
	defer iter.Close()

	// Define predicate and transform functions
	predicateFunc := func(key string, val storagetypes.Storage) (bool, error) {
		k.Logger(sdkCtx).Info("Filter", "req.Filter", req.Filter)
		if req.Filter == "" {
			k.Logger(sdkCtx).Info("No Filter", "req.Filter", req.Filter)
			return true, nil
		}
		wrappedData := "[" + val.Data + "]"
		result := gjson.Get(wrappedData, "#("+req.Filter+")")
		k.Logger(sdkCtx).Info("Result", "result", result)
		return result.Exists() && len(result.Array()) > 0, nil
	}

	transformFunc := func(key string, val storagetypes.Storage) (*storagetypes.Storage, error) {
		k.Logger(sdkCtx).Info("TransformFunc", "val", val)

		if req.Extract != "" {
			k.Logger(sdkCtx).Info("Extract", "req.Extract", req.Extract)
			res := gjson.Get(val.Data, req.Extract)
			if res.Exists() {
				val.Data = res.Raw
			} else {
				k.Logger(sdkCtx).Info("Extract", "req.Extract", req.Extract)
				val.Data = ""
			}
		}
		// create a copy to return its address safely
		return &val, nil
	}

	var entries []*storagetypes.Storage
	var skipped uint64
	var collected uint64
	var total uint64
	var nextKey []byte

	for iter.Valid() {
		key, err := iter.Key()
		if err != nil {
			return nil, status.Error(codes.Internal, err.Error())
		}
		val, err := iter.Value()
		if err != nil {
			return nil, status.Error(codes.Internal, err.Error())
		}

		include, err := predicateFunc(key, val)
		if err != nil {
			return nil, status.Error(codes.Internal, err.Error())
		}
		if !include {
			iter.Next()
			continue
		}

		total++

		if len(pagKey) == 0 && skipped < offset {
			skipped++
			iter.Next()
			continue
		}

		if collected < limit {
			transformed, err := transformFunc(key, val)
			if err != nil {
				return nil, status.Error(codes.Internal, err.Error())
			}
			entries = append(entries, transformed)
			collected++
			iter.Next()
			continue
		}

		if collected >= uint64(limit) {
			// We've reached the limit, set next key for pagination
			trimmed := strings.TrimPrefix(key, ownerPrefix)
			nextKey = []byte(trimmed)
			break
		}

		iter.Next()

		if !countTotal || len(pagKey) > 0 {
			break
		}
	}

	pageRes := &query.PageResponse{NextKey: nextKey}
	if countTotal && len(pagKey) == 0 {
		pageRes.Total = total
	}

	return &storagetypes.QueryStorageListResponse{
		Entries:    entries,
		Pagination: pageRes,
	}, nil
}
