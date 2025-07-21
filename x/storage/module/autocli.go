package module

import (
	autocliv1 "cosmossdk.io/api/cosmos/autocli/v1"
	storageapiv1 "dysonprotocol.com/api/storage/types"
)

// AutoCLIOptions implements the autocli.HasAutoCLIConfig interface.
func (am AppModule) AutoCLIOptions() *autocliv1.ModuleOptions {
	return &autocliv1.ModuleOptions{
		Query: &autocliv1.ServiceCommandDescriptor{
			Service: storageapiv1.Query_ServiceDesc.ServiceName,
			RpcCommandOptions: []*autocliv1.RpcCommandOptions{
				{
					RpcMethod: "StorageGet",
					Use:       "get <owner> --index <index>",
					Short:     "Query the value of a index in the storage by owner",
					PositionalArgs: []*autocliv1.PositionalArgDescriptor{
						{ProtoField: "owner"},
					},
				},
				{
					RpcMethod: "StorageList",
					Use:       "list <owner> --index-prefix <index_prefix>",
					Short:     "List all the keys in the storage with a given prefix",
					PositionalArgs: []*autocliv1.PositionalArgDescriptor{
						{ProtoField: "owner"},
					},
				},
				{
					RpcMethod: "Params",
					Use:       "params",
					Short:     "Query the storage module parameters",
				},
			},
		},
		Tx: &autocliv1.ServiceCommandDescriptor{
			Service:              storageapiv1.Msg_ServiceDesc.ServiceName,
			EnhanceCustomCommand: true,
			RpcCommandOptions: []*autocliv1.RpcCommandOptions{
				{
					RpcMethod: "StorageSet",
					Skip:      true,
				},
				{
					RpcMethod: "StorageDelete",
					Use:       "delete --indexes <indexes>",
					Short:     "Delete one or more storage entries with the specified indexes",
					Long:      "Delete one or more storage entries with the specified indexes. Only existing entries will be deleted. Returns the count of entries deleted.",
				},
			},
		},
	}
}
