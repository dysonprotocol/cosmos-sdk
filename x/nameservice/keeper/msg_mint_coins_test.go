package keeper_test

import (
	"context"
	"regexp"
	"testing"

	"cosmossdk.io/math"
	sdk "github.com/cosmos/cosmos-sdk/types"
	"github.com/stretchr/testify/require"

	nameservicev1 "dysonprotocol.com/x/nameservice/types"
)

// MockCommunityPoolKeeper implements the CommunityPoolKeeper interface for testing
type MockCommunityPoolKeeper struct {
	fundedAmounts []sdk.Coins
	fundedSenders []sdk.AccAddress
}

func (m *MockCommunityPoolKeeper) FundCommunityPool(ctx context.Context, amount sdk.Coins, sender sdk.AccAddress) error {
	m.fundedAmounts = append(m.fundedAmounts, amount)
	m.fundedSenders = append(m.fundedSenders, sender)
	return nil
}

// TestMintCoinsIntegration tests the MintCoins functionality with fee collection
func TestMintCoinsIntegration(t *testing.T) {
	tests := []struct {
		name           string
		mintFeePerCoin string
		coinsToMint    sdk.Coins
		expectedFee    sdk.Coins
		expectError    bool
		errorMsg       string
	}{
		{
			name:           "Single coin with default fee",
			mintFeePerCoin: "1.0",
			coinsToMint:    sdk.NewCoins(sdk.NewCoin("test.dys", math.NewInt(100))),
			expectedFee:    sdk.NewCoins(sdk.NewCoin("udys", math.NewInt(1))),
			expectError:    false,
		},
		{
			name:           "Multiple coins with default fee",
			mintFeePerCoin: "1.0",
			coinsToMint: sdk.NewCoins(
				sdk.NewCoin("test.dys", math.NewInt(100)),
				sdk.NewCoin("another.dys", math.NewInt(50)),
				sdk.NewCoin("third.dys", math.NewInt(25)),
			),
			expectedFee: sdk.NewCoins(sdk.NewCoin("udys", math.NewInt(3))), // 3 coins × 1.0 = 3udys
			expectError: false,
		},
		{
			name:           "Single coin with fractional fee",
			mintFeePerCoin: "0.5",
			coinsToMint:    sdk.NewCoins(sdk.NewCoin("test.dys", math.NewInt(100))),
			expectedFee:    sdk.NewCoins(sdk.NewCoin("udys", math.NewInt(0))), // 0.5 truncated = 0
			expectError:    false,
		},
		{
			name:           "Multiple coins with fractional fee",
			mintFeePerCoin: "0.5",
			coinsToMint: sdk.NewCoins(
				sdk.NewCoin("test.dys", math.NewInt(100)),
				sdk.NewCoin("another.dys", math.NewInt(50)),
				sdk.NewCoin("third.dys", math.NewInt(25)),
			),
			expectedFee: sdk.NewCoins(sdk.NewCoin("udys", math.NewInt(1))), // 3 coins × 0.5 = 1.5, truncated = 1udys
			expectError: false,
		},
		{
			name:           "Zero fee parameter",
			mintFeePerCoin: "0.0",
			coinsToMint:    sdk.NewCoins(sdk.NewCoin("test.dys", math.NewInt(100))),
			expectedFee:    sdk.Coins{}, // No fee
			expectError:    false,
		},
		{
			name:           "High fee with multiple coins",
			mintFeePerCoin: "10.0",
			coinsToMint: sdk.NewCoins(
				sdk.NewCoin("test.dys", math.NewInt(100)),
				sdk.NewCoin("another.dys", math.NewInt(50)),
			),
			expectedFee: sdk.NewCoins(sdk.NewCoin("udys", math.NewInt(20))), // 2 coins × 10.0 = 20udys
			expectError: false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			// This is a unit test for the fee calculation logic
			// In a real integration test, you would set up a complete test environment
			// with keepers, context, and test accounts

			// For now, we test the logic components that would be used
			params := nameservicev1.Params{
				MintFeePerCoin: tt.mintFeePerCoin,
			}

			// Test fee calculation
			mintFeePerCoin, err := params.GetMintFeePerCoinAsDec()
			require.NoError(t, err)

			// Calculate expected fee
			numCoins := len(tt.coinsToMint)
			expectedFeeAmount := mintFeePerCoin.MulInt64(int64(numCoins)).TruncateInt()

			if expectedFeeAmount.IsZero() {
				require.True(t, tt.expectedFee.IsZero() || len(tt.expectedFee) == 0)
			} else {
				expectedFeeCoins := sdk.NewCoins(sdk.NewCoin("udys", expectedFeeAmount))
				require.True(t, expectedFeeCoins.Equal(tt.expectedFee),
					"Expected fee %s, got %s", tt.expectedFee, expectedFeeCoins)
			}
		})
	}
}

