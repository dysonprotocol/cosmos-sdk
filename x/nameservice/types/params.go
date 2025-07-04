package types

import (
	"fmt"
	"time"

	"cosmossdk.io/math"
)

// DefaultBidTimeout is the default value for the bid timeout parameter
const DefaultBidTimeout = time.Hour * 24 * 7 // 7 days
// MinBidTimeout is the minimum allowed value for the bid timeout parameter
const MinBidTimeout = 0 // 0 seconds
// MaxBidTimeout is the maximum allowed value for the bid timeout parameter
const MaxBidTimeout = time.Hour * 24 * 90 // 90 days

// DefaultAllowedDenoms is the default list of allowed denominations
var DefaultAllowedDenoms = []string{"udys"}

// DefaultRejectBidValuationFeePercent is the default percentage of the valuation to charge as a reject bid valuation fee
var DefaultRejectBidValuationFeePercent = "0.03" // 3%

// DefaultMinimumBidPercentIncrease is the default percentage increase required for a new bid compared to the previous bid
var DefaultMinimumBidPercentIncrease = "0.01" // 1%

// NewParams creates a new Params instance with given values
func NewParams(
	bidTimeout time.Duration,
	allowedDenoms []string,
	rejectBidValuationFeePercent string,
	minimumBidPercentIncrease string,
) Params {
	return Params{
		BidTimeout:                   bidTimeout,
		AllowedDenoms:                allowedDenoms,
		RejectBidValuationFeePercent: rejectBidValuationFeePercent,
		MinimumBidPercentIncrease:    minimumBidPercentIncrease,
	}
}

// DefaultParams returns a default set of parameters
func DefaultParams() Params {
	return NewParams(
		DefaultBidTimeout,
		DefaultAllowedDenoms,
		DefaultRejectBidValuationFeePercent,
		DefaultMinimumBidPercentIncrease,
	)
}

// Validate validates the params
func (p Params) Validate() error {
	if err := validateBidTimeout(p.BidTimeout); err != nil {
		return err
	}

	if err := validateAllowedDenoms(p.AllowedDenoms); err != nil {
		return err
	}

	if err := validateRejectBidValuationFeePercent(p.RejectBidValuationFeePercent); err != nil {
		return err
	}

	if err := validateMinimumBidPercentIncrease(p.MinimumBidPercentIncrease); err != nil {
		return err
	}

	return nil
}

func validateBidTimeout(timeout time.Duration) error {
	if timeout < MinBidTimeout {
		return fmt.Errorf("bid timeout must be at least %v, got: %v", MinBidTimeout, timeout)
	}

	if timeout > MaxBidTimeout {
		return fmt.Errorf("bid timeout must be at most %v, got: %v", MaxBidTimeout, timeout)
	}

	return nil
}

func validateAllowedDenoms(denoms []string) error {
	// Check if the denoms list is empty
	if len(denoms) == 0 {
		return fmt.Errorf("allowed denoms list cannot be empty, it must contain at least 'udys'")
	}

	// Check if "udys" is in the allowed denoms list
	dysDenomExists := false
	for _, denom := range denoms {
		// Check that no denom is empty
		if denom == "" {
			return fmt.Errorf("denom cannot be empty")
		}

		if denom == "udys" {
			dysDenomExists = true
		}
	}

	// Ensure "udys" is in the list
	if !dysDenomExists {
		return fmt.Errorf("allowed denoms list must contain 'udys'")
	}

	return nil
}

func validateRejectBidValuationFeePercent(feePercentStr string) error {
	feePercent, err := math.LegacyNewDecFromStr(feePercentStr)
	if err != nil {
		return fmt.Errorf("invalid reject bid valuation fee percent: %s", err)
	}

	// Fee percent must be between 0 and 1 (0% to 100%)
	if feePercent.IsNegative() {
		return fmt.Errorf("reject bid valuation fee percent cannot be negative: %s", feePercentStr)
	}

	if feePercent.GT(math.LegacyOneDec()) {
		return fmt.Errorf("reject bid valuation fee percent cannot be greater than 1 (100%%): %s", feePercentStr)
	}

	return nil
}

func validateMinimumBidPercentIncrease(increasePercentStr string) error {
	increasePercent, err := math.LegacyNewDecFromStr(increasePercentStr)
	if err != nil {
		return fmt.Errorf("invalid minimum bid percent increase: %s", err)
	}

	if increasePercent.IsNegative() {
		return fmt.Errorf("minimum bid percent increase must be non-negative: %s", increasePercent)
	}

	// Percentage can be any non-negative value
	// Upper bound not necessary but might be considered if needed
	return nil
}

// GetRejectBidValuationFeePercentAsDec returns the reject bid valuation fee percent as a math.Dec
func (p Params) GetRejectBidValuationFeePercentAsDec() (math.LegacyDec, error) {
	return math.LegacyNewDecFromStr(p.RejectBidValuationFeePercent)
}

// SetRejectBidValuationFeePercentFromDec sets the reject bid valuation fee percent from a math.Dec
func (p *Params) SetRejectBidValuationFeePercentFromDec(feePercent math.LegacyDec) {
	p.RejectBidValuationFeePercent = feePercent.String()
}

// GetMinimumBidPercentIncreaseAsDec returns the minimum bid percent increase as a math.Dec
func (p Params) GetMinimumBidPercentIncreaseAsDec() (math.LegacyDec, error) {
	return math.LegacyNewDecFromStr(p.MinimumBidPercentIncrease)
}

// SetMinimumBidPercentIncreaseFromDec sets the minimum bid percent increase from a math.Dec
func (p *Params) SetMinimumBidPercentIncreaseFromDec(increasePercent math.LegacyDec) {
	p.MinimumBidPercentIncrease = increasePercent.String()
}
