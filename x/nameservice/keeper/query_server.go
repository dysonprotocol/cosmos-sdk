package keeper

import (
	"context"

	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"

	"dysonprotocol.com/x/nameservice/types"
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
