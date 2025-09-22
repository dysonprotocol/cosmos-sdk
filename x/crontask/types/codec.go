package types

import (
	"github.com/cosmos/cosmos-sdk/codec"
	cdctypes "github.com/cosmos/cosmos-sdk/codec/types"
	sdk "github.com/cosmos/cosmos-sdk/types"
	"github.com/cosmos/cosmos-sdk/types/msgservice"
	gogoprotoany "github.com/cosmos/gogoproto/types/any"
)

// RegisterLegacyAminoCodec registers the crontask module types on the LegacyAmino codec
func RegisterLegacyAminoCodec(cdc *codec.LegacyAmino) {
	// No amino registrations needed for this module
}

// RegisterInterfaces registers the crontask module's interface types
func RegisterInterfaces(registry cdctypes.InterfaceRegistry) {
	// Register message implementations
	registry.RegisterImplementations((*sdk.Msg)(nil),
		&MsgCreateTask{},
		&MsgDeleteTask{},
		&MsgUpdateParams{},
		&MsgCreateSubscription{},
		&MsgDeleteSubscription{},
		&MsgRenewSubscription{},
	)

	// Register UnpackInterfacesMessage implementations
	registry.RegisterImplementations(
		(*gogoprotoany.UnpackInterfacesMessage)(nil),
		&Task{},
		&MsgCreateTask{},
	)

	msgservice.RegisterMsgServiceDesc(registry, &_Msg_serviceDesc)
}

func RegisterCodec(cdc *codec.LegacyAmino) {
	// No codec registrations needed for this module
}
