package keeper

import (
	"context"
	"fmt"

	"strings"

	"cosmossdk.io/collections"
	cosmossdkerrors "cosmossdk.io/errors"
	nameservicev1 "dysonprotocol.com/x/nameservice/types"
	whaleswap "dysonprotocol.com/x/whaleswap"
	whaleswapv1 "dysonprotocol.com/x/whaleswap/types"
	sdk "github.com/cosmos/cosmos-sdk/types"
	sdkerrors "github.com/cosmos/cosmos-sdk/types/errors"
)

func (k Keeper) OpenAuction(ctx context.Context, msg *whaleswapv1.MsgOpenAuction) (*whaleswapv1.MsgOpenAuctionResponse, error) {
	sellerBz, err := k.accKeeper.AddressCodec().StringToBytes(msg.Seller)
	if err != nil {
		return nil, cosmossdkerrors.Wrapf(err, "invalid seller")
	}
	seller := sdk.AccAddress(sellerBz)

	// Validate sell coin (explicit in msg): solid denom, amount > 0, denom != bid_denom
	if !msg.Sell.Amount.IsPositive() {
		return nil, cosmossdkerrors.Wrap(sdkerrors.ErrInvalidRequest, "sell amount must be > 0")
	}
	if k.isLiquidDenom(msg.Sell.Denom) {
		return nil, cosmossdkerrors.Wrapf(sdkerrors.ErrInvalidRequest, "sell denom is liquid: %s", msg.Sell.Denom)
	}
	if msg.Sell.Denom == msg.BidDenom {
		return nil, cosmossdkerrors.Wrapf(sdkerrors.ErrInvalidRequest, "sell and bid denoms must differ: %s", msg.Sell.Denom)
	}

	// Escrow: move from seller → module
	if err := k.bank.SendCoinsFromAccountToModule(ctx, seller, whaleswap.ModuleName, sdk.NewCoins(msg.Sell)); err != nil {
		return nil, cosmossdkerrors.Wrapf(err, "failed to send coins from account to module")
	}

	// Prepare class id based on bid denom (one class per bid denom)
	classID := fmt.Sprintf("whaleswap.dys/auction/%s", msg.BidDenom)
	// Upsert class basic info
	if _, err := k.nameSvc.SaveClass(ctx, &nameservicev1.MsgSaveClass{
		NameDestination: k.accKeeper.GetModuleAddress(whaleswap.ModuleName).String(),
		ClassId:         classID,
		Name:            "Whaleswap Auction",
		Symbol:          "WSA",
		Description:     "Auction class for escrowed solid coins",
	}); err != nil {
		return nil, cosmossdkerrors.Wrapf(err, "failed to save class")
	}
	// Apply policy knobs using params
	p := k.GetParams(ctx)
	_, _ = k.nameSvc.SetNFTClassAlwaysListed(ctx, &nameservicev1.MsgSetNFTClassAlwaysListed{NameDestination: k.accKeeper.GetModuleAddress(whaleswap.ModuleName).String(), ClassId: classID, AlwaysListed: true})
	_, _ = k.nameSvc.SetNFTClassValuationFeePct(ctx, &nameservicev1.MsgSetNFTClassValuationFeePct{NameDestination: k.accKeeper.GetModuleAddress(whaleswap.ModuleName).String(), ClassId: classID, ValuationFeePct: p.ValuationFeePct})
	_, _ = k.nameSvc.SetNFTClassValuationPeriod(ctx, &nameservicev1.MsgSetNFTClassValuationPeriod{NameDestination: k.accKeeper.GetModuleAddress(whaleswap.ModuleName).String(), ClassId: classID, ValuationPeriod: p.ValuationPeriod})
	_, _ = k.nameSvc.SetNFTClassBidTimeout(ctx, &nameservicev1.MsgSetNFTClassBidTimeout{NameDestination: k.accKeeper.GetModuleAddress(whaleswap.ModuleName).String(), ClassId: classID, BidTimeout: p.BidTimeout})
	_, _ = k.nameSvc.SetNFTClassMinimumBidPercentIncrease(ctx, &nameservicev1.MsgSetNFTClassMinimumBidPercentIncrease{NameDestination: k.accKeeper.GetModuleAddress(whaleswap.ModuleName).String(), ClassId: classID, MinimumBidPercentIncrease: p.MinimumBidPercentIncrease})
	// Allowed denoms: only bid_denom
	_, _ = k.nameSvc.SetNFTClassAllowedDenoms(ctx, &nameservicev1.MsgSetNFTClassAllowedDenoms{
		NameDestination: k.accKeeper.GetModuleAddress(whaleswap.ModuleName).String(),
		ClassId:         classID,
		AllowedDenoms:   []string{msg.BidDenom},
	})

	// Mint NFT id = auctionSeq, send to seller
	id, err := k.auctionSeq.Next(ctx)
	if err != nil {
		return nil, cosmossdkerrors.Wrapf(err, "failed to get next auction id")
	}
	nftID := fmt.Sprintf("%010d", id)
	if _, err := k.nameSvc.MintNFT(ctx, &nameservicev1.MsgMintNFT{NameDestination: k.accKeeper.GetModuleAddress(whaleswap.ModuleName).String(), ClassId: classID, NftId: nftID}); err != nil {
		return nil, cosmossdkerrors.Wrapf(err, "failed to mint nft")
	}
	if _, err := k.nameSvc.MoveNft(ctx, &nameservicev1.MsgMoveNft{NameDestination: k.accKeeper.GetModuleAddress(whaleswap.ModuleName).String(), ClassId: classID, NftId: nftID, ToAddress: msg.Seller}); err != nil {
		return nil, cosmossdkerrors.Wrapf(err, "failed to move nft")
	}

	// Record auction
	rec := whaleswapv1.AuctionRecord{AuctionId: id, ClassId: classID, NftId: nftID, Sell: msg.Sell, BidDenom: msg.BidDenom, Seller: msg.Seller}
	if err := k.AuctionsMap.Set(ctx, id, rec); err != nil {
		return nil, cosmossdkerrors.Wrapf(err, "failed to set auction")
	}
	// Write reverse indexes
	if err := k.AuctionsBySellBid.Set(ctx, collections.Join3(rec.Sell.Denom, rec.BidDenom, rec.AuctionId), rec.AuctionId); err != nil {
		return nil, cosmossdkerrors.Wrapf(err, "failed to set auction by sell bid")
	}
	if err := k.AuctionsByBidSell.Set(ctx, collections.Join3(rec.BidDenom, rec.Sell.Denom, rec.AuctionId), rec.AuctionId); err != nil {
		return nil, cosmossdkerrors.Wrapf(err, "failed to set auction by bid sell")
	}

	_ = sdk.UnwrapSDKContext(ctx).EventManager().EmitTypedEvent(&whaleswapv1.EventAuctionCreated{AuctionId: id})
	return &whaleswapv1.MsgOpenAuctionResponse{AuctionId: id}, nil
}

