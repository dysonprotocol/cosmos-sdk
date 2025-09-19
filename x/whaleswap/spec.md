## Whaleswap module (x/whaleswap) – Specification

### 1. Scope and goals

- Port Whaleswap from dyslang scripts (`whaleswap/amm.py`, `orderbook.py`, `auction.py`) to a native Cosmos SDK module.
- Preserve semantics and event shapes where practical; simplify where possible for safety and maintainability.
- Integrate with existing modules: `nameservice`, `nft`, `bank`, `params`.

Non-goals (initial cut): on-chain scripting hooks, cross-chain.


### 2. External dependencies and authorities

- Bank keeper: move funds between user accounts and the module account.
- Nameservice keeper: mint/burn custom denoms, set NFT class policies, set metadata.
- NFT keeper: mint/send/burn NFTs.
- Params keeper: module params.
- Module account: `whaleswap` (escrow, fee accrual, mint/burn authority via nameservice).
- Authority over `whaleswap.dys` root: the module account must be the destination/owner so it can mint/burn/move custom denoms and set class policies.


### 3. Denoms and notation

- Solid denom S: a base on-ledger denom like `DYS_ROOT/foo`.
- Liquid denom L(S): wrapper minted by Whaleswap for S, defined as `whaleswap.dys/coins/<S>` (no encoding).
- Shares denom for pools: `whaleswap.dys/pools/{pool_id}`.
- Price convention (AMM): P = reserve2 / reserve1 ("price of coin2 in coin1 units").


### 4. Module parameters

- pfand_per_offer: sdk.Coin. Locked when creating a liquid offer; released on close/cancel per rules.
- auction knobs (strings matching nameservice types/validation):
  - valuation_fee_pct (Dec in [0,1])
  - valuation_period (duration string)
  - bid_timeout (duration string)
  - min_bid_percent_increase (Dec in [0,1])

Notes:
- Nameservice `mint_fee_per_coin` remains the source of truth for mint fees; however, when minting to a module account, the nameservice skips fee collection. Whaleswap mints shares and liquid wrappers to the `whaleswap` module account and then forwards them to users, so no mint fee is charged along this path. Direct mints to non-module destinations still require the fee.


### 5. State model (keys and indexes)

- Counters (uint64):
  - `counter|pools`, `counter|offers`, `counter|trades`, `counter|auctions`.

- AMM Pools: `pools/{id}` → Pool
  - id (uint64)
  - coin1_denom, coin2_denom (string; coin1 < coin2 lexicographically)
  - reserve1, reserve2 (sdk.Int)
  - total_shares (sdk.Int)
  - shares_denom (string)
  - fee_pct (math.Dec, 0 ≤ fee < 1)
  - min_price, max_price (math.Dec; inclusive bounds on P = R2/R1)
  - block_height (int64), created (time), updated (time), num_trades (uint64)

- Orderbook Offers: `oid|{id}` → OfferData
  - Maker, status {open|closed|cancelled}, have/want coins, remaining, unit ints, remaining_units, pfand_locked
  - Indexes:
    - `maker|{maker}|status|{status}|id|{id}` → `oid|{id}`
    - Price trees (lexicographic):
      - `w|{want}|h|{have}|{price_key}|oid|{id}`
      - `h|{have}|w|{want}|{price_key}|oid|{id}`

- Trades: `tid|{id}` → Trade; indexes:
  - `taker_trade|{taker}|tid|{id}` → `tid|{id}`
  - `offer_trade|oid|{offer_id}|tid|{id}` → `tid|{id}`

- Auctions:
  - Primary: `AuctionsMap[id]` → AuctionRecord {class_id, nft_id, sell (coin), bid_denom, seller}
  - Reverse indexes (collections-based):
    - `(sell_denom, bid_denom, auction_id)` → `auction_id`
    - `(bid_denom, sell_denom, auction_id)` → `auction_id`
  - NFT class: `whaleswap.dys/auction/{bid_denom}` (one class per bid denom)


### 6. AMM – owner-only LP with price band and fee

Design updates (required):
- Mode A (no price range): classic constant product (Uniswap v2) with fee
  - If the owner does not specify a price range, the pool operates with invariant x·y = k.
  - Liquidity is diffuse across all prices; fee is applied to input.
