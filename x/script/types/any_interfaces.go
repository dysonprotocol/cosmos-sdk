package types

import (
	sdk "github.com/cosmos/cosmos-sdk/types"
	gogoprotoany "github.com/cosmos/gogoproto/types/any"
)

// Ensure our types implement the UnpackInterfacesMessage interface
var (
	_ gogoprotoany.UnpackInterfacesMessage = (*MsgExec)(nil)
	_ gogoprotoany.UnpackInterfacesMessage = (*MsgExecResponse)(nil)
	_ gogoprotoany.UnpackInterfacesMessage = (*RunScript)(nil)
	_ gogoprotoany.UnpackInterfacesMessage = (*ResponseRunScript)(nil)
)

// UnpackInterfaces implements the UnpackInterfacesMessage.UnpackInterfaces method
func (msg *MsgExec) UnpackInterfaces(unpacker gogoprotoany.AnyUnpacker) error {
	for _, x := range msg.AttachedMessages {
		var m sdk.Msg
		err := unpacker.UnpackAny(x, &m)
		if err != nil {
			return err
		}
	}
	return nil
}

// UnpackInterfaces implements the UnpackInterfacesMessage.UnpackInterfaces method
func (msg *MsgExecResponse) UnpackInterfaces(unpacker gogoprotoany.AnyUnpacker) error {
	for _, x := range msg.AttachedMessageResults {
		var m sdk.Msg
		err := unpacker.UnpackAny(x, &m)
		if err != nil {
			return err
		}
	}
	return nil
}

func (msg *RunScript) UnpackInterfaces(unpacker gogoprotoany.AnyUnpacker) error {
	for _, x := range msg.AttachedMessages {
		var m sdk.Msg
		err := unpacker.UnpackAny(x, &m)
		if err != nil {
			return err
		}
	}
	return nil
}

func (msg *ResponseRunScript) UnpackInterfaces(unpacker gogoprotoany.AnyUnpacker) error {
	for _, x := range msg.AttachedMessageResults {
		var m sdk.Msg
		err := unpacker.UnpackAny(x, &m)
		if err != nil {
			return err
		}
	}
	return nil
}
