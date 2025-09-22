package types

import (
	"fmt"

	sdk "github.com/cosmos/cosmos-sdk/types"
	sdkerrors "github.com/cosmos/cosmos-sdk/types/errors"
	"github.com/cosmos/cosmos-sdk/types/tx"
	gogoprotoany "github.com/cosmos/gogoproto/types/any"
)

var (
	_ gogoprotoany.UnpackInterfacesMessage = (*Task)(nil)
	_ gogoprotoany.UnpackInterfacesMessage = (*MsgCreateTask)(nil)
)

// UnpackInterfaces implements the UnpackInterfacesMessage interface for Task
func (t Task) UnpackInterfaces(unpacker gogoprotoany.AnyUnpacker) error {
	for i, anyMsg := range t.Msgs {
		var sdkMsg sdk.Msg
		err := unpacker.UnpackAny(anyMsg, &sdkMsg)
		if err != nil {
			return fmt.Errorf("failed to unpack msg at index %d: %w", i, err)
		}
	}

	return nil
}

// UnpackInterfaces implements the UnpackInterfacesMessage interface for MsgCreateTask
func (msg MsgCreateTask) UnpackInterfaces(unpacker gogoprotoany.AnyUnpacker) error {
	for i, anyMsg := range msg.Msgs {
		var sdkMsg sdk.Msg
		err := unpacker.UnpackAny(anyMsg, &sdkMsg)
		if err != nil {
			return fmt.Errorf("failed to unpack msg at index %d: %w", i, err)
		}
	}

	return nil
}

// GetMessages unpacks the Msgs into sdk.Msg's
func (task Task) GetMessages() ([]sdk.Msg, error) {
	return tx.GetMsgs(task.Msgs, "Task")
}

// GetMessageResults unpacks the MsgResults into sdk.Msg's
func (task Task) GetMessageResults() ([]sdk.Msg, error) {
	if len(task.MsgResults) == 0 {
		return []sdk.Msg{}, nil
	}

	results := make([]sdk.Msg, 0, len(task.MsgResults))
	for i, resultMsg := range task.MsgResults {
		if resultMsg != nil {
			cached := resultMsg.GetCachedValue()
			if cached == nil {
				return nil, fmt.Errorf("result at index %d has nil cached value", i)
			}
			if msg, ok := cached.(sdk.Msg); ok {
				results = append(results, msg)
			}
		}
	}
	return results, nil
}

// SetMessages sets the Msgs field by converting sdk.Msg to Any
func (task *Task) SetMessages(msgs []sdk.Msg) error {
	anys, err := tx.SetMsgs(msgs)
	if err != nil {
		return fmt.Errorf("failed to pack messages: %w", err)
	}
	task.Msgs = anys
	return nil
}

// SetMessageResults sets the MsgResults field by converting sdk.Msg to Any
func (task *Task) SetMessageResults(results []sdk.Msg) error {
	anys, err := tx.SetMsgs(results)
	if err != nil {
		return fmt.Errorf("failed to pack results: %w", err)
	}
	task.MsgResults = anys
	return nil
}

// SetMessages sets the Msgs field by converting sdk.Msg to Any
func (msg *MsgCreateTask) SetMessages(msgs []sdk.Msg) error {
	anys, err := tx.SetMsgs(msgs)
	if err != nil {
		return fmt.Errorf("failed to pack messages: %w", err)
	}
	msg.Msgs = anys
	return nil
}

// GetMessages unpacks the Msgs into sdk.Msg's
func (msg MsgCreateTask) GetMessages() ([]sdk.Msg, error) {
	return tx.GetMsgs(msg.Msgs, "MsgCreateTask")
}

// ValidateBasic for MsgCreateSubscription validates fields
func (m *MsgCreateSubscription) ValidateBasic() error {
	if m.Creator == "" {
		return sdkerrors.ErrInvalidRequest.Wrap("creator is required")
	}
	if m.ScriptAddress == "" {
		return sdkerrors.ErrInvalidRequest.Wrap("script_address is required")
	}
	if m.Function == "" {
		return sdkerrors.ErrInvalidRequest.Wrap("function is required")
	}
	if len(m.EventType) == 0 {
		return sdkerrors.ErrInvalidRequest.Wrap("event_type is required")
	}
	if m.TaskGasLimit == 0 {
		return sdkerrors.ErrInvalidRequest.Wrap("task_gas_limit must be > 0")
	}
	if !m.TaskGasFee.IsPositive() {
		return sdkerrors.ErrInvalidRequest.Wrap("task_gas_fee must be positive")
	}
	if len(m.EventType) > 100 {
		return sdkerrors.ErrInvalidRequest.Wrap("event_type exceeds 100 characters")
	}
	if len(m.Filter) > 100 {
		return sdkerrors.ErrInvalidRequest.Wrap("filter exceeds 100 characters")
	}
	if len(m.ScriptAddress) > 100 {
		return sdkerrors.ErrInvalidRequest.Wrap("script_address exceeds 100 characters")
	}
	if len(m.Function) > 100 {
		return sdkerrors.ErrInvalidRequest.Wrap("function exceeds 100 characters")
	}
	if len(m.Args) > 100 {
		return sdkerrors.ErrInvalidRequest.Wrap("args exceeds 100 characters")
	}
	if len(m.Kwargs) > 100 {
		return sdkerrors.ErrInvalidRequest.Wrap("kwargs exceeds 100 characters")
	}
	return nil
}

// ValidateBasic for MsgDeleteSubscription validates fields
func (m *MsgDeleteSubscription) ValidateBasic() error {
	if m.Creator == "" {
		return sdkerrors.ErrInvalidRequest.Wrap("creator is required")
	}
	return nil
}

// ValidateBasic for MsgRenewSubscription validates fields
func (m *MsgRenewSubscription) ValidateBasic() error {
	if m.Creator == "" {
		return sdkerrors.ErrInvalidRequest.Wrap("creator is required")
	}
	if len(m.NewExpiry) == 0 {
		return sdkerrors.ErrInvalidRequest.Wrap("new_expiry is required")
	}
	if len(m.NewExpiry) > 100 {
		return sdkerrors.ErrInvalidRequest.Wrap("new_expiry exceeds 100 characters")
	}
	return nil
}
