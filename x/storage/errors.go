package storage

import (
	"cosmossdk.io/errors"
	"cosmossdk.io/math"
)

var (
	// ErrInvalidOwner is returned when the owner address is invalid
	ErrInvalidOwner = errors.Register("storage", 1, "invalid owner address")

	// ErrEmptyIndex is returned when the index is empty
	ErrEmptyIndex = errors.Register("storage", 2, "index cannot be empty")

	// ErrInsufficientStake is returned when the account doesn't have sufficient delegated stake for storage
	ErrInsufficientStake = errors.Register("storage", 3, "insufficient stake for storage operation")
)

// NewInsufficientStakeError creates a detailed insufficient stake error message
func NewInsufficientStakeError(have, need math.Int, bytes uint64) error {
	return errors.Wrapf(ErrInsufficientStake,
		"insufficient stake: have %s udys, need %s udys for %d bytes of storage",
		have.String(), need.String(), bytes)
}