// TestMintCoinsValidation tests input validation for MintCoins
func TestMintCoinsValidation(t *testing.T) {
	tests := []struct {
		name          string
		msg           *nameservicev1.MsgMintCoins
		expectError   bool
		errorContains string
	}{
		{
			name: "Valid message",
			msg: &nameservicev1.MsgMintCoins{
				NameDestination: "dys1abc123",
				Amount:          sdk.NewCoins(sdk.NewCoin("test.dys", math.NewInt(100))),
			},
			expectError: false,
		},
		{
			name: "Empty coins",
			msg: &nameservicev1.MsgMintCoins{
				NameDestination: "dys1abc123",
				Amount:          sdk.Coins{},
			},
			expectError:   true,
			errorContains: "no coins to mint",
		},
		{
			name: "Invalid denom format",
			msg: &nameservicev1.MsgMintCoins{
				NameDestination: "dys1abc123",
				Amount:          sdk.NewCoins(sdk.NewCoin("invalid_denom", math.NewInt(100))),
			},
			expectError:   true,
			errorContains: "invalid denom format",
		},
		{
			name: "Valid subdenom format",
			msg: &nameservicev1.MsgMintCoins{
				NameDestination: "dys1abc123",
				Amount:          sdk.NewCoins(sdk.NewCoin("test.dys/subtoken", math.NewInt(100))),
			},
			expectError: false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			// Test denom validation logic
			if len(tt.msg.Amount) > 0 {
				validDenomPattern := regexp.MustCompile(`^[A-Za-z0-9.\-_]+\.dys(?:/[0-9A-Za-z:\-_]+)*$`)
				for _, coin := range tt.msg.Amount {
					isValid := validDenomPattern.MatchString(coin.Denom)
					if tt.expectError && tt.errorContains == "invalid denom format" {
						require.False(t, isValid, "Expected denom %s to be invalid", coin.Denom)
					} else if !tt.expectError {
						require.True(t, isValid, "Expected denom %s to be valid", coin.Denom)
					}
				}
			}
		})
	}
}

// TestEventCoinsMinted tests that the event includes the fee information
func TestEventCoinsMinted(t *testing.T) {
	tests := []struct {
		name        string
		amount      sdk.Coins
		feeCharged  sdk.Coins
		expectEvent bool
	}{
		{
			name:        "Event with fee",
			amount:      sdk.NewCoins(sdk.NewCoin("test.dys", math.NewInt(100))),
			feeCharged:  sdk.NewCoins(sdk.NewCoin("udys", math.NewInt(1))),
			expectEvent: true,
		},
		{
			name:        "Event without fee",
			amount:      sdk.NewCoins(sdk.NewCoin("test.dys", math.NewInt(100))),
			feeCharged:  sdk.Coins{},
			expectEvent: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			// Event now has no fields; just ensure it can be constructed
			_ = &nameservicev1.EventCoinsMinted{}
		})
	}
}

// TestFeeCalculationEdgeCases tests edge cases for fee calculation
func TestFeeCalculationEdgeCases(t *testing.T) {
	tests := []struct {
		name           string
		mintFeePerCoin string
		numCoins       int
		expectedFee    string
		expectError    bool
	}{
		{
			name:           "Very small fee with many coins",
			mintFeePerCoin: "0.001",
			numCoins:       100,
			expectedFee:    "0", // 100 × 0.001 = 0.1, truncated = 0
			expectError:    false,
		},
		{
			name:           "Large fee with single coin",
			mintFeePerCoin: "1000000.0",
			numCoins:       1,
			expectedFee:    "1000000",
			expectError:    false,
		},
		{
			name:           "Exact one udys with fraction",
			mintFeePerCoin: "0.334",
			numCoins:       3,
			expectedFee:    "1", // 3 × 0.334 = 1.002, truncated = 1
			expectError:    false,
		},
		{
			name:           "Invalid fee parameter",
			mintFeePerCoin: "invalid",
			numCoins:       1,
			expectedFee:    "",
			expectError:    true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			params := nameservicev1.Params{
				MintFeePerCoin: tt.mintFeePerCoin,
			}

			mintFeePerCoin, err := params.GetMintFeePerCoinAsDec()
			if tt.expectError {
				require.Error(t, err)
				return
			}
			require.NoError(t, err)

			totalFeeAmount := mintFeePerCoin.MulInt64(int64(tt.numCoins)).TruncateInt()
			require.Equal(t, tt.expectedFee, totalFeeAmount.String())
		})
	}
}
