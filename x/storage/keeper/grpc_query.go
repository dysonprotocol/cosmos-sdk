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

	// Create the key directly using strings
	pairKey := collections.Join(req.Owner, req.Index)
	record, err := k.StorageMap.Get(ctx, pairKey)
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
	if _, err := sdk.AccAddressFromBech32(req.Owner); err != nil {
		return nil, status.Errorf(codes.InvalidArgument, "invalid owner address: %v", err)
	}

	if len(req.Filter) > 100 {
		return nil, status.Errorf(codes.InvalidArgument, "filter path too long: max 100 characters")
	}
	if len(req.Extract) > 100 {
		return nil, status.Errorf(codes.InvalidArgument, "extract path too long: max 100 characters")
	}

	// Define a predicate function to filter by index_prefix if provided
	predicateFunc := func(key collections.Pair[string, string], val storagetypes.Storage) (bool, error) {
		// First, index prefix check
		if !strings.HasPrefix(val.Index, req.IndexPrefix) {
			return false, nil
		}
		// Then, optional GJSON filter check
		if req.Filter != "" {
			// Wrap the data in an array to use GJSON's query functionality
			// This allows us to use all GJSON query operators: ==, !=, <, <=, >, >=, %, !%
			wrappedData := "[" + val.Data + "]"

			// Apply the filter as a GJSON array query
			result := gjson.Get(wrappedData, "#("+req.Filter+")")

			// Return true only if there's a match (non-empty result)
			return result.Exists() && len(result.Array()) > 0, nil
		}
		return true, nil
	}

	// Transform function: we produce a pointer to match a repeated `Storage` => []*Storage
	transformFunc := func(key collections.Pair[string, string], val storagetypes.Storage) (*storagetypes.Storage, error) {
		out := val
		if req.Extract != "" {
			res := gjson.Get(val.Data, req.Extract)
			if res.Exists() {
				out.Data = res.Raw
			} else {
				out.Data = ""
			}
		}
		// create a copy to return its address safely
		return &out, nil
	}

	// Now we do store-level filtered pagination in one pass
	results, pageRes, err := query.CollectionFilteredPaginate[
		collections.Pair[string, string], // K
		storagetypes.Storage,             // V
		collections.Map[collections.Pair[string, string], storagetypes.Storage], // C
		*storagetypes.Storage, // T
	](
		ctx,
		k.StorageMap,
		req.Pagination,
		predicateFunc,
		transformFunc,
		query.WithCollectionPaginationPairPrefix[string, string](req.Owner),
	)
	if err != nil && !errors.IsOf(err, collections.ErrInvalidIterator) {
		return nil, status.Error(codes.Internal, err.Error())
	}

	// `results` is a `[]*storagetypes.Storage` directly
	return &storagetypes.QueryStorageListResponse{
		Entries:    results,
		Pagination: pageRes,
	}, nil
}
