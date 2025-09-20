package keeper

import (
	"context"
	"fmt"
	"strings"

	"cosmossdk.io/collections"
	"cosmossdk.io/core/store"
	"cosmossdk.io/log"
	cosmossdk_math "cosmossdk.io/math"

	nameservicekeeper "dysonprotocol.com/x/nameservice/keeper"
	nameservicev1 "dysonprotocol.com/x/nameservice/types"
	whaleswap "dysonprotocol.com/x/whaleswap"
	whaleswapv1 "dysonprotocol.com/x/whaleswap/types"
	"github.com/cosmos/cosmos-sdk/codec"
	sdk "github.com/cosmos/cosmos-sdk/types"
)

var (
	ParamsKey   = collections.NewPrefix(0)
	PoolSeqKey  = collections.NewPrefix(1)
	PoolsPrefix = collections.NewPrefix(2)
	// Orderbook sequences and maps
	OfferSeqKey  = collections.NewPrefix(3)
	OffersPrefix = collections.NewPrefix(4)
	TradeSeqKey  = collections.NewPrefix(5)
	TradesPrefix = collections.NewPrefix(6)
	// Auctions
	AuctionSeqKey  = collections.NewPrefix(7)
	AuctionsPrefix = collections.NewPrefix(8)
	// Auction reverse indexes
	AuctionsBySellBidPrefix = collections.NewPrefix(9)
	AuctionsByBidSellPrefix = collections.NewPrefix(10)
	// Offers reverse indexes
	OffersByHavePrefix        = collections.NewPrefix(11)
	OffersByWantPrefix        = collections.NewPrefix(12)
	OffersByPairPricePrefix   = collections.NewPrefix(13)
	OffersByOwnerStatusPrefix = collections.NewPrefix(14)
)

type Keeper struct {
	cdc       codec.Codec
	store     store.KVStoreService
	accKeeper whaleswapv1.AccountKeeper
	bank      whaleswapv1.BankKeeper
	nameSvc   whaleswapv1.NameserviceKeeper
	nft       whaleswapv1.NFTKeeper
	logger    log.Logger
	// authority address that can update params
	authority string

	Schema   collections.Schema
	params   collections.Item[whaleswapv1.Params]
	poolSeq  collections.Sequence
	PoolsMap collections.Map[uint64, whaleswapv1.Pool]
	// Orderbook
	offerSeq  collections.Sequence
	OffersMap collections.Map[uint64, whaleswapv1.OfferData]
	tradeSeq  collections.Sequence
	TradesMap collections.Map[uint64, whaleswapv1.Trade]
	// Offer reverse indexes
	OffersByHave        collections.Map[collections.Pair[string, uint64], uint64]
	OffersByWant        collections.Map[collections.Pair[string, uint64], uint64]
	OffersByPairPrice   collections.Map[collections.Triple[string, string, uint64], uint64]
	OffersByOwnerStatus collections.Map[collections.Triple[string, string, uint64], uint64]
	// Auctions (scaffold)
	auctionSeq  collections.Sequence
	AuctionsMap collections.Map[uint64, whaleswapv1.AuctionRecord]
	// Reverse indexes
	AuctionsBySellBid collections.Map[collections.Triple[string, string, uint64], uint64]
	AuctionsByBidSell collections.Map[collections.Triple[string, string, uint64], uint64]
}

