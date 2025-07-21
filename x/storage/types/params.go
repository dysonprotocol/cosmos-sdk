package types

import (
	"fmt"
)

// DefaultMaxStorageSize is the default maximum storage size in bytes (1KB)
const DefaultMaxStorageSize = uint64(1024) // 1KB

// MinMaxStorageSize is the minimum allowed value for max storage size
const MinMaxStorageSize = uint64(1024) // 1KB

// MaxMaxStorageSize is the maximum allowed value for max storage size
const MaxMaxStorageSize = uint64(100 * 1024 * 1024) // 100MB

// NewParams creates a new Params instance with given values
func NewParams(maxStorageSize uint64) Params {
	return Params{
		MaxStorageSize: maxStorageSize,
	}
}

// DefaultParams returns a default set of parameters
func DefaultParams() Params {
	return NewParams(DefaultMaxStorageSize)
}

// Validate validates the params
func (p Params) Validate() error {
	if err := validateMaxStorageSize(p.MaxStorageSize); err != nil {
		return err
	}
	return nil
}

func validateMaxStorageSize(maxStorageSize uint64) error {
	if maxStorageSize < MinMaxStorageSize {
		return fmt.Errorf("max storage size must be at least %d bytes, got: %d", MinMaxStorageSize, maxStorageSize)
	}

	if maxStorageSize > MaxMaxStorageSize {
		return fmt.Errorf("max storage size must be at most %d bytes, got: %d", MaxMaxStorageSize, maxStorageSize)
	}

	return nil
}