- Mode B (price range set): concentrated liquidity (Uniswap v3-style) with a single band per pool
  - The owner specifies an inclusive price band [min_price, max_price] over P = R2/R1.
  - Within the band the pool uses concentrated liquidity math; outside the band swaps halt and liquidity sits fully in one asset.
- Each pool has a fee percentage `fee_pct` applied to swaps (0 ≤ fee < 1).
- Owner definition: the pool "owner" at any time is the address that holds strictly more than 50% of the outstanding pool shares.
  - Enforcement: before any owner-privileged action (Add/Remove liquidity, UpdatePoolConfig), the module computes majority-of-shares for the pool's `shares_denom` by iterating balances (or using a cached value with verification) and requires the signer to be the current majority holder.
  - The module may cache `owner_majority_cached` on mints/burns/known transfers but must re-validate during privileged ops to avoid stale state.
- Anyone can swap as long as the resulting price stays within the configured range.
- The pool owner can change pool config (fee_pct, min_price, max_price) at any time.
- No one can join someone else's pool (owner-only liquidity). Others may hold/receive shares via transfers, but only the current majority holder may add/remove liquidity.

Pool creation
- Msg: CreatePool(coinA, coinB, min_price, max_price, fee_pct)
  - Caller becomes owner.
  - Canonicalize: coin1_denom < coin2_denom; reorder amounts accordingly.
  - Move both coin amounts caller → module; initialize reserves.
  - total_shares = initial_shares (e.g., 100000) minted to owner; shares denom `whaleswap.dys/pools/{pool_id}`.
  - Validate 0 ≤ fee_pct < 1 and 0 ≤ min_price ≤ max_price; initial P within [min,max].

Owner adds/removes liquidity (only owner)

Owner is defined as the address that holds strictly more than 50% of the outstanding pool shares. Only owner can add liquidity. Anyone can remove liquidity as long as the resulting price stays within the configured range.

Mode A (v2, no price range)
- Msg: AddLiquidity(pool_id, amount1, amount2)
  - Proportional join to current reserves.
  - Refund any excess to owner.
  - Mint shares: shares = min(floor(added1 * total_shares / R1), floor(added2 * total_shares / R2)).
  - Update reserves, total_shares.
  

- Msg: RemoveLiquidity(pool_id, shares)
  - Proportional exit: out1 = floor(shares * R1 / total_shares), out2 analogously.
  - Burn shares; send outs; update reserves.

Mode B (v3-style, price range set)
- Notation: P = R2/R1, s = sqrt(P). Let sa = sqrt(min_price), sb = sqrt(max_price), sp = sqrt(current_price). Liquidity L is constant within [sa, sb].
- Given a desired add (amount1 for denom1, amount2 for denom2), the effective L added is:
  - If sp ≤ sa (below range): amount1 contributes, amount2 ignored → L = amount1 * (sa * sb) / (sb - sa)
  - If sp ≥ sb (above range): amount2 contributes, amount1 ignored → L = amount2 / (sb - sa)
  - If sa < sp < sb (within range):
    - L0 = amount1 * (sp * sb) / (sb - sp)
    - L1 = amount2 / (sp - sa)
    - L = min(L0, L1), refund any excess component to owner.
- Reserves implied by (L, sp) inside the band evolve with swaps; we store R1/R2 directly and ensure they remain consistent with L.
- Removing liquidity by ΔL returns amounts using:
  - If sp within [sa, sb]:
    - out1 = floor(ΔL * (sb - sp) / (sp * sb))
    - out2 = floor(ΔL * (sp - sa))
  - If sp ≤ sa: out1 = floor(ΔL * (sb - sa) / (sa * sb)), out2 = 0
  - If sp ≥ sb: out1 = 0, out2 = floor(ΔL * (sb - sa))
- In all cases, enforce post-condition price remains within [min,max].