func NewKeeper(
	cdc codec.Codec,
	store store.KVStoreService,
	acc whaleswapv1.AccountKeeper,
	bank whaleswapv1.BankKeeper,
	nameSvc whaleswapv1.NameserviceKeeper,
	nft whaleswapv1.NFTKeeper,
	logger log.Logger,
	authority string,
) Keeper {
	sb := collections.NewSchemaBuilder(store)
	k := Keeper{
		cdc:       cdc,
		store:     store,
		accKeeper: acc,
		bank:      bank,
		nameSvc:   nameSvc,
		nft:       nft,
		logger:    logger,
		authority: authority,
		params: collections.NewItem(
			sb,
			ParamsKey,
			"params",
			codec.CollValue[whaleswapv1.Params](cdc),
		),
	}
	k.poolSeq = collections.NewSequence(sb, PoolSeqKey, "pool_seq")
	k.PoolsMap = collections.NewMap(
		sb,
		PoolsPrefix,
		"pools",
		collections.Uint64Key,
		codec.CollValue[whaleswapv1.Pool](cdc),
	)
	// Orderbook collections
	k.offerSeq = collections.NewSequence(sb, OfferSeqKey, "offer_seq")
	k.OffersMap = collections.NewMap(
		sb,
		OffersPrefix,
		"offers",
		collections.Uint64Key,
		codec.CollValue[whaleswapv1.OfferData](cdc),
	)
	k.OffersByHave = collections.NewMap(
		sb,
		OffersByHavePrefix,
		"offers_by_have",
		collections.PairKeyCodec(collections.StringKey, collections.Uint64Key),
		collections.Uint64Value,
	)
	k.OffersByWant = collections.NewMap(
		sb,
		OffersByWantPrefix,
		"offers_by_want",
		collections.PairKeyCodec(collections.StringKey, collections.Uint64Key),
		collections.Uint64Value,
	)
	k.OffersByPairPrice = collections.NewMap(
		sb,
		OffersByPairPricePrefix,
		"offers_by_pair_price",
		collections.TripleKeyCodec(collections.StringKey, collections.StringKey, collections.Uint64Key),
		collections.Uint64Value,
	)
	k.OffersByOwnerStatus = collections.NewMap(
		sb,
		OffersByOwnerStatusPrefix,
		"offers_by_owner_status",
		collections.TripleKeyCodec(collections.StringKey, collections.StringKey, collections.Uint64Key),
		collections.Uint64Value,
	)
	k.tradeSeq = collections.NewSequence(sb, TradeSeqKey, "trade_seq")
	k.TradesMap = collections.NewMap(
		sb,
		TradesPrefix,
		"trades",
		collections.Uint64Key,
		codec.CollValue[whaleswapv1.Trade](cdc),
	)
	// Auctions collections (sequence only for now)
	k.auctionSeq = collections.NewSequence(sb, AuctionSeqKey, "auction_seq")
	k.AuctionsMap = collections.NewMap(
		sb,
		AuctionsPrefix,
		"auctions",
		collections.Uint64Key,
		codec.CollValue[whaleswapv1.AuctionRecord](cdc),
	)
	k.AuctionsBySellBid = collections.NewMap(
		sb,
		AuctionsBySellBidPrefix,
		"auctions_by_sell_bid",
		collections.TripleKeyCodec(collections.StringKey, collections.StringKey, collections.Uint64Key),
		collections.Uint64Value,
	)
	k.AuctionsByBidSell = collections.NewMap(
		sb,
		AuctionsByBidSellPrefix,
		"auctions_by_bid_sell",
		collections.TripleKeyCodec(collections.StringKey, collections.StringKey, collections.Uint64Key),
		collections.Uint64Value,
	)
	schema, err := sb.Build()
	if err != nil {
		panic(err)
	}
	k.Schema = schema
	return k
}

func (k Keeper) Logger(ctx sdk.Context) log.Logger {
	return ctx.Logger().With("module", "x/whaleswap")
}

func (k Keeper) GetAuthority() string { return k.authority }

func (k Keeper) GetParams(ctx context.Context) (p whaleswapv1.Params) {
	p, err := k.params.Get(ctx)
	if err != nil {
		return whaleswapv1.Params{}
	}
	return p
}

func (k Keeper) SetParams(ctx context.Context, p whaleswapv1.Params) error {
	if err := p.Validate(); err != nil {
		return err
	}
	return k.params.Set(ctx, p)
}

// helpers
func (k Keeper) addr(_ context.Context, bech32 string) (sdk.AccAddress, error) {
	return sdk.AccAddressFromBech32(bech32)
}

func (k Keeper) normalizeBand(band sdk.Coins, denom1, denom2 string) (sdk.Coins, error) {
	if len(band) == 0 {
		return nil, nil
	}
	if len(band) != 2 {
		return nil, fmt.Errorf("price band must contain exactly two coins or be empty")
	}
	// Build canonical two-coin set in requested denom order and rely on SDK validation
	c1 := band.AmountOf(denom1)
	c2 := band.AmountOf(denom2)
	coins := sdk.NewCoins(
		sdk.NewCoin(denom1, c1),
		sdk.NewCoin(denom2, c2),
	)
	if err := coins.Validate(); err != nil {
		return nil, fmt.Errorf("invalid price band: %w", err)
	}
	return coins, nil
}

func (k Keeper) bandRatio(band sdk.Coins, denom1, denom2 string) (cosmossdk_math.LegacyDec, error) {
	if len(band) != 2 {
		return cosmossdk_math.LegacyDec{}, fmt.Errorf("band must have 2 coins")
	}
	a := band.AmountOf(denom1)
	b := band.AmountOf(denom2)
	return cosmossdk_math.LegacyNewDecFromInt(b).Quo(cosmossdk_math.LegacyNewDecFromInt(a)), nil
}

