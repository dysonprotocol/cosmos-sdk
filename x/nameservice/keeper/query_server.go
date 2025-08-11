package keeper

import (
	"context"

	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"

	"cosmossdk.io/collections"
	"dysonprotocol.com/x/nameservice/types"
	sdk "github.com/cosmos/cosmos-sdk/types"
	"github.com/cosmos/cosmos-sdk/types/query"
)

// Ensure Keeper implements QueryServer interface
var _ types.QueryServer = Keeper{}

// ComputeHash implements the Query/ComputeHash gRPC method
func (k Keeper) ComputeHash(c context.Context, req *types.ComputeHashRequest) (*types.ComputeHashResponse, error) {
	if req.Name == "" {
		return nil, status.Error(codes.InvalidArgument, "name cannot be empty")
	}

	if req.Salt == "" {
		return nil, status.Error(codes.InvalidArgument, "salt cannot be empty")
	}

	if req.Committer == "" {
		return nil, status.Error(codes.InvalidArgument, "committer address cannot be empty")
	}

	// Use the common hash function
	hexhash := k.ComputeNameRegistrationHash(req.Name, req.Committer, req.Salt)

	return &types.ComputeHashResponse{
		HexHash: hexhash,
	}, nil
}

// ResolveName implements the Query/ResolveName gRPC method
func (k Keeper) ResolveName(c context.Context, req *types.QueryResolveNameRequest) (*types.QueryResolveNameResponse, error) {
	if req == nil {
		return nil, status.Error(codes.InvalidArgument, "invalid request")
	}

	if req.NameOrAddress == "" {
		return nil, status.Error(codes.InvalidArgument, "name_or_address cannot be empty")
	}

	// Use the ResolveNameOrAddress method from the keeper
	address, err := k.ResolveNameOrAddress(c, req.NameOrAddress)
	if err != nil {
		return nil, status.Error(codes.InvalidArgument, err.Error())
	}

	return &types.QueryResolveNameResponse{
		Address: address,
	}, nil
}

// Params implements the Query/Params gRPC method
func (k Keeper) Params(c context.Context, req *types.QueryParamsRequest) (*types.QueryParamsResponse, error) {
	if req == nil {
		return nil, status.Error(codes.InvalidArgument, "invalid request")
	}

	params := k.GetParams(c)

	return &types.QueryParamsResponse{Params: params}, nil
}

// QueryNamesByDestination implements the Query/QueryNamesByDestination gRPC method
func (k Keeper) QueryNamesByDestination(c context.Context, req *types.QueryNamesByDestinationRequest) (*types.QueryNamesByDestinationResponse, error) {
	if req == nil {
		return nil, status.Error(codes.InvalidArgument, "invalid request")
	}

	if req.Destination == "" {
		return nil, status.Error(codes.InvalidArgument, "destination address cannot be empty")
	}

	// Validate the destination address
	_, err := sdk.AccAddressFromBech32(req.Destination)
	if err != nil {
		return nil, status.Error(codes.InvalidArgument, "invalid destination address format")
	}

	// Fetch the name strings for each matching entry
	nameResults, pageRes, err := query.CollectionPaginate(
		c,
		k.nameDestinations,
		req.Pagination,
		func(key collections.Pair[string, string], value string) (string, error) {
			// Return the source name (which is the value)
			return value, nil
		},
		query.WithCollectionPaginationPairPrefix[string, string](req.Destination),
	)
	if err != nil {
		return nil, status.Error(codes.Internal, err.Error())
	}

	return &types.QueryNamesByDestinationResponse{
		Names:      nameResults,
		Pagination: pageRes,
	}, nil
}

// QueryNFTClassesByName implements the Query/QueryNFTClassesByName gRPC method
func (k Keeper) QueryNFTClassesByName(c context.Context, req *types.QueryNFTClassesByNameRequest) (*types.QueryNFTClassesByNameResponse, error) {
	if req == nil {
		return nil, status.Error(codes.InvalidArgument, "invalid request")
	}

	if req.Name == "" {
		return nil, status.Error(codes.InvalidArgument, "name cannot be empty")
	}

	// Ensure the provided name exists as a Name NFT root
	// This verifies existence; does not require .dys suffix explicitly per spec
	if !k.nftKeeper.HasNFT(c, NamesClassID, req.Name) {
		return nil, status.Error(codes.NotFound, "root name NFT not found")
	}

	// Iterate the reverse index by root name prefix and collect class IDs
	classIDs, pageRes, err := query.CollectionPaginate(
		c,
		k.classesByRootName,
		req.Pagination,
		func(key collections.Pair[string, string], value string) (string, error) {
			return value, nil
		},
		query.WithCollectionPaginationPairPrefix[string, string](req.Name),
	)
	if err != nil {
		return nil, status.Error(codes.Internal, err.Error())
	}

	return &types.QueryNFTClassesByNameResponse{
		ClassIds:   classIDs,
		Pagination: pageRes,
	}, nil
}
