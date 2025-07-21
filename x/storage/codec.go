package storage

import (
	"dysonprotocol.com/x/storage/types"
	codectypes "github.com/cosmos/cosmos-sdk/codec/types"
	sdk "github.com/cosmos/cosmos-sdk/types"
	"github.com/cosmos/cosmos-sdk/types/msgservice"
)

// RegisterLegacyAminoCodec registers all the necessary group module concrete
// types and interfaces with the provided codec reference.
// These types are used for Amino JSON serialization.
func RegisterLegacyAminoCodec(registrar interface{}) {
}

// RegisterInterfaces registers the interfaces types with the interface registry.
func RegisterInterfaces(registrar codectypes.InterfaceRegistry) {
	registrar.RegisterImplementations((*sdk.Msg)(nil),
		&types.MsgStorageSet{},
		&types.MsgStorageDelete{},
		&types.MsgUpdateParams{},
	)

	msgservice.RegisterMsgServiceDesc(registrar, &types.Msg_serviceDesc)
}
