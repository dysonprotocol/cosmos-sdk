package types

import (
	"encoding/json"

	cosmossdkerrors "cosmossdk.io/errors"
	sdk "github.com/cosmos/cosmos-sdk/types"
)

// SetNFTClassData marshals the NFTClassData into JSON and sets it as the class metadata
func SetNFTClassData(classData *NFTClassData) (string, error) {
	bz, err := json.Marshal(classData)
	if err != nil {
		return "", cosmossdkerrors.Wrap(err, "failed to marshal NFT class data")
	}
	return string(bz), nil
}

// GetNFTClassData unmarshals the class metadata JSON into NFTClassData
func GetNFTClassDataFromJSON(metadata string) (*NFTClassData, error) {
	var classData NFTClassData
	err := json.Unmarshal([]byte(metadata), &classData)
	if err != nil {
		return nil, cosmossdkerrors.Wrap(err, "failed to unmarshal NFT class data")
	}
	return &classData, nil
}

// SetNFTData marshals the NFTData into JSON and sets it as the NFT metadata
func SetNFTData(nftData *NFTData) (string, error) {
	bz, err := json.Marshal(nftData)
	if err != nil {
		return "", cosmossdkerrors.Wrap(err, "failed to marshal NFT data")
	}
	return string(bz), nil
}

// GetNFTDataFromJSON unmarshals the NFT metadata JSON into NFTData
func GetNFTDataFromJSON(metadata string) (*NFTData, error) {
	var nftData NFTData
	err := json.Unmarshal([]byte(metadata), &nftData)
	if err != nil {
		return nil, cosmossdkerrors.Wrap(err, "failed to unmarshal NFT data")
	}
	return &nftData, nil
}

// NewNFTClassData creates a new NFTClassData with default values
func NewNFTClassData() *NFTClassData {
	return &NFTClassData{
		AlwaysListed:    false,
		ValuationFeePct: "0",
	}
}

// NewNFTData creates a new NFTData with default values
func NewNFTData() *NFTData {
	return &NFTData{
		Listed:        false,
		Valuation:     sdk.Coin{},
		CurrentBidder: "",
		CurrentBid:    sdk.Coin{},
	}
}