func (k Keeper) currentPrice(pool whaleswapv1.Pool) (cosmossdk_math.LegacyDec, error) {
	r1 := cosmossdk_math.LegacyNewDecFromInt(pool.CoinA.Amount)
	r2 := cosmossdk_math.LegacyNewDecFromInt(pool.CoinB.Amount)
	if r1.IsZero() {
		return cosmossdk_math.LegacyDec{}, fmt.Errorf("reserve1 is zero")
	}
	return r2.Quo(r1), nil
}

// ---- Concentrated liquidity helpers ----

// sqrtPrice returns sqrt(dec) using LegacyDec.ApproxSqrt
func (k Keeper) sqrtPrice(d cosmossdk_math.LegacyDec) (cosmossdk_math.LegacyDec, error) {
	return d.ApproxSqrt()
}

// bandSqrt returns sa, sb (sqrt(min_price), sqrt(max_price))
func (k Keeper) bandSqrt(pool whaleswapv1.Pool) (cosmossdk_math.LegacyDec, cosmossdk_math.LegacyDec, error) {
	if len(pool.MinPrice) != 2 || len(pool.MaxPrice) != 2 {
		return cosmossdk_math.LegacyDec{}, cosmossdk_math.LegacyDec{}, fmt.Errorf("band not set")
	}
	minRatio := cosmossdk_math.LegacyNewDecFromInt(pool.MinPrice.AmountOf(pool.CoinB.Denom)).Quo(
		cosmossdk_math.LegacyNewDecFromInt(pool.MinPrice.AmountOf(pool.CoinA.Denom)),
	)
	maxRatio := cosmossdk_math.LegacyNewDecFromInt(pool.MaxPrice.AmountOf(pool.CoinB.Denom)).Quo(
		cosmossdk_math.LegacyNewDecFromInt(pool.MaxPrice.AmountOf(pool.CoinA.Denom)),
	)
	sa, err := k.sqrtPrice(minRatio)
	if err != nil {
		return cosmossdk_math.LegacyDec{}, cosmossdk_math.LegacyDec{}, err
	}
	sb, err := k.sqrtPrice(maxRatio)
	if err != nil {
		return cosmossdk_math.LegacyDec{}, cosmossdk_math.LegacyDec{}, err
	}
	return sa, sb, nil
}

// poolSqrtPrice returns current sqrt price sp
func (k Keeper) poolSqrtPrice(pool whaleswapv1.Pool) (cosmossdk_math.LegacyDec, error) {
	p, err := k.currentPrice(pool)
	if err != nil {
		return cosmossdk_math.LegacyDec{}, err
	}
	return k.sqrtPrice(p)
}

// liquidityForReserves computes L from current reserves when sp in band
func (k Keeper) liquidityForReserves(pool whaleswapv1.Pool) (cosmossdk_math.LegacyDec, cosmossdk_math.LegacyDec, cosmossdk_math.LegacyDec, error) {
	sa, sb, err := k.bandSqrt(pool)
	if err != nil {
		return cosmossdk_math.LegacyDec{}, cosmossdk_math.LegacyDec{}, cosmossdk_math.LegacyDec{}, err
	}
	sp, err := k.poolSqrtPrice(pool)
	if err != nil {
		return cosmossdk_math.LegacyDec{}, cosmossdk_math.LegacyDec{}, cosmossdk_math.LegacyDec{}, err
	}
	if sp.LT(sa) || sp.GT(sb) {
		return cosmossdk_math.LegacyDec{}, cosmossdk_math.LegacyDec{}, cosmossdk_math.LegacyDec{}, fmt.Errorf("price outside band")
	}
	r1 := cosmossdk_math.LegacyNewDecFromInt(pool.CoinA.Amount)
	r2 := cosmossdk_math.LegacyNewDecFromInt(pool.CoinB.Amount)
	// L candidates
	// L0 = R1 * sp * sb / (sb - sp)
	L0 := r1.Mul(sp).Mul(sb).Quo(sb.Sub(sp))
	// L1 = R2 / (sp - sa)
	L1 := r2.Quo(sp.Sub(sa))
	L := cosmossdk_math.LegacyMinDec(L0, L1)
	return L, sa, sb, nil
}

