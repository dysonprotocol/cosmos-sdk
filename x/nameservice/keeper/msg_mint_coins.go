package keeper

import (
	"context"
	"regexp"

	cosmossdkerrors "cosmossdk.io/errors"
	"cosmossdk.io/math"
	nameservice "dysonprotocol.com/x/nameservice"
	nameservicev1 "dysonprotocol.com/x/nameservice/types"
	sdk "github.com/cosmos/cosmos-sdk/types"
	sdkerrors "github.com/cosmos/cosmos-sdk/types/errors"
)

// MintCoins implements the MsgServer.MintCoins method
func (k Keeper) MintCoins(ctx context.Context, msg *nameservicev1.MsgMintCoins) (*nameservicev1.MsgMintCoinsResponse, error) {
	// 1. Validate signer address
	ownerAddr, err := sdk.AccAddressFromBech32(msg.NameDestination)
	if err != nil {
		return nil, cosmossdkerrors.Wrapf(sdkerrors.ErrInvalidAddress, "invalid name_destination address: %s", msg.NameDestination)
	}

	// 2. Validate coins
	if msg.Amount.Empty() {
		return nil, cosmossdkerrors.Wrap(sdkerrors.ErrInvalidRequest, "no coins to mint")
	}

	// Regex for valid coin denom format - removed the + character
	validDenomPattern := regexp.MustCompile(`^[A-Za-z0-9.\-_]+\.dys(?:/[0-9A-Za-z:\-_]+)*$`)

	// 3. For each coin, verify that the owner owns the root name
	for _, coin := range msg.Amount {
		// Validate coin denom with regex
		if !validDenomPattern.MatchString(coin.Denom) {
			return nil, cosmossdkerrors.Wrapf(
				sdkerrors.ErrInvalidRequest,
				"invalid denom format, must match pattern: %s",
				validDenomPattern.String(),
			)
		}

		// Verify the sender controls the destination for the denom's root name
		if err := k.VerifyDenomDestination(ctx, coin.Denom, msg.NameDestination); err != nil {
			return nil, err
		}
	}

	// 4. Calculate and collect minting fee
	params := k.GetParams(ctx)
	mintFeePerCoin, err := params.GetMintFeePerCoinAsDec()
	if err != nil {
		return nil, cosmossdkerrors.Wrap(err, "failed to parse mint fee per coin")
	}

	var feeCharged sdk.Coins
	if !mintFeePerCoin.IsZero() {
		// Calculate total fee: number_of_coins × mint_fee_per_coin
		numCoins := math.NewInt(int64(len(msg.Amount)))
		totalFeeAmount := mintFeePerCoin.MulInt(numCoins).TruncateInt()

		if !totalFeeAmount.IsZero() {
			feeCharged = sdk.NewCoins(sdk.NewCoin("udys", totalFeeAmount))

			// Collect fee to community pool before minting
			if err := k.communityPoolKeeper.FundCommunityPool(ctx, feeCharged, ownerAddr); err != nil {
				return nil, cosmossdkerrors.Wrap(err, "failed to fund community pool with minting fee")
			}

			k.Logger.Info("MintCoins: Collected minting fee",
				"name_destination", msg.NameDestination,
				"coins_minted", len(msg.Amount),
				"fee_charged", feeCharged.String())
		}
	}

	// 5. Mint the coins to the module account
	err = k.bankKeeper.MintCoins(ctx, nameservice.ModuleName, msg.Amount)
	if err != nil {
		return nil, cosmossdkerrors.Wrap(err, "failed to mint coins")
	}

	// 6. Send the minted coins from the module to the owner
	err = k.bankKeeper.SendCoinsFromModuleToAccount(ctx, nameservice.ModuleName, ownerAddr, msg.Amount)
	if err != nil {
		return nil, cosmossdkerrors.Wrap(err, "failed to send minted coins to owner")
	}

	// 7. Emit event with fee information
	if evErr := sdk.UnwrapSDKContext(ctx).EventManager().EmitTypedEvent(
		&nameservicev1.EventCoinsMinted{
			Amount:     msg.Amount,
			FeeCharged: feeCharged,
		},
	); evErr != nil {
		k.Logger.Error("failed to emit coins minted event", "error", evErr)
		return nil, cosmossdkerrors.Wrap(evErr, "failed to emit coins minted event")
	}

	k.Logger.Info("MintCoins: Successfully minted coins", "name_destination", msg.NameDestination, "amount", msg.Amount.String())

	return &nameservicev1.MsgMintCoinsResponse{}, nil
}
