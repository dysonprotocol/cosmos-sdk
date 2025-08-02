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
	ErrInsufficientStake = errors.Register("storage", 3, "insufficient delegated stake for storage operation")
)

// NewInsufficientStakeError creates a detailed insufficient stake error message
func NewInsufficientStakeError(account string, have, need math.Int, bytes uint64) error {
	ratio := need.Quo(math.NewIntFromUint64(bytes))
	return errors.Wrapf(ErrInsufficientStake,
		"insufficient delegated stake: account [%s] has %s udys staked, need %s udys staked for %d bytes of storage (ratio: %s udys per byte)",
		account, have.String(), need.String(), bytes, ratio.String())
}