Swaps (any user)
- Msg: PoolSwap(route_ids, input_coin, minimum_out_amount, out_denom)
  - For each hop, apply based on pool mode:
    - Mode A (v2): constant product with fee on input.
      - k = R1*R2; effective_in = dx * (1 - fee_pct).
      - out = R2 - ceil(k / (R1 + effective_in)) (or symmetric for coin2 input).
      - Update reserves; enforce price band if configured.
    - Mode B (v3-style): concentrated liquidity within [sa, sb].
      - Use sqrt-price integration with constant liquidity L.
      - For token1→token2 swap (input denom1, output denom2), price moves up: with fee on input, let dxe = dx*(1-fee_pct).
        - Move from sp to sp' within [sa, sb] such that dxe = L * (1/sp - 1/sp').
        - out = floor(L * (sp' - sp)). If input exhausts before hitting band edge, stop; else stop at boundary.
      - For token2→token1, symmetric with price moving down: dye = dy*(1-fee_pct), dxe = floor(L * (1/sp' - 1/sp)).
      - Reject if resulting price exits band.
  - After final hop, require out_denom match and amount ≥ minimum_out_amount; send to caller.

Pool configuration updates (only owner)
- Msg: UpdatePoolConfig(pool_id, fee_pct?, min_price?, max_price?)
  - Optional fields; validate 0 ≤ fee_pct < 1 and 0 ≤ min_price ≤ max_price.
  - Ensure current mid-price remains within new band.

Ownership
- Ownership is implicit from share distribution. There is no explicit SetPoolOwner message.
- Ownership may change when share transfers or liquidity mint/burn cause a different address to cross the 50% threshold. 

Events
- pool_created, poolupdate, pool_liquidity_added, pool_liquidity_removed, pool_swap.

Invariants
- total_shares supply (bank) equals stored total_shares.
- Reserves non-negative; price band respected after each state change.
- Shares_denom unique per pool.
- Majority owner checks: privileged ops must verify signer holds >50% of `shares_denom` at execution time.

Notes
- Mode selection is implicit: if min_price/max_price are unset (or represent [0, +∞)), behavior is Mode A; otherwise Mode B.


### 7. Liquid conversions (wrapping)

Msgs
- ConvertToLiquid(denom, amount)
  - Move `amount` of solid denom caller → module (escrow backing).
  - Mint L(denom) to the module account (fee skipped due to module destination) and forward to caller.

- ConvertToSolid(liquid_denom, amount)
  - Move liquid from caller → module; burn; send solid to caller; require module escrow ≥ amount.

Notes
- Due to module authority and nameservice behavior, mint fees are skipped for module-destination mints and thus are not required for ConvertToLiquid. Backing is always enforced and must equal or exceed burned liquid on ConvertToSolid.


### 8. Orderbook DEX

Msgs
- MakeOffer(have, want)
  - Normal: have is solid; escrow have in module (bank send user→module). No pfand.
  - Liquid: have is liquid L(S); require maker holds ≥ pfand_per_offer; move pfand maker→module; no have attachments.

- TakeOffer(trades[])
  - Batch settlement; for each trade:
    - Taker pays solid want first (escrow), remainder via L(want) moved to module and burned.
    - Maker-have liquid: burn L(have) moved from maker; send solid have to taker; release pfand to taker on close.
    - Maker-have normal: send solid have from module escrow to taker.
  - Update offer remaining, status; record trades; emit events.

- CancelOffer(offer_id)
  - Maker can cancel open; third-party may cancel liquid offers if maker lacks ≥ 1 unit of L(have); pfand sent to closer.

Indexes and queries
- Offers primary: `OffersMap[id]` → OfferData
- Reverse indexes:
  - `(have_denom, id)` → `id`
  - `(want_denom, id)` → `id`
  - Normalized pair+price (single direction only): `(low|high, price_dec, id)` → `id`, where `low = min(have, want)`, `high = max(have, want)`, and `price_dec = amount(high) / amount(low)` as a cosmos.Dec string; this yields stable lexical ordering and avoids duplicate entries.
- Trades primary/indexes: by `offer_id`, by `taker`


### 9. Auctions

Msgs
- OpenAuction(sell, bid_denom)
  - Move explicit solid `sell` coin from seller → module (escrow).
  - Create/upsert NFT class `whaleswap.dys/auction/{bid_denom}`.
  - Set class policy from whaleswap params: always_listed=true; valuation_fee_pct; valuation_period; bid_timeout; minimum_bid_percent_increase.
  - Set allowed_denoms to only `bid_denom`.
  - Mint NFT with id equal to the allocated `auction_id` (zero-padded) to seller.
  - Store `AuctionRecord` keyed by `auction_id`.
  - Populate reverse indexes:
    - (sell_denom, bid_denom, auction_id) → auction_id
    - (bid_denom, sell_denom, auction_id) → auction_id

- RedeemAuction(auction_id)
  - Only NFT owner; only if no current bidder; send escrowed sell denom back; burn NFT.
  - Delete primary `AuctionRecord` and both reverse index entries.


### 10. Advanced composed execution (atomic multi-op match-and-settle)

This section was removed. The module will not implement composed execution in the MVP.


### 11. Queries (gRPC + CLI)

- Pools: Get(pool_id), List(pagination). Return reserves, fee_pct, band, owner, timestamps, num_trades.
- Offers: Get(id), ByOwner(owner,status), Offers(have_denom?, want_denom?) with pagination.
  - ByOwner requires `owner`; when `status` provided, the `(owner,status,id)` index is used; otherwise a filtered scan is used.
  - Offers list prefers reverse indexes when filters are provided:
    - both have and want: use normalized `(low|high, price, id)` index and verify exact direction
    - only have: use `(have, id)` index and optionally filter `want`
    - only want: use `(want, id)` index and optionally filter `have`
    - neither: full scan of primary map
- Trades: ByOffer(offer_id), ByTaker(addr).
- Auctions: Get(id), List with optional filters (sell_denom?, bid_denom?) and pagination.
  - If both filters: use (sell,bid,auction_id) index.
  - If only sell_denom: use (sell,*,auction_id) index.
  - If only bid_denom: use (bid,*,auction_id) index.
  - If neither: paginate primary map.
- Params: Get.


### 12. Genesis

- Contents: params, counters, pools, offers, trades, auctions.
- Validate: denoms format, params ranges, unique shares denom per pool, no duplicate indexes, counters ≥ max id in state.
- Export/import symmetric.


### 13. Errors and validation (high level)

- Denoms must be valid; coin amounts must be > 0 (except zero in specific system fields).
- AMM swap: reject output ≤ 0, reserve depletion, price band violations.
- Add/remove liquidity: owner-only; must keep price within band; shares > 0.
- Orderbook: forbid liquid attachments at make; want must be solid; all computed amounts integral.
- Liquid conversions: enforce fee sufficiency; escrow backing checks.


### 14. Math and rounding policy

- Prefer sdk.Int storage for amounts; use math.Dec for fee_pct and price bounds.
- AMM per-hop swap: `out = R_out - ceil(k / (R_in + effective_in))` with `effective_in = in * (1 - fee_pct)`.
- Shares mint/burn: floor for proportional calculations; reject if both outs floor to 0.


### 15. Events (selected)

- pool_created(pool_id), poolupdate(pool_id), pool_swap(pool_id), pool_liquidity_added(pool_id), pool_liquidity_removed(pool_id), pool_owner_changed(pool_id)
- offer_created(offer_id), offer_taken(offer_id), offer_cancelled(offer_id), pfand_locked(amount), pfand_released(amount)
- auction_created(auction_id), auction_redeemed(auction_id)


### 16. Testing plan (outline)

- Unit tests: AMM math (ceil/floor, price band enforcement, fee application), orderbook settlement paths, auctions, conversions.
- E2E tests (pytest):
  - Liquid convert in/out with mint fees.
  - AMM owner-only add/remove; swap inside band; reject outside band; fee accrual observed.
  - Orderbook: normal vs liquid offers; take (base+liquid mix); cancel eligibility; pfand release paths.
  - Auctions open/redeem with class policy setup.


### 17. Migration notes from scripts

- No "attachments"; module explicitly moves funds via bank keeper.
- Preserve major event names for minimal test diffs.
- Price band and fee are new vs. script AMM; tests must reflect updated constraints.

Module authority differences vs scripts (important):
- Fee semantics: scripts required attached `udys` to pay nameservice mint fees. The module mints to its own account and then forwards coins, so nameservice skips fees in these paths. Direct user-facing mints (if any) would still require fees.
- Liquid denom format: the module uses a direct prefix `whaleswap.dys/coins/<solid>` instead of base64url encoding.
- Shares minting: initial and incremental share mints occur to the module account first (no fee), then are sent to LPs.


### 18. Future extensions (non-blocking)

- Concentrated liquidity per tick ranges; multi-fee tiers.
- Pool pause/guardians; TWAP oracles.
- Batch auctions integrated with AMM inventory.


# TODO
### What’s left per spec (prioritized)

- AMM (files: `x/whaleswap/keeper/msg_liquidity.go`, `msg_pool_swap.go`, `keeper.go`, `spec.md`)
  - Enforce price band post-AddLiquidity and post-RemoveLiquidity. (done)
  - Concentrated-liquidity math (sqrt-price, L-based) when a price range is set; current implementation is v2 with band checks only.
  - Emit consistent poolupdate events on all reserve mutations (we already do most).
  - Keep integer-first math; ensure single ctx/time read per handler (mostly done).

- Orderbook DEX (files: `x/whaleswap/keeper/msg_orderbook.go`, `query_offers.go`, `query_trades.go`, `keeper.go`)
  - Emit missing events: pfand_locked on MakeOffer (liquid), pfand_released on close/cancel, offer_cancelled. (done)
  - Implement queries with pagination:
    - OffersByOwner(owner,status?) (done)
    - OffersByHave(have_denom) (done)
    - OffersByWant(want_denom) (done)
    - TradesByOffer(offer_id) (done)
    - TradesByTaker(taker) (done)
  - Indexing: add secondary indexes (owner+status, have/want) via `collections` for performance; optionally start with filtered scan for MVP.

- Liquid conversions (files: `x/whaleswap/keeper/msg_convert.go`, `keeper.go`)
  - Fee semantics updated: module mints to module account (fee skipped) then forwards. Documented above. (done)

- Auctions (files: `x/whaleswap/keeper/msg_auction.go`, `query_auctions.go`, `keeper.go`)
  - Implement MsgOpenAuction (escrow exactly one solid denom; set class/policy via nameservice; mint NFT to seller; record).
  - Implement MsgRedeemAuction (only NFT owner; only if no current bidder; burn NFT; release escrow).
  - Queries: Auction(id), AuctionByPair(sell,bid).
  - Events: auction_created, auction_redeemed.
  - Keeper state: add `AuctionSeq`, `AuctionsMap` (and pair index) via `collections`.

- Queries split/localization (files: `x/whaleswap/keeper/query_*.go`)
  - Move all query handlers into per-query files (we split Pools; finish Offers/Trades/Auctions).

- Genesis (files: `x/whaleswap/genesis.go`, `x/whaleswap/keeper/genesis.go`)
  - Export/import params, counters (pool/offer/trade/auction seq), pools, offers, trades, auctions.
  - Validate denoms, unique shares, counters ≥ max ids.
  - Add invariants where applicable.

- Params and defaults (files: `x/whaleswap/types/params.go`, `spec.md`)
  - Ensure sane defaults for `pfand_per_offer` (denom `whaleswap.dys/pfand`, amount 0), auction knobs.
  - Validation already present; ensure doc parity.

- CLI/REST (files: `x/whaleswap/module/module.go`, `client/` commands)
  - Tx and query commands for all msgs/queries (AMM, orderbook, auctions, conversions, params).

- Authority and safety (files: `app_config.go`, `genesis`, docs)
  - Ensure module controls `whaleswap.dys` root at genesis for mint/burn/class ops.
  - Invariants: share supply == bank supply; escrow/pfand correctness.

- Tests/docs (files: `tests/whaleswap/*`, `x/whaleswap/spec.md`, README)
  - Port and adapt existing whaleswap tests to module txs/queries.
  - Add e2e for AMM range checks, orderbook liquid paths, auctions, conversions.
  - Update `spec.md` with final behaviors and parameter notes.

I'll add orderbook events, implement offers/trades queries with basic pagination, enforce price-band checks in AddLiquidity/RemoveLiquidity, and remove the unimplemented stub methods so each query is defined once. Then I'll run lints on the touched files.


- Added orderbook events:
  - Emit EventPfandLocked on MakeOffer (liquid).
  - Emit EventOfferCancelled and EventPfandReleased on CancelOffer; kept existing EventOfferCreated/Taken.

- Enforced price band on LP ops:
  - AddLiquidity and RemoveLiquidity now reject if resulting price leaves [min,max].

- Implemented queries with pagination scans:
  - OffersByOwner(owner,status), OffersByHave(have_denom), OffersByWant(want_denom).
  - TradesByOffer(offer_id), TradesByTaker(taker).
  - Split into query_offers.go, query_trades.go; kept Auction queries stubbed in query_auctions.go.

- Cleaned duplicates:
  - Removed overlapping methods from query_server.go; it now only has Offer and interface binding.

Next: implement auctions (Open/Redeem + queries) and start ComposeOperations.
==================================================
I’ll implement Auctions next: keeper collections for auctions, MsgOpenAuction/MsgRedeemAuction, and queries; then add ComposeOperations scaffolding.
Also, I’ll keep queries split into query_offers.go/query_trades.go and leave auction queries in query_auctions.go until we wire storage.
==================================================
Implemented: Offers/Trades queries now return paginate results; pfand release event on offer close; auction sequence scaffold added to keeper.
Next steps: implement MsgOpenAuction/MsgRedeemAuction + Auction queries; scaffold ComposeOperations.
Spec updated behavior is already met for:
Orderbook events (offer_created/taken/cancelled, pfand_locked/released).
AMM band enforcement on add/remove.
==================================================
Added concentrated-liquidity helpers in keeper.go:
sqrt price, band sqrt, current sqrt price
liquidityForReserves to compute L within [sa,sb]
Implemented v3 math paths:
AddLiquidity: when band set, compute ΔL contribution from dx/dy using sqrt-price formulas; refund excess; approximate shares mint via proportional fallback; enforce band after update (kept existing check).
PoolSwap: when band set, approximate sqrt-price integration to derive out amount using L, sp, [sa,sb]; clamp to band; update reserves; fee applied to input.
==================================================
Here’s what remains to implement to meet the spec.

### AMM (pools)
- Implement concentrated remove-liquidity math
  - Use the L-based formulas for out1/out2 when bands are set (sa/sb/sp), not proportional share exits. Files: `x/whaleswap/keeper/msg_liquidity.go`.
- Map ΔL to shares minted/burned
  - Shares should be derived from ΔL (not proportional fallback); define consistent policy and apply in add/remove. Files: `msg_liquidity.go`.
- Refine concentrated swap integration and edge handling
  - Clamp precisely at band edges, preserve L consistency, and ensure fee treatment matches spec across hops. Files: `msg_pool_swap.go`.
- Emit EventPoolUpdate uniformly on every reserve mutation
  - Ensure one event per mutation path (add/remove/swap). Files: `keeper.go`, `msg_*`.
- Standardize errors
  - Replace remaining fmt.Errorf with `sdkerrors.Wrap/Wrapf`. Files: `msg_liquidity.go`, `msg_pool_swap.go`, others.

### ComposeOperations
- Implement `MsgComposeOperations`
  - Three-phase execution: collect inputs → apply ops internally (TakeOffer/PoolSwap with module escrow bookkeeping) → single final settlement. All-or-nothing. Files: `x/whaleswap/keeper/msg_compose.go` (new), reuse math from existing handlers, keep state updates atomic.

### Genesis
- Full InitGenesis/ExportGenesis
  - Persist/export params, counters (pool/offer/trade/auction seq), pools, offers, trades, auctions.
  - On InitGenesis, set counters ≥ max ID and rebuild reverse indexes:
    - Offers: `(have,id)`, `(want,id)`, `(low|high,price,id)`, `(owner,status,id)`
    - Auctions: `(sell,bid,id)`, `(bid,sell,id)`
  - Files: `x/whaleswap/genesis.go`, `x/whaleswap/keeper/genesis.go`.

### Orderbook DEX
- Mostly done: Make/Take/Cancel, pfand paths, reverse indexes, queries. Add any missing sdkerrors wrapping and ensure index cleanup on all terminal state transitions (already present but double-check). Files: `msg_orderbook.go`, `query_offers.go`, `query_trades.go`.

### Auctions
- Done: Open/Redeem, class policy, bidder check, reverse indexes, queries. Ensure sdkerrors consistency and event emissions. Files: `msg_auction.go`, `query_auctions.go`.

### Wrapping (liquid conversions)
- Align proto with behavior
  - Remove `mint_fee` from `MsgConvertToLiquid` proto (currently still present in `proto/dysonprotocol/whaleswap/v1/tx.proto`) to match keeper logic that mints to module with zero fee and forwards. Regenerate protos, adjust client docs.

### Invariants and authority
- Add invariants (optional but recommended)
  - Shares bank supply == stored; escrow/pfand accounting consistent; auction escrow matches records.
- Ensure `whaleswap.dys` root authority at genesis
  - Module account must control it for mint/burn/class ops.

### CLI/REST and docs/tests
- CLI/REST
  - tx and query commands mirroring msgs/queries (like other modules). Files: `x/whaleswap/module/module.go` and client cmd scaffolding.
- Tests
  - Port `tests/whaleswap/*` to module txs/queries; add e2e for AMM bands, orderbook liquid paths, auctions, conversions. Use `make test PYTEST_ARGS=" --ff --nf -x -s"` as usual.
- Docs
  - Update `x/whaleswap/spec.md` and README with finalized behaviors and parameters.

- I marked the helper work as complete; I’ll keep the concentrated AMM task open while we wire ΔL-based shares and v3 remove math.
==================================================
I'll implement concentrated AMM improvements now: add ΔL↔shares helpers, use ΔL-based shares in AddLiquidity, implement concentrated RemoveLiquidity outputs, and refactor PoolSwap to choose v2 vs v3 paths exclusively. Then I'll run lints.

[1 tool called]

I’m going to implement the concentrated AMM fully:
- Add ΔL-based shares mint/burn in Add/Remove.
- Implement v3 remove math using sqrt-price formulas.
- Refactor PoolSwap to choose v2 vs v3 path exclusively and emit uniform pool update events.
- Then lint the modified files.

[10 tools called]

- Implemented concentrated AMM fully on core paths:
  - AddLiquidity: computes ΔL from dx/dy per band; mints shares via Δshares = floor(ΔL * totalShares / Lcur); refunds excess; persists via updatePool; emits liquidity event.
  - RemoveLiquidity: concentrated exits use ΔL from shares and return amounts using sqrt-price formulas; v2 path unchanged.
  - PoolSwap: clean separation of v3 vs v2; v3 uses sqrt-price integration with clamped band movement; reserves updated directly on pool; uniform updatePool + EventPoolSwap.

- Lints clean on edited files.
==================================================
Replaced remaining fmt.Errorf with sdkerrors.Wrap/Wrapf:
Updated msg_liquidity.go and msg_pool_swap.go to use cosmossdkerrors + sdkerrors.
Added missing imports in msg_pool_swap.go.
All edited files lint clean.
==================================================
[1 tool called]

I'll update the code and spec now: remove the ComposeOperations RPC/messages from tx.proto, delete the keeper stub, and strip the composed-execution section from spec.md. Then I'll fix imports and lints.

[7 tools called]

I'll restore a temporary ComposeOperations stub to satisfy the current generated interface, regenerate protos to remove ComposeOperations, then delete the stub and re-run lints.

[2 tools called]

- Removed ComposeOperations:
  - Deleted RPC and all related messages from `proto/dysonprotocol/whaleswap/v1/tx.proto`.
  - Updated `x/whaleswap/spec.md`: removed composed-execution section, added note it’s not in MVP.
  - Kept a temporary stub in `x/whaleswap/keeper/msg_server.go` to satisfy the current generated interface until you run proto generation. After you run make proto-gen install, we can delete the stub.

- Next step: run proto-gen to drop ComposeOperations from the generated Go interfaces, then I’ll remove the temporary stub.
==================================================
I'll remove the ComposeOperations stub and clean the codec registrations to eliminate any references to removed types. Then I'll run lints.

[4 tools called]

- Removed all ComposeOperations references:
  - Deleted from `proto/dysonprotocol/whaleswap/v1/tx.proto`.
  - Dropped from `x/whaleswap/codec.go` registrations.
  - Removed method from `x/whaleswap/keeper/msg_server.go`.
  - Updated `x/whaleswap/spec.md` to note the feature is not in MVP.

- Build error fixed.
==================================================
- Mint fee field removed from proto; code regenerated and binary builds clean.
- Wrapping flow now matches keeper: mint to module with zero fee, then forward.
==================================================