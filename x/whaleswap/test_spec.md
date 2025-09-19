## Whaleswap test plan (CLI, Swagger API, Dyslang)

### Scope

- Validate x/whaleswap end-to-end for three feature areas:
  - AMM: pools (create/update), LP (add/remove), swap, owner gating, bands, fees
  - Orderbook: make/take/cancel, liquid mode Pfand, indexes and queries
  - Auctions: open/redeem, NFT class policy, allowed denoms, reverse indexes
- Exercise three surfaces for each area:
  - CLI (autocli): dysond tx/query whaleswap
  - Swagger API (gRPC-Gateway): HTTP GET/POST against REST endpoints
  - Dyslang scripts: call whaleswap Msg/Query via _msg/_query

### Test harness and conventions

- Use existing pytest infrastructure and fixtures from tests/conftest.py:
  - chainnet: bootstraps network; returns dysond command runner per-chain
  - generate_account, faucet: account creation and funding
  - api_address: REST host:port for Swagger tests
- Do not use time.sleep(); rely on dysond query wait-tx and poll_until_condition
- Let errors bubble up; use plain asserts and pytest.raises where needed
- Prefer small, focused tests that assert one behavior at a time
- For event-derived IDs, parse tx result events with type:
  - dysonprotocol.whaleswap.v1.EventPoolCreated → pool_id
  - dysonprotocol.whaleswap.v1.EventOfferCreated → offer_id
  - dysonprotocol.whaleswap.v1.EventAuctionCreated → auction_id

### File layout

- tests/whaleswap/
  - test_amm_cli.py
  - test_amm_api.py
  - test_amm_script.py
  - test_orderbook_cli.py
  - test_orderbook_api.py
  - test_orderbook_script.py
  - test_auction_cli.py
  - test_auction_api.py
  - test_auction_script.py

### Shared helpers (patterns)

- Funding and keys:
```python
dysond = chainnet[0]
[name, addr] = generate_account("user")
faucet(addr, amount=1_000_000)
```

- Wait for tx success:
```python
tx = dysond("tx", "whaleswap", "create-pool", "--coin-a", "1000udys",
            "--coin-b", "500ufoo", "--from", name)
assert tx.get("code", 1) == 0, tx
```

- Extract ID from events:
```python
pool_evs = [e for e in tx.get("events", []) if e.get("type") == "dysonprotocol.whaleswap.v1.EventPoolCreated"]
pool_id = int([a for e in pool_evs for a in e.get("attributes", []) if a.get("key") == "pool_id"][0]["value"])
```

- REST base URL in tests:
```python
base = f"http://{api_address['host']}:{api_address['port']}"
```

---

## AMM

### CLI tests (test_amm_cli.py)

- CreatePool (v2 constant product):
  - create with --coin-a, --coin-b, optional --fee-pct
  - assert event pool_id and query pool returns canonical denom order (denomA < denomB)
  - shares minted to creator: bank balance of shares_denom > 0

- CreatePool with band (v3 concentrated):
  - add --min-price and --max-price bands
  - reject if initial price outside band

- UpdatePoolConfig (owner-only):
  - non-owner update fails; majority owner (>50% shares) update succeeds
  - fee and band changes validated; current price must remain within new band

- AddLiquidity (owner-only):
  - v2: ratio-preserving join; excess refund present; minted shares > 0
  - v3: refunds one side to match ΔL; post-op price within band

- RemoveLiquidity:
  - v2: proportional exit; v3: band-aware outputs; post-op price within band

  - PoolSwap (single pool only):
  - v2 and v3 paths; amount out > 0; post-op price within band; out denom matches
  - To route across multiple pools, chain multiple PoolSwap msgs in one tx or call the module multiple times from a script

Example CLI:
```bash
dysond tx whaleswap create-pool --coin-a=1000udys --coin-b=500ufoo --fee-pct=0.003 --from alice
dysond tx whaleswap create-pool --coin-a=1000udys --coin-b=500ufoo \
  --min-price=1udys,2ufoo --max-price=1udys,3ufoo --from alice
dysond tx whaleswap add-liquidity --pool-id=1 --amount1=200udys --amount2=100ufoo --from alice
dysond tx whaleswap remove-liquidity --pool-id=1 --shares=50 --from alice
dysond tx whaleswap swap --pool-id=1 --input=100udys --minimum-out-amount=50 --out-denom=ufoo --from bob
```

### Swagger API tests (test_amm_api.py)

- GET pool by id:
```bash
curl "$BASE/dysonprotocol/whaleswap/v1/pools/1"
```

- GET pools with pagination:
```bash
curl "$BASE/dysonprotocol/whaleswap/v1/pools?pagination.limit=50"
```

- Assert JSON fields: coinA/coinB, shares_denom, fee_pct, min_price/max_price, num_trades

### Dyslang script tests (test_amm_script.py)

- Upload a small script that wraps whaleswap Msgs via _msg:
```python
code = '''
from dys import _msg

def amm_create(denom_a, amt_a, denom_b, amt_b):
    return _msg({
        "@type": "/dysonprotocol.whaleswap.v1.MsgCreatePool",
        "creator": "${SIGNER}",
        "coin_a": {"denom": denom_a, "amount": str(amt_a)},
        "coin_b": {"denom": denom_b, "amount": str(amt_b)}
    })
'''
```
- Execute amm_create via tx script exec; assert tx success and pool exists via query
- Add/remove liquidity and swap using similar wrappers; assert events and pool state deltas

---

## Orderbook

