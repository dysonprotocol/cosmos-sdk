package keeper

import (
	"context"

	cosmossdkerrors "cosmossdk.io/errors"
	math "cosmossdk.io/math"
	nameservicev1 "dysonprotocol.com/x/nameservice/types"
	sdk "github.com/cosmos/cosmos-sdk/types"
	sdkerrors "github.com/cosmos/cosmos-sdk/types/errors"
)

// Constants for time calculation
const SecondsInDay = 24 * 60 * 60
const DaysInYear = 365

// Renew implements the MsgServer.Renew method
func (k Keeper) Renew(ctx context.Context, msg *nameservicev1.MsgRenew) (*nameservicev1.MsgRenewResponse, error) {
	sdkCtx := sdk.UnwrapSDKContext(ctx)

	// Validate addresses
	payerAddr, err := sdk.AccAddressFromBech32(msg.Payer)
	if err != nil {
		return nil, cosmossdkerrors.Wrapf(sdkerrors.ErrInvalidAddress, "invalid payer address: %s", msg.Payer)
	}

	// Get the current NFT data
	nftData, err := k.GetNFTData(ctx, msg.NftClassId, msg.NftId)
	if err != nil {
		k.Logger.Error("Renew: Failed to get NFT data",
			"nft_class_id", msg.NftClassId,
			"nft_id", msg.NftId,
			"error", err)
		return nil, cosmossdkerrors.Wrapf(err, "failed to get NFT data for %s", msg.NftId)
	}

	// Validate the valuation from NFT data
	err = k.ValidateValuation(ctx, nftData.Valuation)
	if err != nil {
		return nil, err
	}

	// Get the annual fee percentage from the NFT class metadata
	feePercent, err := k.GetNamesClassAnnualPct(ctx)
	if err != nil {
		k.Logger.Error("Renew: Failed to get annual percentage from class metadata", "error", err)
		return nil, cosmossdkerrors.Wrap(err, "failed to get annual percentage for renewal")
	}

	// Convert the single coin to a DecCoins for precise math operations
	decValuation := sdk.NewDecCoinsFromCoins(nftData.Valuation)

	// Calculate the current time and determine the renewal period start time
	currentTime := sdkCtx.BlockTime()

	startTime := nftData.ValuationExpiry

	// Set new expiry date to exactly 1 year from the start time
	newExpiry := currentTime.AddDate(1, 0, 0)

	// Calculate the exact renewal period in seconds using math.Int for precision
	renewalPeriodSeconds := math.NewInt(newExpiry.Unix() - startTime.Unix())

	// Calculate days as seconds / seconds-per-day
	renewalPeriodDaysInt := renewalPeriodSeconds.Quo(math.NewInt(SecondsInDay))

	// Create a decimal for more precise calculations with any remainder
	secondsRemainder := renewalPeriodSeconds.Mod(math.NewInt(SecondsInDay))

	// Get a precise decimal representation of days including partial days
	renewalPeriodDaysDecimal := math.LegacyNewDecFromInt(renewalPeriodDaysInt)
	if !secondsRemainder.IsZero() {
		fractionOfDay := math.LegacyNewDecFromInt(secondsRemainder).Quo(math.LegacyNewDecFromInt(math.NewInt(SecondsInDay)))
		renewalPeriodDaysDecimal = renewalPeriodDaysDecimal.Add(fractionOfDay)
	}

	// Calculate the proportion of a year (365 days) that we're renewing for
	yearProportion := renewalPeriodDaysDecimal.Quo(math.LegacyNewDecFromInt(math.NewInt(DaysInYear)))

	// Convert to LegacyDec for compatibility with SDK DecCoins methods
	legacyFeePercentDec, err := math.LegacyNewDecFromStr(feePercent)
	if err != nil {
		return nil, cosmossdkerrors.Wrap(err, "failed to convert fee percentage to legacy decimal")
	}

	// Calculate fee by multiplying the valuation by fee percentage and the year proportion
	decFees := decValuation.MulDec(legacyFeePercentDec).MulDec(yearProportion)

	// Convert back to regular Coins for blockchain transactions
	fee, _ := decFees.TruncateDecimal()

	// Charge the fee
	if !fee.IsZero() {
		err = k.communityPoolKeeper.FundCommunityPool(ctx, fee, payerAddr)
		if err != nil {
			return nil, cosmossdkerrors.Wrap(err, "failed to send fee to community pool")
		}
	}

	// Update expiry in NFT data
	nftData.ValuationExpiry = newExpiry

	// Update the NFT data
	if err := k.SetNFTData(ctx, msg.NftClassId, msg.NftId, nftData); err != nil {
		k.Logger.Error("Renew: Failed to set NFT data",
			"nft_class_id", msg.NftClassId,
			"nft_id", msg.NftId,
			"error", err)
		return nil, cosmossdkerrors.Wrapf(err, "failed to update NFT data for %s", msg.NftId)
	}

	// Emit event
	err = sdkCtx.EventManager().EmitTypedEvent(
		&nameservicev1.EventNameRenewed{
			Name:      msg.NftId,
			NewExpiry: newExpiry,
		})
	if err != nil {
		k.Logger.Error("failed to emit name renewed event", "error", err)
		return nil, cosmossdkerrors.Wrap(err, "failed to emit name renewed event")
	}

	return &nameservicev1.MsgRenewResponse{
		Expiry: newExpiry,
	}, nil
}

// GetNamesClassAnnualPct returns the annual percentage fee from the NFT class metadata
func (k Keeper) GetNamesClassAnnualPct(ctx context.Context) (string, error) {
	// Ensure the class exists before trying to access its data
	if !k.nftKeeper.HasClass(ctx, NamesClassID) {
		// Try to create the class if it doesn't exist
		if err := k.EnsureNamesClassExists(ctx); err != nil {
			return "", cosmossdkerrors.Wrap(err, "failed to get nameservice NFT class")
		}

		// Check again after creation
		if !k.nftKeeper.HasClass(ctx, NamesClassID) {
			return "", cosmossdkerrors.Wrap(sdkerrors.ErrNotFound, "nameservice NFT class not found")
		}
	}

	// Extract the NFT class data using the centralized GetNFTClassData method
	nftClassData, err := k.GetNFTClassData(ctx, NamesClassID)
	if err != nil {
		return "", cosmossdkerrors.Wrap(err, "nameservice NFT class data error")
	}

	// If annual_pct is empty, return an error
	if nftClassData.AnnualPct == "" {
		return "0", nil
	}

	// Return the annual percentage from the class data
	return nftClassData.AnnualPct, nil
}
