package types

import (
	"fmt"

	"cosmossdk.io/math"
	sdk "github.com/cosmos/cosmos-sdk/types"
)

// Defaults
var DefaultPfandPerOffer = sdk.NewCoin("whaleswap.dys/pfand", math.NewInt(0))

func NewParams(pfandPerOffer sdk.Coin, valuationFeePct, minBidPctIncrease string) Params {
	return Params{
		PfandPerOffer:             pfandPerOffer,
		ValuationFeePct:           valuationFeePct,
		MinimumBidPercentIncrease: minBidPctIncrease,
	}
}

func DefaultParams() Params {
	return NewParams(DefaultPfandPerOffer, "0", "0")
}

func (p Params) Validate() error {
	if !p.PfandPerOffer.Amount.IsZero() && p.PfandPerOffer.Denom == "" {
		return fmt.Errorf("pfand_per_offer denom must be set when amount > 0")
	}
	if p.ValuationFeePct != "" {
		if _, err := math.LegacyNewDecFromStr(p.ValuationFeePct); err != nil {
			return fmt.Errorf("invalid valuation_fee_pct: %v", err)
		}
	}
	if p.MinimumBidPercentIncrease != "" {
		if _, err := math.LegacyNewDecFromStr(p.MinimumBidPercentIncrease); err != nil {
			return fmt.Errorf("invalid minimum_bid_percent_increase: %v", err)
		}
	}
	return nil
}
