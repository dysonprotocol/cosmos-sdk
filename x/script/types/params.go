package types

import (
	"fmt"
)

// DefaultMaxRelativeHistoricalBlocks is the default value for the max relative historical blocks parameter
const DefaultMaxRelativeHistoricalBlocks = int64(10)

// MinMaxRelativeHistoricalBlocks is the minimum allowed value for the max relative historical blocks parameter
const MinMaxRelativeHistoricalBlocks = int64(0)

// MaxMaxRelativeHistoricalBlocks is the maximum allowed value for the max relative historical blocks parameter
const MaxMaxRelativeHistoricalBlocks = int64(10000)

// DefaultAbsoluteHistoricalBlockCutoff is the default value for the absolute historical block cutoff parameter
const DefaultAbsoluteHistoricalBlockCutoff = int64(1)

// MinAbsoluteHistoricalBlockCutoff is the minimum allowed value for the absolute historical block cutoff parameter
const MinAbsoluteHistoricalBlockCutoff = int64(1)

// NewParams creates a new Params instance with given values
func NewParams(maxRelativeHistoricalBlocks int64, absoluteHistoricalBlockCutoff int64) Params {
	return Params{
		MaxRelativeHistoricalBlocks:   maxRelativeHistoricalBlocks,
		AbsoluteHistoricalBlockCutoff: absoluteHistoricalBlockCutoff,
	}
}

// DefaultParams returns a default set of parameters
func DefaultParams() Params {
	return NewParams(DefaultMaxRelativeHistoricalBlocks, DefaultAbsoluteHistoricalBlockCutoff)
}

// Validate validates the params
func (p Params) Validate() error {
	if err := validateMaxRelativeHistoricalBlocks(p.MaxRelativeHistoricalBlocks); err != nil {
		return err
	}
	if err := validateAbsoluteHistoricalBlockCutoff(p.AbsoluteHistoricalBlockCutoff); err != nil {
		return err
	}
	return nil
}

func validateMaxRelativeHistoricalBlocks(maxRelativeHistoricalBlocks int64) error {
	if maxRelativeHistoricalBlocks < MinMaxRelativeHistoricalBlocks {
		return fmt.Errorf("max relative historical blocks must be at least %d, got: %d", MinMaxRelativeHistoricalBlocks, maxRelativeHistoricalBlocks)
	}

	if maxRelativeHistoricalBlocks > MaxMaxRelativeHistoricalBlocks {
		return fmt.Errorf("max relative historical blocks must be at most %d, got: %d", MaxMaxRelativeHistoricalBlocks, maxRelativeHistoricalBlocks)
	}

	return nil
}

func validateAbsoluteHistoricalBlockCutoff(absoluteHistoricalBlockCutoff int64) error {
	if absoluteHistoricalBlockCutoff < MinAbsoluteHistoricalBlockCutoff {
		return fmt.Errorf("absolute historical block cutoff must be at least %d, got: %d", MinAbsoluteHistoricalBlockCutoff, absoluteHistoricalBlockCutoff)
	}

	return nil
}
