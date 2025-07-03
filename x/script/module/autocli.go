package module

import (
	autocliv1 "cosmossdk.io/api/cosmos/autocli/v1"
	scriptv1 "dysonprotocol.com/api/script/types"
)

// AutoCLIOptions implements the autocli.HasAutoCLIConfig interface.
func (am AppModule) AutoCLIOptions() *autocliv1.ModuleOptions {
	return &autocliv1.ModuleOptions{
		// Query commands are handled by custom implementation in GetQueryCmd()
		Query: &autocliv1.ServiceCommandDescriptor{
			Service:              scriptv1.Query_ServiceDesc.ServiceName,
			EnhanceCustomCommand: true,
		},
		Tx: &autocliv1.ServiceCommandDescriptor{
			Service:              scriptv1.Msg_ServiceDesc.ServiceName,
			EnhanceCustomCommand: false,
		},
	}
}