func (k Keeper) ensureMajorityOwner(ctx context.Context, pool whaleswapv1.Pool, signer sdk.AccAddress) error {
	total := k.bank.GetSupply(ctx, pool.SharesDenom).Amount
	if !total.IsPositive() {
		return fmt.Errorf("invalid total shares supply")
	}
	bal := k.bank.GetBalance(ctx, signer, pool.SharesDenom).Amount
	if bal.MulRaw(2).LTE(total) {
		return fmt.Errorf("signer is not majority owner of shares")
	}
	return nil
}

func (k Keeper) updatePool(ctx context.Context, pool *whaleswapv1.Pool) error {
	sdkCtx := sdk.UnwrapSDKContext(ctx)
	t := sdkCtx.BlockTime()
	pool.Updated = &t
	if err := k.PoolsMap.Set(ctx, pool.PoolId, *pool); err != nil {
		return err
	}
	_ = sdkCtx.EventManager().EmitTypedEvent(&whaleswapv1.EventPoolUpdate{PoolId: pool.PoolId})
	return nil
}

func (k Keeper) sendToModule(ctx context.Context, from sdk.AccAddress, coins sdk.Coins) error {
	return k.bank.SendCoinsFromAccountToModule(ctx, from, whaleswap.ModuleName, coins)
}

func (k Keeper) sendFromModule(ctx context.Context, to sdk.AccAddress, coins sdk.Coins) error {
	return k.bank.SendCoinsFromModuleToAccount(ctx, whaleswap.ModuleName, to, coins)
}

func (k Keeper) burnModule(ctx context.Context, coins sdk.Coins) error {
	return k.bank.BurnCoins(ctx, whaleswap.ModuleName, coins)
}

// ----- Orderbook + liquid helpers -----

const liquidPrefix = whaleswapv1.LiquidDenomPrefix

func (k Keeper) isLiquidDenom(denom string) bool {
	return strings.HasPrefix(denom, liquidPrefix)
}

// decodeLiquidDenom strips whaleswap.dys/coins/ prefix and returns the solid denom
func (k Keeper) decodeLiquidDenom(liquid string) (string, error) {
	if !k.isLiquidDenom(liquid) {
		return "", fmt.Errorf("invalid liquid denom: %s", liquid)
	}
	return strings.TrimPrefix(liquid, liquidPrefix), nil
}

// gcdInt computes GCD(a,b) using Euclidean algorithm
func (k Keeper) gcdInt(a, b cosmossdk_math.Int) cosmossdk_math.Int {
	if a.IsNegative() {
		a = a.Neg()
	}
	if b.IsNegative() {
		b = b.Neg()
	}
	for b.IsPositive() {
		t := a.Mod(b)
		a = b
		b = t
	}
	return a
}

// ensureWhaleswapRootName ensures that the root name "whaleswap.dys" exists and
// resolves to the whaleswap module account. This allows nameservice auth checks
// to pass when minting shares under the denom prefix "whaleswap.dys/...".
func (k Keeper) ensureWhaleswapRootName(ctx context.Context) error {
	// Resolve destination if the name exists already
	authority := k.nameSvc.GetAuthority()

	want := k.accKeeper.GetModuleAddress(whaleswap.ModuleName).String()
	if dest, err := k.nameSvc.ResolveNameOrAddress(ctx, whaleswapv1.RootName); err == nil {
		if dest == want {
			return nil
		}
		// Update destination to whaleswap module address; owner is current NFT owner
		owner := k.nft.GetOwner(ctx, nameservicekeeper.NamesClassID, whaleswapv1.RootName).String()
		set := &nameservicev1.MsgSetDestination{Owner: owner, Name: whaleswapv1.RootName, Destination: want}
		if _, err := k.nameSvc.SetDestination(ctx, set); err != nil {
			return fmt.Errorf("failed to set destination for %s to module: %w", whaleswapv1.RootName, err)
		}
		return nil
	}

	// Name not found: mint the name NFT to nameservice authority, then set destination
	mint := &nameservicev1.MsgMintNFT{
		NameDestination: authority,
		ClassId:         nameservicekeeper.NamesClassID,
		NftId:           whaleswapv1.RootName,
		Uri:             want,
		UriHash:         "",
	}
	if _, err := k.nameSvc.MintNFT(ctx, mint); err != nil {
		return fmt.Errorf("failed to mint name NFT %s to nameservice authority: %w", whaleswapv1.RootName, err)
	}
	set := &nameservicev1.MsgSetDestination{Owner: authority, Name: whaleswapv1.RootName, Destination: want}
	if _, err := k.nameSvc.SetDestination(ctx, set); err != nil {
		return fmt.Errorf("failed to set destination for %s to module after mint: %w", whaleswapv1.RootName, err)
	}
	return nil
}
