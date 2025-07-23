# PBI-5: Manage coins in demo-dwapp (list balances & send funds)

[View in Backlog](../backlog.md#user-content-5)

## Overview
A new page in the `demo-dwapp` frontend should enable users to manage their on-chain coins. The page will list all account balances (with denom metadata) and provide a form to send funds to another address. It should display transaction results, including hash and error feedback, in a user-friendly way.

## Problem Statement
Currently, the demo-dwapp lacks any UI for users to see their coin balances or to transfer tokens. This limits testing and demonstration of the bank module functionality within Dyson Protocol.

## User Stories
1. **View Balances**: As a user, I can see all my balances with readable denomination names, symbols, and display exponents so that I understand my holdings.
2. **Send Funds**: As a user, I can enter an amount, denomination, and recipient address in a form, submit the transaction, and receive immediate feedback (success, tx-hash, or error message).
3. **Error Handling**: As a user, if the transaction fails (e.g., insufficient funds, invalid address), I see a clear error message explaining why.

## Technical Approach
* Query the bank module's gRPC/REST endpoints to fetch balances (`cosmos.bank.v1beta1.Query/AllBalances`) and denom metadata (`cosmos.bank.v1beta1.Query/DenomMetadata`).
* Re-use the existing JavaScript helpers in `demo-dwapp/storage/static/js/walletStore.js` (e.g. `getAccountInfo`, `sendMsg`) and `demo-dwapp/storage/static/js/dysonTxUtils.js` for all wallet interaction, gas estimation, signing and broadcasting. **Do not duplicate this logic.**
* Build the new `/coins` page using server-rendered HTML enhanced with **htmx** for dynamic/partial updates (e.g. refreshing balances after a send) and **Alpine.js** for lightweight state management and interactivity.
  * Balance table: denom symbol, amount (formatted by exponent), and denom unit.
  * Send form: recipient address (Bech32), amount, denom selector (populated from metadata) that calls `$store.walletStore.sendMsg({ msg: MsgSend, ... })`.
* On submit, construct and broadcast a `cosmos.bank.v1beta1.MsgSend` via the existing `sendMsg` helper; refresh the balance table on success.
* Display response:
  * Success: show tx-hash (with link to explorer if configured) and optionally block height confirmation.
  * Failure: show error string returned by `sendMsg`.
* Handle in-flight state and disable form while pending.

## UX/UI Considerations
* Use a simple card layout with two sections: "Balances" (table) and "Send Funds" (form).
* Ensure responsive design for mobile.
* Validation: amount > 0, valid Bech32 address, denom selected.
* Feedback: spinner during submit, alert banners for success/failure.

## Acceptance Criteria
| ID | Description |
|----|-------------|
| AC1 | Navigating to `/coins` shows a list of all balances with denom symbol, amount (formatted), and denom unit. |
| AC2 | The list includes metadata (symbol & exponent) fetched from the chain. |
| AC3 | A Send Funds form allows entering recipient address, amount, and selecting denom. |
| AC4 | Submitting the form broadcasts a `MsgSend`; on success, the balance list refreshes and tx-hash is displayed. |
| AC5 | On failure, an error message is shown without page reload. |
| AC6 | All UI input fields are validated client-side before submit. |

## Dependencies
* Bank module endpoints must be accessible from demo-dwapp.
* Wallet integration (Keplr or similar) available to sign transactions.

## Open Questions
* Which wallet provider will be the default (Keplr vs others)?
* Should we support multi-denom selection for balances&mdash;display unknown denoms or filter?

## Related Tasks
TBD – see `docs/delivery/5/tasks.md` once tasks are created. 