### CLI tests (test_orderbook_cli.py)

- MakeOffer (normal):
  - have=solid, want=solid; escrow in module; EventOfferCreated; OffersByOwner shows status=open

- MakeOffer (liquid):
  - have is liquid L(S); optionally update params.pfand_per_offer > 0 via UpdateParams (authority)
  - locks pfand; EventPfandLocked emitted

- TakeOffer (batch):
  - settle base want first, then liquid want burn if needed
  - maker-have liquid: require maker provides L(have) to burn; pfand released on close (EventPfandReleased)
  - maker-have normal: release escrowed base have to taker
  - Offer status transitions to closed when remaining_units == 0; reverse indexes removed

- CancelOffer:
  - maker can cancel open; third-party can cancel liquid offer if maker lacks ≥1 unit liquid have; pfand released to closer

Example CLI:
```bash
dysond tx whaleswap make-offer --have=100udys --want=50ufoo --from alice
dysond tx whaleswap convert-to-liquid --denom=udys --amount=100 --from alice
dysond tx whaleswap make-offer --have=100whaleswap.dys/coins/udys --want=50ufoo --from alice
dysond tx whaleswap take-offer --trades='[{"offer_id":1,"take_units":"10"}]' --from bob
dysond tx whaleswap cancel-offer --offer-id=2 --from bob
```

### Swagger API tests (test_orderbook_api.py)

- GET offer by id:
```bash
curl "$BASE/dysonprotocol/whaleswap/v1/offers/1"
```

- List offers with optional filters:
```bash
curl "$BASE/dysonprotocol/whaleswap/v1/offers?have_denom=udys&want_denom=ufoo&pagination.limit=100"
```

- OffersByOwner with optional status:
```bash
curl "$BASE/dysonprotocol/whaleswap/v1/offers/by-owner?owner=$ADDR&status=open"
```

- Trades:
```bash
curl "$BASE/dysonprotocol/whaleswap/v1/trades/by-offer?offer_id=1&pagination.limit=50"
curl "$BASE/dysonprotocol/whaleswap/v1/trades/by-taker?taker=$ADDR&pagination.limit=50"
```

Assertions:
- Correct filtering, stable pagination, and presence/absence in reverse indexes after close/cancel

### Dyslang script tests (test_orderbook_script.py)

- Script wrappers:
```python
code = '''
from dys import _msg

def mk_offer(have_denom, have_amt, want_denom, want_amt):
    return _msg({
        "@type": "/dysonprotocol.whaleswap.v1.MsgMakeOffer",
        "maker": "${SIGNER}",
        "have": {"denom": have_denom, "amount": str(have_amt)},
        "want": {"denom": want_denom, "amount": str(want_amt)}
    })
'''
```
- Execute mk_offer; query offer; then take/cancel via wrappers and assert status, trades, and pfand events

---

## Auctions

### CLI tests (test_auction_cli.py)

- OpenAuction:
  - provide --sell=<amountdenom> and --bid-denom
  - assert NFT minted class whaleswap.dys/auction/{bid_denom} to seller; record stored; reverse indexes set

- RedeemAuction:
  - when no bidder: burns NFT, releases sell escrow to caller, deletes record and reverse indexes
  - when bidder exists: redeem must fail with ErrInvalidRequest

Example CLI:
```bash
dysond tx whaleswap open-auction --seller=$(dysond keys show alice -a) --bid-denom=ufoo --sell=100udys --from alice
dysond tx whaleswap redeem-auction --auction-id=1 --from alice
```

### Swagger API tests (test_auction_api.py)

- GET single auction:
```bash
curl "$BASE/dysonprotocol/whaleswap/v1/auctions/1"
```

- List auctions with filters:
```bash
curl "$BASE/dysonprotocol/whaleswap/v1/auctions?sell_denom=udys&bid_denom=ufoo&pagination.limit=50"
```

Assertions:
- After redeem, GET returns not found; filtered listings exclude redeemed id in both reverse indexes

### Dyslang script tests (test_auction_script.py)

- Script wrappers to open and redeem auctions:
```python
code = '''
from dys import _msg

def open_auc(seller, bid_denom, sell_denom, sell_amt):
    return _msg({
        "@type": "/dysonprotocol.whaleswap.v1.MsgOpenAuction",
        "seller": seller,
        "bid_denom": bid_denom,
        "sell": {"denom": sell_denom, "amount": str(sell_amt)}
    })
'''
```
- Execute open_auc; assert class policy/allowed denoms via nameservice queries where applicable; then test redeem path with/without bidder

---

## Negative and edge cases (spread across suites)

- AMM: attempt non-owner LP; band violations on add/remove/swap; invalid fee_pct
- Orderbook: invalid denoms; want must be solid; insufficient funds; liquid close index cleanup
- Auctions: sell==bid denom rejected; redeem with active bidder rejected

---

## Pagination and sorting checks

- Use pagination.limit/offset and page_reverse to verify stable orderings for:
  - Pools, Offers (with/without filters), TradesByOffer/Taker, Auctions (with/without filters)
  - Ensure non-overlapping pages and ascending/descending as requested

---

## Execution notes

- CLI commands use the chainnet run_command wrapper; it appends --yes and a generous --gas by default
- Prefer dysond query wait-tx to gate on transaction finality before querying state
- For REST, use api_address fixture to form base URL; prefer requests over external tools

---

## Out-of-scope for MVP

- ComposeOperations is removed; no tests planned
- Cross-chain behaviors are out of scope


