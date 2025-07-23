# PBI-8: List and manage NFTs in demo-dwapp (list & detail view with bidding)

[View in Backlog](../backlog.md#user-content-8)

## Overview
Implement comprehensive NFT browsing and management features in the `demo-dwapp` frontend. Users should be able to list NFT classes, view NFTs (with full metadata), place bids, accept/reject bids, and toggle listed status. UI must clearly state that `nftclass.always_listed` overrides per-NFT listed flags.

## Problem Statement
Current demo lacks any dedicated NFT browsing or trading interface, limiting the ability to showcase DysonProtocol's NFT functionality and bidding mechanics.

## User Story
As a User, I want to browse NFT classes and NFTs, place bids, and manage listing so that I can trade NFTs directly from the web app.

## Technical Approach (High-level)
* New backend routes in `demo-dwapp/script.py`:
  * `/nftclasses` – render list of all NFT classes (REST: `GET /cosmos/nft/v1beta1/classes`)
  * `/nfts/class/{class_id}` – detail view for a class + all NFTs (REST: class & `nfts?class_id=`)
  * `/nfts/owner/{address}` – list of NFTs owned by address (REST: `nfts?owner=`)
* Templates: `nftclasses.html`, `nfts.html` extending `base.html`.
* Alpine store `nftStore.js` to drive UI logic (bidding, accept/reject, listed flag etc.).
* Update navigation bar to include "NFTs".

## Acceptance Criteria
| ID | Description |
|----|-------------|
| AC1 | Visiting `/nftclasses` loads all NFT classes with class-level metadata. |
| AC2 | Selecting a class loads `/nfts/class/{class_id}` showing all NFTs in that class with metadata & bid info. |
| AC3 | Users can submit bids on NFTs; success/failure & tx-hash feedback shown. |
| AC4 | NFT owners can accept or reject the current highest bid. |
| AC5 | Owners can toggle the NFT's listed flag with note that class `always_listed` flag takes precedence. |
| AC6 | `/nfts/owner/{address}` lists all NFTs for the given owner address. |
| AC7 | All interactions use existing walletStore `sendMsg` helper; no duplicated signing code. |

## Dependencies
* Nameservice & NFT modules must expose required endpoints.

## Related Tasks
See `./tasks.md`. 