func (k Keeper) RedeemAuction(ctx context.Context, msg *whaleswapv1.MsgRedeemAuction) (*whaleswapv1.MsgRedeemAuctionResponse, error) {
	rec, err := k.AuctionsMap.Get(ctx, msg.AuctionId)
	if err != nil {
		return nil, cosmossdkerrors.Wrapf(err, "auction not found: %d", msg.AuctionId)
	}
	if rec.Seller != msg.Caller {
		return nil, cosmossdkerrors.Wrap(sdkerrors.ErrUnauthorized, "only seller can redeem in MVP")
	}
	// Enforce no current bidder
	nftData, err := k.nameSvc.GetNFTData(ctx, rec.ClassId, rec.NftId)
	if err != nil {
		return nil, cosmossdkerrors.Wrapf(err, "nft not found: %s/%s", rec.ClassId, rec.NftId)
	}
	if strings.TrimSpace(nftData.CurrentBidder) != "" {
		return nil, cosmossdkerrors.Wrap(sdkerrors.ErrInvalidRequest, "cannot redeem while a bid is active")
	}
	to, err2 := k.accKeeper.AddressCodec().StringToBytes(msg.Caller)
	if err2 != nil {
		return nil, cosmossdkerrors.Wrapf(err2, "invalid caller")
	}
	if err := k.bank.SendCoinsFromModuleToAccount(ctx, whaleswap.ModuleName, sdk.AccAddress(to), sdk.NewCoins(rec.Sell)); err != nil {
		return nil, cosmossdkerrors.Wrapf(err, "failed to send coins")
	}
	if _, err := k.nameSvc.BurnNFT(ctx, &nameservicev1.MsgBurnNFT{NameDestination: k.accKeeper.GetModuleAddress(whaleswap.ModuleName).String(), ClassId: rec.ClassId, NftId: rec.NftId}); err != nil {
		return nil, cosmossdkerrors.Wrapf(err, "failed to burn nft")
	}
	// Delete record + reverse indexes
	if err := k.AuctionsMap.Remove(ctx, msg.AuctionId); err != nil {
		return nil, cosmossdkerrors.Wrapf(err, "failed to remove auction")
	}
	_ = k.AuctionsBySellBid.Remove(ctx, collections.Join3(rec.Sell.Denom, rec.BidDenom, rec.AuctionId))
	_ = k.AuctionsByBidSell.Remove(ctx, collections.Join3(rec.BidDenom, rec.Sell.Denom, rec.AuctionId))
	_ = sdk.UnwrapSDKContext(ctx).EventManager().EmitTypedEvent(&whaleswapv1.EventAuctionRedeemed{AuctionId: msg.AuctionId})
	return &whaleswapv1.MsgRedeemAuctionResponse{}, nil
}
