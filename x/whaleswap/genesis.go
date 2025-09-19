package whaleswap

import (
	"dysonprotocol.com/x/whaleswap/types"
)

// NewGenesisState creates a new genesis state with default values.
func NewGenesisState() *types.GenesisState {
	return &types.GenesisState{
		Params: types.DefaultParams(),
	}
}

// DefaultGenesis returns default genesis state for the whaleswap module
func DefaultGenesis() *types.GenesisState { return NewGenesisState() }

// ValidateGenesisState performs basic genesis validation.
func ValidateGenesisState(s types.GenesisState) error {
	return s.Params.Validate()
}
