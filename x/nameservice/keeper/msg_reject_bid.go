package keeper

import (
	"context"
	"fmt"
	"time"

	cosmossdkerrors "cosmossdk.io/errors"
	"cosmossdk.io/math"
	nameservice "dysonprotocol.com/x/nameservice"
	nameservicev1 "dysonprotocol.com/x/nameservice/types"
	sdk "github.com/cosmos/cosmos-sdk/types"
	sdkerrors "github.com/cosmos/cosmos-sdk/types/errors"
)

// RejectBid rejects the current bid and optionally increases the name valuation.
// The difference (newValue - oldValue) is used to calculate a proportional fee
// that the owner must pay to the community pool.
func (k Keeper) RejectBid(ctx context.Context, msg *nameservicev1.MsgRejectBid) (*nameservicev1.MsgRejectBidResponse, error) {
	k.Logger.Info("RejectBid: Processing", "nft_class_id", msg.NftClassId, "nft_id", msg.NftId, "owner", msg.Owner, "new_value", msg.NewValuation)

	sdkCtx := sdk.UnwrapSDKContext(ctx)

	// Extract the NFT data
	nftData, err := k.GetNFTData(ctx, msg.NftClassId, msg.NftId)
	if err != nil {
		k.Logger.Error("RejectBid: NFT not found", "nft_class_id", msg.NftClassId, "nft_id", msg.NftId, "error", err)
		return nil, cosmossdkerrors.Wrapf(err, "failed to get NFT data")
	}

	// Verify authorization: the sender must be the owner of the specific NFT
	ownerAddr := k.nftKeeper.GetOwner(ctx, msg.NftClassId, msg.NftId)
	if ownerAddr.String() != msg.Owner {
		k.Logger.Error("RejectBid: Authorization failed",
			"sender", msg.Owner,
			"actual_owner", ownerAddr.String(),
			"nft_class_id", msg.NftClassId,
			"nft_id", msg.NftId)
		return nil, cosmossdkerrors.Wrapf(
			sdkerrors.ErrUnauthorized,
			"only the owner of the NFT (%s) can reject bids for it",
			ownerAddr.String())
	}

	// Convert message sender address
	senderAddr, err := sdk.AccAddressFromBech32(msg.Owner)
	if err != nil {
		k.Logger.Error("RejectBid: Invalid owner address", "owner", msg.Owner, "error", err)
		return nil, cosmossdkerrors.Wrapf(sdkerrors.ErrInvalidAddress, "invalid owner address: %s", msg.Owner)
	}

	// Check if there's an active bid
	if nftData.CurrentBidder == "" || nftData.CurrentBid.IsZero() {
		k.Logger.Error("RejectBid: No active bid", "nft_class_id", msg.NftClassId, "nft_id", msg.NftId)
		return nil, cosmossdkerrors.Wrap(sdkerrors.ErrNotFound, "no active bid to reject")
	}

	// Check that the new valuation has the same denomination as the current bid
	if msg.NewValuation.Denom != nftData.CurrentBid.Denom {
		k.Logger.Error("RejectBid: New valuation denom mismatch",
			"new_valuation_denom", msg.NewValuation.Denom,
			"current_bid_denom", nftData.CurrentBid.Denom)
		return nil, cosmossdkerrors.Wrap(sdkerrors.ErrInvalidRequest,
			fmt.Sprintf("new valuation denom (%s) must match current bid denom (%s)",
				msg.NewValuation.Denom, nftData.CurrentBid.Denom))
	}

	// Enforce that the new valuation is at least the minimum percent higher than the current bid
	classDataForBids, _ := k.GetNFTClassData(ctx, msg.NftClassId)
	minBidIncrease, err := math.LegacyNewDecFromStr(classDataForBids.MinimumBidPercentIncrease)
	if err != nil {
		k.Logger.Error("RejectBid: Failed to parse minimum bid percent increase", "error", err)
		return nil, cosmossdkerrors.Wrap(err, "failed to parse minimum bid percent increase")
	}

	// Convert amounts to LegacyDec for arithmetic
	currentBidAmountLegacy, err := math.LegacyNewDecFromStr(nftData.CurrentBid.Amount.String())
	if err != nil {
		k.Logger.Error("RejectBid: Failed to convert current bid amount to decimal", "error", err)
		return nil, cosmossdkerrors.Wrap(err, "failed to convert current bid amount to decimal")
	}

	// Convert min increase to LegacyDec (even though already a LegacyDec, keep consistent with patterns)
	minBidIncreaseLegacy, err := math.LegacyNewDecFromStr(minBidIncrease.String())
	if err != nil {
		k.Logger.Error("RejectBid: Failed to convert minimum bid increase to legacy decimal", "error", err)
		return nil, cosmossdkerrors.Wrap(err, "failed to convert minimum bid increase to legacy decimal")
	}

	onePlusIncrease := math.LegacyOneDec().Add(minBidIncreaseLegacy)
	minRequiredValuation := currentBidAmountLegacy.Mul(onePlusIncrease).Ceil()

	newValuationAmountLegacy, err := math.LegacyNewDecFromStr(msg.NewValuation.Amount.String())
	if err != nil {
		k.Logger.Error("RejectBid: Failed to convert new valuation amount to decimal", "error", err)
		return nil, cosmossdkerrors.Wrap(err, "failed to convert new valuation amount to decimal")
	}

	if newValuationAmountLegacy.LT(minRequiredValuation) {
		percentDisplay := minBidIncreaseLegacy.Mul(math.LegacyNewDec(100)).TruncateInt().String()
		minRequiredInt := minRequiredValuation.TruncateInt().String()

		k.Logger.Error("RejectBid: New valuation does not meet minimum percentage increase",
			"new_valuation", msg.NewValuation.Amount.String(),
			"current_bid", nftData.CurrentBid.Amount.String(),
			"min_required", minRequiredInt,
			"min_increase_percent_display", percentDisplay,
			"denom", msg.NewValuation.Denom)

		return nil, cosmossdkerrors.Wrap(
			sdkerrors.ErrInvalidRequest,
			fmt.Sprintf(
				"The next minimum acceptable valuation is %s%% higher than current bid: %s %s",
				percentDisplay,
				minRequiredInt,
				msg.NewValuation.Denom,
			),
		)
	}

	// Refund the bidder
	bidderAddr, err := sdk.AccAddressFromBech32(nftData.CurrentBidder)
	if err != nil {
		k.Logger.Error("RejectBid: Invalid bidder address", "bidder", nftData.CurrentBidder, "error", err)
		return nil, cosmossdkerrors.Wrapf(sdkerrors.ErrInvalidAddress, "invalid bidder address: %s", nftData.CurrentBidder)
	}
	bidCoins := sdk.NewCoins(nftData.CurrentBid)
	err = k.bankKeeper.SendCoinsFromModuleToAccount(ctx, nameservice.ModuleName, bidderAddr, bidCoins)
	if err != nil {
		k.Logger.Error("RejectBid: Failed to refund bid amount", "amount", nftData.CurrentBid, "error", err)
		return nil, cosmossdkerrors.Wrap(err, "failed to refund bid amount")
	}

	// Validate the new valuation
	if err := k.ValidateValuation(ctx, msg.NftClassId, msg.NewValuation); err != nil {
		return nil, cosmossdkerrors.Wrapf(err, "failed to validate new valuation: %s", msg.NewValuation.String())
	}

	currentTime := sdkCtx.BlockTime()

	// Set a new expiry time of now + 1 year
	newExpiryTime := currentTime.AddDate(1, 0, 0)

	// --------------------------------
	// Calculate and charge reject bid fee on full new valuation
	// --------------------------------

	// Get the reject bid fee percentage
	rejectFeePercent, err := math.LegacyNewDecFromStr(classDataForBids.RejectBidValuationFeePercent)
	if err != nil {
		return nil, cosmossdkerrors.Wrap(err, "failed to parse reject bid valuation fee percent")
	}

	// Calculate fee based on the full new valuation
	totalFeeCoins := sdk.Coins{}
	if !rejectFeePercent.IsZero() {

		// Convert to DecCoins for decimal arithmetic
		decValuation := sdk.NewDecCoinsFromCoins(msg.NewValuation)

		// Convert to LegacyDec for compatibility with SDK DecCoins methods
		legacyRejectFeePercent, err := math.LegacyNewDecFromStr(rejectFeePercent.String())
		if err != nil {
			return nil, cosmossdkerrors.Wrap(err, "failed to convert reject fee percent to legacy decimal")
		}

		// Calculate the fee amount: valuation * rejectFeePercent
		decRejectFee := decValuation.MulDec(legacyRejectFeePercent)

		// Convert back to regular coins
		totalFeeCoins, _ = decRejectFee.TruncateDecimal()

		// Charge the reject fee
		if !totalFeeCoins.IsZero() {
			k.Logger.Info("Charging reject bid fee on full valuation",
				"nft_class_id", msg.NftClassId,
				"nft_id", msg.NftId,
				"valuation", msg.NewValuation.String(),
				"reject_fee_percent", rejectFeePercent.String(),
				"reject_fee", totalFeeCoins.String())

			// Send to community pool
			if err := k.communityPoolKeeper.FundCommunityPool(ctx, totalFeeCoins, senderAddr); err != nil {
				return nil, cosmossdkerrors.Wrap(err, "failed to fund community pool with reject fee")
			}
		}
	}

	// Update the NFT data: set new valuation, new expiry, clear out the current bid
	nftData.Valuation = msg.NewValuation
	nftData.ValuationExpiry = newExpiryTime
	nftData.CurrentBidder = ""
	nftData.CurrentBid = sdk.Coin{}
	nftData.BidTimestamp = nil

	// Update the NFT data using the centralized function
	if err := k.SetNFTData(ctx, msg.NftClassId, msg.NftId, nftData); err != nil {
		k.Logger.Error("RejectBid: Failed to update NFT data", "error", err)
		return nil, cosmossdkerrors.Wrapf(err, "failed to update NFT data")
	}

	// Emit an event
	if evErr := sdkCtx.EventManager().EmitTypedEvent(
		&nameservicev1.EventBidRejected{
			ClassId:      msg.NftClassId, // Class ID of the NFT
			NftId:        msg.NftId,      // NFT ID
			RejectionFee: totalFeeCoins,  // Fee paid to the community pool
		},
	); evErr != nil {
		k.Logger.Error("failed to emit bid rejected event", "error", evErr)
		return nil, cosmossdkerrors.Wrap(evErr, "failed to emit bid rejected event")
	}

	k.Logger.Info("RejectBid: Completed successfully",
		"nft_class_id", msg.NftClassId,
		"nft_id", msg.NftId,
		"new_valuation", msg.NewValuation.String(),
		"new_expiry", newExpiryTime.Format(time.RFC3339),
		"total_fees", totalFeeCoins.String())

	// TODO: after protobuf regeneration, include RejectionFee in response
	return &nameservicev1.MsgRejectBidResponse{}, nil
}
