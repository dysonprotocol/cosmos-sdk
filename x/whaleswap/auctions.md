## Auctions

### High-level architecture
- Whaleswap opens an “auction” by:
  - Escrowing a solid coin in the whaleswap module.
  - Minting an NFT in nameservice as the on-chain marker/handle for that auction.
  - Configuring the NFT class policy to enable/limit bidding.
- Bids, accept/reject/claim are handled by the nameservice module on that NFT.
- When there’s no active bid, the current NFT owner can redeem the escrow from whaleswap; whaleswap burns the NFT, cleans indexes, and (if a sale happened) records a Trade.

### Core data models (and relations)
- Whaleswap
  - AuctionRecord: links escrow → NFT identity and denoms.
```97:105:/Users/user/dysonprotocol2/proto/dysonprotocol/whaleswap/v1/whaleswap.proto
message AuctionRecord {
  uint64 auction_id = 1;
  string class_id = 2;
  string nft_id = 3;
  cosmos.base.v1beta1.Coin sell = 4 [ (gogoproto.nullable) = false ];
  string bid_denom = 5;
  string seller = 6 [ (cosmos_proto.scalar) = "cosmos.AddressString" ];
}
```
  - Msgs:
```268:287:/Users/user/dysonprotocol2/proto/dysonprotocol/whaleswap/v1/tx.proto
// Open an auction by escrowing exactly one solid denom amount.
message MsgOpenAuction { ... }
// Redeem auction escrow by NFT owner when no current bidder exists.
message MsgRedeemAuction { ... }
```
  - Indices (primary + reverse):
```22:45:/Users/user/dysonprotocol2/x/whaleswap/keeper/keeper.go
var (
  ...
  // Auctions
  AuctionSeqKey  = collections.NewPrefix(7)
  AuctionsPrefix = collections.NewPrefix(8)
  // Auction reverse indexes
  AuctionsBySellBidPrefix = collections.NewPrefix(9)
  AuctionsByBidSellPrefix = collections.NewPrefix(10)
  ...
)
```
```75:81:/Users/user/dysonprotocol2/x/whaleswap/keeper/keeper.go
auctionSeq  collections.Sequence
AuctionsMap collections.Map[uint64, whaleswapv1.AuctionRecord]
AuctionsBySellBid collections.Map[collections.Triple[string, string, uint64], uint64]
AuctionsByBidSell collections.Map[collections.Triple[string, string, uint64], uint64]
```
  - Events:
```45:55:/Users/user/dysonprotocol2/proto/dysonprotocol/whaleswap/v1/events.proto
message EventAuctionCreated { uint64 auction_id = 1; }
message EventAuctionRedeemed { uint64 auction_id = 1; }
message EventTradeRecorded { uint64 trade_id = 1; uint64 offer_id = 2; uint64 pool_id = 3; uint64 auction_id = 4; }
```
  - Params applied to NFT class:
```18:49:/Users/user/dysonprotocol2/proto/dysonprotocol/whaleswap/v1/params.proto
// valuation_fee_pct, valuation_period, bid_timeout, minimum_bid_percent_increase
```
  - Class naming helpers:
```7:13:/Users/user/dysonprotocol2/x/whaleswap/types/constants.go
const ( RootName="whaleswap.dys" ... AuctionClassPrefix = "whaleswap.dys/auction/" ...)
```
```30:31:/Users/user/dysonprotocol2/x/whaleswap/types/constants.go
func AuctionClassID(bidDenom string) string { return AuctionClassPrefix + bidDenom }
```

- Nameservice
  - Per-class policy (set by whaleswap on open):
```37:89:/Users/user/dysonprotocol2/proto/dysonprotocol/nameservice/v1/nameservice.proto
message NFTClassData {
  bool always_listed = 1;
  string valuation_fee_pct = 2; google.protobuf.Duration valuation_period = 8;
  google.protobuf.Duration bid_timeout = 4;
  repeated string allowed_denoms = 5;
  string reject_bid_valuation_fee_percent = 6;
  string minimum_bid_percent_increase = 7;
}
```
  - Per-NFT state used for bidding and valuation:
```91:110:/Users/user/dysonprotocol2/proto/dysonprotocol/nameservice/v1/nameservice.proto
message NFTData {
  bool listed = 1; cosmos.base.v1beta1.Coin valuation = 2; google.protobuf.Timestamp valuation_expiry = 3;
  string current_bidder = 4; cosmos.base.v1beta1.Coin current_bid = 5;
  google.protobuf.Timestamp bid_timestamp = 6; uint64 bid_height = 7; string metadata = 8;
}
```
  - Bid lifecycle states:
```112:120:/Users/user/dysonprotocol2/proto/dysonprotocol/nameservice/v1/nameservice.proto
enum BidStatus { ... BID_ACTIVE=1; BID_OUTBID=2; BID_ACCEPTED=3; BID_REJECTED=4; BID_CLAIMED=5; }
```

