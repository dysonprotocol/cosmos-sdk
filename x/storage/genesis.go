package storage

import (
	"dysonprotocol.com/x/storage/types"
	gogoprotoany "github.com/cosmos/gogoproto/types/any"
)

// NewGenesisState creates a new genesis state with default values.
func NewGenesisState() *types.GenesisState {
	return &types.GenesisState{
		Params:  types.DefaultParams(),
		Entries: []types.Storage{},
	}
}

// DefaultGenesis returns default genesis state for the storage module
func DefaultGenesis() *types.GenesisState {
	return NewGenesisState()
}

// ValidateGenesisState performs basic genesis state validation returning an error upon any failure.
func ValidateGenesisState(s types.GenesisState) error {
	// Validate params
	if err := s.Params.Validate(); err != nil {
		return err
	}

	// Validate entries
	for _, entry := range s.Entries {
		if entry.Index == "" {
			return ErrEmptyIndex
		}
	}
	return nil
}

// UnpackGenesisStateInterfaces implements UnpackInterfacesMessage.UnpackInterfaces
func UnpackGenesisStateInterfaces(s types.GenesisState, unpacker gogoprotoany.AnyUnpacker) error {
	return nil
}
