package types

import (
	"fmt"
)

// Protocol identity constants (not runtime-configurable)
const (
	RootName           = "whaleswap.dys"
	LiquidDenomPrefix  = "whaleswap.dys/coins/"
	PoolsDenomPrefix   = "whaleswap.dys/pools/"
	AuctionClassPrefix = "whaleswap.dys/auction/"
	PfandDenom         = "whaleswap.dys/pfand"
	MintFeeDenom       = "udys"

	OfferStatusOpen      = "open"
	OfferStatusClosed    = "closed"
	OfferStatusCancelled = "cancelled"

	AuctionClassName   = "Whaleswap Auction"
	AuctionClassSymbol = "WSA"
)

// LiquidDenom builds the liquid wrapper denom for a solid denom.
func LiquidDenom(solid string) string { return LiquidDenomPrefix + solid }

// PoolSharesDenom builds the pool shares denom for a pool id.
func PoolSharesDenom(id uint64) string { return fmt.Sprintf("%s%d", PoolsDenomPrefix, id) }

// AuctionClassID builds the auction NFT class id for a bid denom.
func AuctionClassID(bidDenom string) string { return AuctionClassPrefix + bidDenom }
