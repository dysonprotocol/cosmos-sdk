# PBI-6: Manage names via demo-dwapp

## Overview
Provide full lifecycle management of Nameservice assets (names, NFTs, coins) directly from the demo-dwapp UI, and extend the Nameservice module with secure move messages for coins and NFTs.

## Problem Statement
Developers and end-users currently need to rely on CLI commands to manage names, NFTs and custom coins. This limits usability and adoption. In addition, there is no native way for a name owner to transfer their custom denomination coins/NFTs between arbitrary accounts while preserving module-safety guarantees.

## User Stories
* As a user, I can move all coins under a name I own to another user in a single transaction.
* As a user, I can move NFTs under a name I own to another user in a single transaction.
* As a user, I can register names, manage valuations, mint/transfer/burn coins, create NFT classes, mint/transfer/burn NFTs, and manage bids – all from the demo-dwapp UI.

## Technical Approach
1. Extend the `x/nameservice` module:
   • Define `MsgMoveCoins` (mirrors `MsgMintCoins`) – server-side transfer if signer passes `VerifyDenomOwner` and both addresses are non-module accounts.
   • Define `MsgMoveNft` (mirrors `MsgMintNft`) – same ownership & module checks.
   • Add protobuf defs, keeper logic, message service wiring, CLI/Autocli bindings, swagger, and events.
2. Demo-dwapp additions:
   • New route `/names` in `script.py`.
   • Front-end pages plus Alpine stores/components to cover all Nameservice actions enumerated in the Goal.
   • Re-use existing walletStore patterns and SRI/import-map pipeline.
3. Testing: unit + integration tests for new messages, E2E coverage of UI workflows.

## UX/UI Considerations
* Mirror UX conventions of existing Coins page.
* Progressive disclosure – tabs or accordion per sub-feature (registration, NFTs, coins, trading).
* Provide live balance/name ownership display and optimistic UI with tx hash feedback.

## Acceptance Criteria
1. `MsgMoveCoins` and `MsgMoveNft` pass all keeper checks and are exposed via CLI/RPC.
2. Unauthorized or module accounts cannot invoke move operations.
3. `/names` UI allows every action listed in Goal and displays success/failure.
4. E2E test covers happy-path scenarios for register → set destination → mint coin → move coin → bid/accept flow.

## Dependencies
* Nameservice module existing mint/transfer logic.
* Wallet signing support in demo-dwapp.

## Decisions
* Move operations will emit new dedicated events (`EventCoinsMoved`, `EventNftMoved`).
* No rate limiting will be enforced on large coin moves.

## Related Tasks
[Tasks for PBI 6](./tasks.md)