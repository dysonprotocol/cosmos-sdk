# Whaleswap: CLI quickstart (deposit, withdraw, make, take, cancel)

This guide targets users comfortable with trading/crypto, and explains Whaleswap-specific behavior precisely.

Replace ALL_CAPS placeholders with real values:

- `SCRIPT`: Whaleswap script address (the script owner)
- `EXECUTOR` / `EXECUTOR_NAME`: sender address / key name
- `DYS_ROOT`: a registered Dyson nameservice root (for example, `aliceabcd.dys`)

## Terminology (Whaleswap)

- `solid denom S`: a normal chain coin denom like `DYS_ROOT/usd` or `DYS_ROOT/abc`. These are the “real” on-ledger tokens held by accounts or `SCRIPT`.
- `liquid denom L(S)`: Whaleswap’s liquid form of `S`, defined as `DYS_NAME/coins/<base64url(S)>`. Use `quote_liquid_denom(S)`.
- `pfand`: a deposit token `DYS_NAME/pfand` locked when making liquid offers; returned to whoever closes the offer (maker, taker on fill, or third party if maker can no longer fund the offer).
- `have`: what the maker delivers to a taker on fill (maker’s out leg)
- `want`: what the maker receives from the taker on fill (maker’s in leg)
- `normal offer`: `have` is a solid denom and must be escrowed by attaching a `MsgSend` of `have` to `SCRIPT` during `make`
- `liquid offer`: `have` is a liquid denom `L(S)`; maker locks `pfand` at `make`. On `take`, `L(S)` is burned and `S` is released to the taker
- `attached messages`: extra messages included in a transaction via `--attached-message` flags; used to escrow funds to the script (e.g., `MsgSend`)

### Solid vs Liquid

- `solid` = native ledger tokens under the `nameservice` (e.g., `DYS_ROOT/foo`).
- `liquid` = Whaleswap-minted wrappers `L(S)` that are always 1:1 redeemable for `S`.
- Conversion:
  - `deposit(S, n)`: user sends `n` units of `S` (plus a small `udys` mint fee) to `SCRIPT`; `SCRIPT` mints `n` units of `L(S)` to the user.
  - `withdraw(L(S), n)`: user returns/burns `n` units of `L(S)`; `SCRIPT` releases `n` units of `S` to the user.
- Invariant: balances of `S` held by `SCRIPT` back the circulating `L(S)` supply exactly.

Minting coins (including shares/pfand) requires an explicit `mint_fee` in `udys` equal to `ceil(units * mint_fee_per_coin)`. The script provides `quote_mint_fee(amount)` and verifies attached `udys` cover it.

## 0) Helpers

Quote required `udys` for minting `N` units (ceiling):
```bash
dysond query script run \
  --script-address SCRIPT \
  --executor-address EXECUTOR \
  --function-name quote_mint_fee \
  --args '["100"]' -o json
```
Quote liquid denom for a solid denom `S`:
```bash
dysond query script run \
  --script-address SCRIPT \
  --executor-address EXECUTOR \
  --function-name quote_liquid_denom \
  --args '["DYS_ROOT/coinS"]' -o json
```

Attach bank sends with `--attached-message` (repeatable). Example: send `100` `udys` to `SCRIPT`:
```bash
--attached-message '{"@type":"/cosmos.bank.v1beta1.MsgSend","from_address":"EXECUTOR","to_address":"SCRIPT","amount":[{"denom":"udys","amount":"100"}]}'
```

## 1) Convert to liquid (`S` → `L(S)`)

- Attach `S` amount to `SCRIPT`
- Attach `udys` ≥ `quote_mint_fee(S_amount)`
- Execute `convert_to_liquid(S, amount)`

```bash
dysond tx script exec \
  --script-address SCRIPT \
  --function-name convert_to_liquid \
  --args '["DYS_ROOT/coinS","100"]' \
  --from EXECUTOR_NAME \
  --attached-message '{"@type":"/cosmos.bank.v1beta1.MsgSend","from_address":"EXECUTOR","to_address":"SCRIPT","amount":[{"denom":"DYS_ROOT/coinS","amount":"100"}]}' \
  --attached-message '{"@type":"/cosmos.bank.v1beta1.MsgSend","from_address":"EXECUTOR","to_address":"SCRIPT","amount":[{"denom":"udys","amount":"FEE_INT"}]}' \
  -y -o json
```

Response includes `{ "liquid_denom": "...", "amount": "..." }`.

## 2) Convert to solid (`L(S)` → `S`)

```bash
dysond tx script exec \
  --script-address SCRIPT \
  --function-name convert_to_solid \
  --args '["LIQUID_DENOM","100"]' \
  --from EXECUTOR_NAME -y -o json
```

## 3) Make offer

### Normal (solid `have` escrow)

Attach base `have` to `SCRIPT` equal to the `have.amount`:
```bash
dysond tx script exec \
  --script-address SCRIPT \
  --function-name make_offer \
  --args '[{"denom":"DYS_ROOT/have","amount":30},{"denom":"DYS_ROOT/want","amount":45}]' \
  --from EXECUTOR_NAME \
  --attached-message '{"@type":"/cosmos.bank.v1beta1.MsgSend","from_address":"EXECUTOR","to_address":"SCRIPT","amount":[{"denom":"DYS_ROOT/have","amount":"30"}]}' \
  -y -o json
```

### Liquid (`have` is `L(S)`, pfand required)

Maker must hold `pfand` (`DYS_NAME/pfand`). No `have` attachments:
```bash
dysond tx script exec \
  --script-address SCRIPT \
  --function-name make_offer \
  --args '[{"denom":"LIQUID_HAVE","amount":20},{"denom":"DYS_ROOT/want","amount":30}]' \
  --from EXECUTOR_NAME -y -o json
```

## 4) Take

- If paying solid `want`, attach solid `want` to `SCRIPT`
- If paying `L(want)`, attach liquid `want` to `SCRIPT` (script will burn `L(want)` and release solid `want`)

```bash
dysond tx script exec \
  --script-address SCRIPT \
  --function-name take_offer \
  --args '[[{"offer_id":OFFER_ID,"take_units":null]]]' \
  --from EXECUTOR_NAME \
  --attached-message '{"@type":"/cosmos.bank.v1beta1.MsgSend","from_address":"EXECUTOR","to_address":"SCRIPT","amount":[{"denom":"DYS_ROOT/want","amount":"30"}]}' \
  -y -o json
```

## 5) Cancel

- Maker can cancel open offers
- Anyone can cancel a liquid offer if the maker cannot fund ≥ 1 `L(have)` unit; `pfand` is sent to the closer

```bash
dysond tx script exec \
  --script-address SCRIPT \
  --function-name cancel_offer \
  --args '[OFFER_ID]' \
  --from EXECUTOR_NAME -y -o json
```

Look for `pfand_released` with reason `maker_cancel` or `maker_insufficient`.

## 6) Explicit `mint_fee`

- The script always quotes fee with `quote_mint_fee(amount)` and validates that attached `udys` cover it
- If you call nameservice `mint-coins` directly, include `--mint-fee Xudys` and ensure the signer owns that many `udys`

## Notes

- Normal `make` forbids liquid attachments
- `want` is always a solid denom; takers may pay solid or liquid
- `deposit`/`withdraw` maintain that `SCRIPT` solid balances back all liquid supply
