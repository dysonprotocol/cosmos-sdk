package types

import (
	"fmt"
)

// DefaultGenesis returns default genesis state as raw bytes for the nameservice module
func DefaultGenesis() *GenesisState {
	return &GenesisState{
		Params:      DefaultParams(),
		Commitments: []Commitment{},
	}
}

// ValidateGenesis validates the provided genesis state to ensure the
// expected invariants holds.
func ValidateGenesis(data *GenesisState) error {
	// Validate params
	if err := data.Params.Validate(); err != nil {
		return err
	}

	// Validate commitments
	commitmentMap := make(map[string]bool)
	for _, commitment := range data.Commitments {
		if commitment.Hexhash == "" {
			return fmt.Errorf("empty commitment hash")
		}
		if commitmentMap[commitment.Hexhash] {
			return fmt.Errorf("duplicate commitment found: %s", commitment.Hexhash)
		}
		commitmentMap[commitment.Hexhash] = true
	}

	return nil
}
