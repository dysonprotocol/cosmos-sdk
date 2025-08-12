package types

import (
	"context"

	nft "dysonprotocol.com/x/nft"
	sdk "github.com/cosmos/cosmos-sdk/types"
	banktypes "github.com/cosmos/cosmos-sdk/x/bank/types"
)

// AccountKeeper defines the expected account keeper
type AccountKeeper interface {
	GetAccount(ctx context.Context, addr sdk.AccAddress) sdk.AccountI
	GetModuleAccount(ctx context.Context, moduleName string) sdk.ModuleAccountI
	GetModuleAddress(moduleName string) sdk.AccAddress
}

// BankKeeper defines the expected bank keeper
type BankKeeper interface {
	SpendableCoins(ctx context.Context, addr sdk.AccAddress) sdk.Coins
	GetBalance(ctx context.Context, addr sdk.AccAddress, denom string) sdk.Coin
	HasSupply(ctx context.Context, denom string) bool
	SendCoins(ctx context.Context, fromAddr sdk.AccAddress, toAddr sdk.AccAddress, amt sdk.Coins) error
	SendCoinsFromModuleToAccount(ctx context.Context, senderModule string, recipientAddr sdk.AccAddress, amt sdk.Coins) error
	SendCoinsFromAccountToModule(ctx context.Context, senderAddr sdk.AccAddress, recipientModule string, amt sdk.Coins) error
	MintCoins(ctx context.Context, moduleName string, amt sdk.Coins) error
	BurnCoins(ctx context.Context, moduleName string, amt sdk.Coins) error
	SetDenomMetaData(ctx context.Context, denomMetaData banktypes.Metadata)
}

// CommunityPoolKeeper defines the expected community pool keeper
type CommunityPoolKeeper interface {
	FundCommunityPool(ctx context.Context, amount sdk.Coins, sender sdk.AccAddress) error
}

// NFTKeeper defines the expected NFT keeper
type NFTKeeper interface {
	// Class methods
	SaveClass(ctx context.Context, class nft.Class) error
	UpdateClass(ctx context.Context, class nft.Class) error
	GetClass(ctx context.Context, classID string) (nft.Class, bool)
	HasClass(ctx context.Context, classID string) bool

	// NFT methods
	Mint(ctx context.Context, token nft.NFT, receiver sdk.AccAddress) error
	Burn(ctx context.Context, classID string, nftID string) error
	Update(ctx context.Context, token nft.NFT) error
	GetNFT(ctx context.Context, classID string, nftID string) (nft.NFT, bool)
	GetOwner(ctx context.Context, classID string, nftID string) sdk.AccAddress
	HasNFT(ctx context.Context, classID string, nftID string) bool
	// Transfer transfers an NFT to a new owner
	Transfer(ctx context.Context, classID string, nftID string, receiver sdk.AccAddress) error
}
