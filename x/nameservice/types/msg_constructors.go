package types

import (
	sdk "github.com/cosmos/cosmos-sdk/types"
	banktypes "github.com/cosmos/cosmos-sdk/x/bank/types"
)

// NewMsgCommit creates a new MsgCommit instance
func NewMsgCommit(committer string, hexhash string) *MsgCommit {
	return &MsgCommit{
		Committer: committer,
		Hexhash:   hexhash,
	}
}

// NewMsgReveal creates a new MsgReveal instance
func NewMsgReveal(committer, name, salt string) *MsgReveal {
	return &MsgReveal{
		Committer: committer,
		Name:      name,
		Salt:      salt,
	}
}

// NewMsgSetValuation creates a new MsgSetValuation instance
func NewMsgSetValuation(owner, nftClassId, nftId string, valuation sdk.Coin) *MsgSetValuation {
	return &MsgSetValuation{
		Owner:           owner,
		NftClassId:      nftClassId,
		NftId:           nftId,
		Valuation:       valuation,
		MaxAnnualPctFee: "", // Initialize as empty string
	}
}

// NewMsgRenew creates a new MsgRenew instance
func NewMsgRenew(payer, nftClassId, nftId string) *MsgRenew {
	return &MsgRenew{
		Payer:      payer,
		NftClassId: nftClassId,
		NftId:      nftId,
	}
}

// NewMsgPlaceBid creates a new MsgPlaceBid instance
func NewMsgPlaceBid(bidder string, nftClassId string, nftId string, bidAmount sdk.Coin) *MsgPlaceBid {
	return &MsgPlaceBid{
		Bidder:     bidder,
		NftClassId: nftClassId,
		NftId:      nftId,
		BidAmount:  bidAmount,
	}
}

// NewMsgAcceptBid creates a new MsgAcceptBid instance
func NewMsgAcceptBid(owner string, nftClassId string, nftId string) *MsgAcceptBid {
	return &MsgAcceptBid{
		Owner:      owner,
		NftClassId: nftClassId,
		NftId:      nftId,
	}
}

// NewMsgRejectBid creates a new MsgRejectBid instance
func NewMsgRejectBid(owner string, nftClassId string, nftId string, newValuation sdk.Coin) *MsgRejectBid {
	return &MsgRejectBid{
		Owner:        owner,
		NftClassId:   nftClassId,
		NftId:        nftId,
		NewValuation: newValuation,
	}
}

// NewMsgClaimBid creates a new MsgClaimBid instance
func NewMsgClaimBid(bidder string, nftClassId string, nftId string) *MsgClaimBid {
	return &MsgClaimBid{
		Bidder:     bidder,
		NftClassId: nftClassId,
		NftId:      nftId,
	}
}

// NewMsgSetDestination creates a new MsgSetDestination instance
func NewMsgSetDestination(owner string, name string, destination string) *MsgSetDestination {
	return &MsgSetDestination{
		Owner:       owner,
		Name:        name,
		Destination: destination,
	}
}

// NewMsgMintCoins creates a new MsgMintCoins instance
func NewMsgMintCoins(owner string, amount sdk.Coins) *MsgMintCoins {
	return &MsgMintCoins{
		Owner:  owner,
		Amount: amount,
	}
}

// NewMsgBurnCoins creates a new MsgBurnCoins instance
func NewMsgBurnCoins(owner string, amount sdk.Coins) *MsgBurnCoins {
	return &MsgBurnCoins{
		Owner:  owner,
		Amount: amount,
	}
}

// NewMsgSetDenomMetadata creates a new MsgSetDenomMetadata instance
func NewMsgSetDenomMetadata(authority string, metadata banktypes.Metadata) *MsgSetDenomMetadata {
	return &MsgSetDenomMetadata{
		Authority: authority,
		Metadata:  metadata,
	}
}

// NewMsgSaveClass creates a new MsgSaveClass instance
func NewMsgSaveClass(
	owner string,
	classID string,
	name string,
	symbol string,
	description string,
	uri string,
	uriHash string,
) *MsgSaveClass {
	return &MsgSaveClass{
		Owner:       owner,
		ClassId:     classID,
		Name:        name,
		Symbol:      symbol,
		Description: description,
		Uri:         uri,
		UriHash:     uriHash,
	}
}

// NewMsgMintNFT creates a new MsgMintNFT instance
func NewMsgMintNFT(
	owner string,
	classID string,
	nftID string,
	uri string,
	uriHash string,
) *MsgMintNFT {
	return &MsgMintNFT{
		Owner:   owner,
		ClassId: classID,
		NftId:   nftID,
		Uri:     uri,
		UriHash: uriHash,
	}
}

// NewMsgBurnNFT creates a new MsgBurnNFT instance
func NewMsgBurnNFT(
	owner string,
	classID string,
	nftID string,
) *MsgBurnNFT {
	return &MsgBurnNFT{
		Owner:   owner,
		ClassId: classID,
		NftId:   nftID,
	}
}

// NewMsgSetNFTMetadata creates a new MsgSetNFTMetadata instance
func NewMsgSetNFTMetadata(owner, classID, nftID, metadata string) *MsgSetNFTMetadata {
	return &MsgSetNFTMetadata{
		Owner:    owner,
		ClassId:  classID,
		NftId:    nftID,
		Metadata: metadata,
	}
}

// NewMsgSetNFTClassExtraData creates a new MsgSetNFTClassExtraData instance
func NewMsgSetNFTClassExtraData(owner, classID, extraData string) *MsgSetNFTClassExtraData {
	return &MsgSetNFTClassExtraData{
		Owner:     owner,
		ClassId:   classID,
		ExtraData: extraData,
	}
}
