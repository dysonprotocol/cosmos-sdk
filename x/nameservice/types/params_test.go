package types

import (
	"testing"
	"time"
)

func TestDefaultParams(t *testing.T) {
	params := DefaultParams()
	
	// Check that all default values are set correctly
	if params.BidTimeout != DefaultBidTimeout {
		t.Errorf("Expected BidTimeout %v, got %v", DefaultBidTimeout, params.BidTimeout)
	}
	
	if params.MintFeePerCoin != DefaultMintFeePerCoin {
		t.Errorf("Expected MintFeePerCoin %s, got %s", DefaultMintFeePerCoin, params.MintFeePerCoin)
	}
	
	// Validate that default params are valid
	if err := params.Validate(); err != nil {
		t.Errorf("Default params should be valid, got error: %v", err)
	}
}

func TestValidateMintFeePerCoin(t *testing.T) {
	tests := []struct {
		name        string
		feeStr      string
		expectError bool
	}{
		// Valid cases
		{"default value", "1.0", false},
		{"zero fee", "0.0", false},
		{"fractional fee", "0.5", false},
		{"large fee", "100.25", false},
		{"very small fee", "0.001", false},
		{"integer value", "1", false},
		{"high precision", "1.123456789", false},
		
		// Invalid cases
		{"negative fee", "-1.0", true},
		{"invalid string", "invalid", true},
		{"not a number", "not_a_number", true},
		{"empty string", "", true},
		{"negative fractional", "-0.5", true},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := validateMintFeePerCoin(tt.feeStr)
			if tt.expectError && err == nil {
				t.Errorf("Expected error for input %q, but got none", tt.feeStr)
			}
			if !tt.expectError && err != nil {
				t.Errorf("Expected no error for input %q, but got: %v", tt.feeStr, err)
			}
		})
	}
}

func TestGetMintFeePerCoinAsDec(t *testing.T) {
	tests := []struct {
		name        string
		feeStr      string
		expectError bool
		expectedDec string
	}{
		{"default value", "1.0", false, "1.000000000000000000"},
		{"zero fee", "0.0", false, "0.000000000000000000"},
		{"fractional fee", "0.5", false, "0.500000000000000000"},
		{"large fee", "100.25", false, "100.250000000000000000"},
		{"invalid string", "invalid", true, ""},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			params := Params{MintFeePerCoin: tt.feeStr}
			dec, err := params.GetMintFeePerCoinAsDec()
			
			if tt.expectError && err == nil {
				t.Errorf("Expected error for input %q, but got none", tt.feeStr)
			}
			if !tt.expectError && err != nil {
				t.Errorf("Expected no error for input %q, but got: %v", tt.feeStr, err)
			}
			if !tt.expectError && dec.String() != tt.expectedDec {
				t.Errorf("Expected decimal %s, got %s", tt.expectedDec, dec.String())
			}
		})
	}
}

func TestParamsValidate(t *testing.T) {
	validParams := DefaultParams()
	
	// Test valid params
	err := validParams.Validate()
	if err != nil {
		t.Errorf("Valid params should not return error: %v", err)
	}
	
	// Test invalid mint fee per coin
	invalidParams := validParams
	invalidParams.MintFeePerCoin = "-1.0"
	err = invalidParams.Validate()
	if err == nil {
		t.Error("Expected error for negative mint fee per coin")
	}
	
	// Test invalid mint fee per coin (non-numeric)
	invalidParams2 := validParams
	invalidParams2.MintFeePerCoin = "invalid"
	err = invalidParams2.Validate()
	if err == nil {
		t.Error("Expected error for non-numeric mint fee per coin")
	}
}

func TestNewParams(t *testing.T) {
	bidTimeout := time.Hour * 24
	allowedDenoms := []string{"udys", "stake"}
	rejectBidFee := "0.05"
	minBidIncrease := "0.02"
	mintFee := "2.0"
	
	params := NewParams(bidTimeout, allowedDenoms, rejectBidFee, minBidIncrease, mintFee)
	
	if params.BidTimeout != bidTimeout {
		t.Errorf("Expected BidTimeout %v, got %v", bidTimeout, params.BidTimeout)
	}
	if params.MintFeePerCoin != mintFee {
		t.Errorf("Expected MintFeePerCoin %s, got %s", mintFee, params.MintFeePerCoin)
	}
	if params.RejectBidValuationFeePercent != rejectBidFee {
		t.Errorf("Expected RejectBidValuationFeePercent %s, got %s", rejectBidFee, params.RejectBidValuationFeePercent)
	}
	if params.MinimumBidPercentIncrease != minBidIncrease {
		t.Errorf("Expected MinimumBidPercentIncrease %s, got %s", minBidIncrease, params.MinimumBidPercentIncrease)
	}
	if len(params.AllowedDenoms) != len(allowedDenoms) {
		t.Errorf("Expected AllowedDenoms length %d, got %d", len(allowedDenoms), len(params.AllowedDenoms))
	}
}