### Lifecycle (state machine)
- OpenAuction (seller)
  - Validates sell>0, both denoms solid and different; escrows `sell` to whaleswap module; ensures `whaleswap.dys` root; creates/updates NFT class `whaleswap.dys/auction/{bid_denom}`; sets policy (always_listed, valuation_fee_pct, valuation_period, bid_timeout, minimum_bid_percent_increase, allowed_denoms={bid_denom}); mints NFT id = zero-padded auction_id to seller; indexes AuctionRecord; emits EventAuctionCreated.
```55:91:/Users/user/dysonprotocol2/x/whaleswap/keeper/msg_auction.go
// Save class + set policy knobs + allowed_denoms
...
```
```93:118:/Users/user/dysonprotocol2/x/whaleswap/keeper/msg_auction.go
// Mint NFT to seller; record AuctionRecord; write reverse indexes
...
```
- Bidding (participants; nameservice)
  - PlaceBid escrows bid in nameservice, refunds prior bidder, enforces allowed denom and min increase, updates NFTData.current_bid/current_bidder/bid_timestamp; tracks BidRecord status transitions (ACTIVE→OUTBID).
- Seller accepts or rejects
  - AcceptBid (owner): pays owner from escrowed bid, transfers NFT to bidder, sets valuation to bid, marks bid ACCEPTED.
  - RejectBid (owner): refunds bidder, enforces new valuation ≥ min% over current bid, charges reject fee to community pool, clears bid, sets new valuation/expiry; marks bid REJECTED.
- Bidder claims after timeout
  - ClaimBid (bidder): after class bid_timeout from bid_timestamp, pays owner, transfers NFT to bidder, sets valuation to bid; marks bid CLAIMED.
- RedeemAuction (NFT owner)
  - Owner-only; requires no `current_bidder`; pre-checks whaleswap escrow ≥ sell; sends escrowed `sell` to caller, burns NFT, removes indexes/record, emits EventAuctionRedeemed. If sale happened (current owner != original seller), records a whaleswap Trade for unified history.
```125:176:/Users/user/dysonprotocol2/x/whaleswap/keeper/msg_auction.go
// Authorize by current NFT owner; require no active bid; release escrow; burn NFT; delete indexes
...
```
```178:209:/Users/user/dysonprotocol2/x/whaleswap/keeper/msg_auction.go
// If owner changed and valuation set, record Trade with auction_id
...
```

### Queries and indexing
- Single and paginated listings:
```27:56:/Users/user/dysonprotocol2/x/whaleswap/keeper/query_auctions.go
// Uses AuctionsBySellBid / AuctionsByBidSell reverse indexes with pagination
...
```
- Additional: `AuctionsBySeller`, `AuctionByNFT`, and a price-range scan endpoint.

### How modules connect
- Whaleswap escrows the sell coin and anchors the auction to an NFT in nameservice.
- Nameservice governs bidding/valuation/timing via per-class policy and per-NFT state; funds flow (bid escrow/refund/payout) occur in nameservice during bid actions.
- Final settlement of the sell asset occurs in whaleswap via RedeemAuction by whoever owns the NFT at that time; whaleswap burns the NFT and optionally records a Trade for the sale.

- Simplicity note: There’s no explicit “close/cancel” message; “redeem with no active bid” acts as close/cancel (returns the escrow to the current owner and deletes the auction).

- Class identity: One auction class per bid denom: `whaleswap.dys/auction/{bid_denom}` ensures bids are constrained to that denom.

- Authorization: Whaleswap asserts `whaleswap.dys` root resolves to the whaleswap module for class ops; RedeemAuthorization is current NFT owner.

- Invariants:
  - Redeem is blocked when there is an active bid.
  - Allowed denoms for bids are restricted to the configured `bid_denom`.
  - Escrow must be present in whaleswap module or Redeem fails.

- Tests: CLI tests cover open, bid policy, NFT transfer and redeem, redeem blocked with active bid, seller/seller-index queries.

- Discoverability: Queries by (sell,bid), by seller, by NFT id; price-range query exists but currently acts as a scan placeholder.

- Improvements (optional):
  - Finish “effective price” filter in `AuctionsByPairPriceRange`.
  - Consider an explicit CancelAuction that burns NFT and returns escrow if no active bid, as a UX affordance over Redeem naming.

- Short answers
  - Data models: `AuctionRecord` (whaleswap), `NFTClassData`/`NFTData`/`BidRecord` (nameservice); indexes in whaleswap by (sell,bid) and (bid,sell).
  - Lifecycle: open (escrow + NFT + policy) → bids (nameservice) → accept/reject/claim (nameservice) → redeem (whaleswap) → burn + optional trade record.

- Summary of findings
  - Whaleswap uses nameservice NFTs as auction “tickets” and policy enforcers; nameservice handles bidding logic/escrows for bids; whaleswap escrows the item for sale and releases it on redeem; ownership of the NFT determines who can redeem; trades are recorded on redeem when a sale occurred.