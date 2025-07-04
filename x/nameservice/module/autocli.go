package module

import (
	autocliv1 "cosmossdk.io/api/cosmos/autocli/v1"
	nameservicev1 "dysonprotocol.com/api/nameservice/types"
)

// AutoCLIOptions implements the autocli.HasAutoCLIConfig interface.
func (am AppModule) AutoCLIOptions() *autocliv1.ModuleOptions {
	return &autocliv1.ModuleOptions{
		Query: &autocliv1.ServiceCommandDescriptor{
			Service:              nameservicev1.Query_ServiceDesc.ServiceName,
			EnhanceCustomCommand: true,
			RpcCommandOptions: []*autocliv1.RpcCommandOptions{
				{
					RpcMethod: "ComputeHash",
					Use:       "compute-hash",
					Short:     "Compute the hash for a name, salt, and committer address",
					FlagOptions: map[string]*autocliv1.FlagOptions{
						"name": {
							Name:         "name",
							Usage:        "Name to compute the hash for",
							DefaultValue: "",
						},
						"salt": {
							Name:         "salt",
							Usage:        "Salt to use for the hash computation",
							DefaultValue: "",
						},
						"committer": {
							Name:         "committer",
							Usage:        "Committer address",
							DefaultValue: "",
						},
					},
				},
				{
					RpcMethod: "Params",
					Use:       "params",
					Short:     "Query the current nameservice parameters",
				},
			},
		},
		Tx: &autocliv1.ServiceCommandDescriptor{
			Service:              nameservicev1.Msg_ServiceDesc.ServiceName,
			EnhanceCustomCommand: true,
			RpcCommandOptions: []*autocliv1.RpcCommandOptions{
				{
					RpcMethod: "Commit",
					Use:       "commit",
					Short:     "Commit to registering a name",
					FlagOptions: map[string]*autocliv1.FlagOptions{
						"hexhash": {
							Name:         "commitment",
							Usage:        "The hex hash of the name commitment",
							DefaultValue: "",
						},
						"valuation": {
							Name:         "valuation",
							Usage:        "The valuation for the name (format: 100dys)",
							DefaultValue: "",
						},
					},
				},
				{
					RpcMethod: "Reveal",
					Use:       "reveal",
					Short:     "Reveal a name to complete registration",
					FlagOptions: map[string]*autocliv1.FlagOptions{
						"name": {
							Name:         "name",
							Usage:        "The name to reveal",
							DefaultValue: "",
						},
						"salt": {
							Name:         "salt",
							Usage:        "The salt used in the commitment",
							DefaultValue: "",
						},
					},
				},
				{
					RpcMethod: "SetDestination",
					Use:       "set-destination",
					Short:     "Set the destination address for a name",
					FlagOptions: map[string]*autocliv1.FlagOptions{
						"name": {
							Name:         "name",
							Usage:        "The name to set the destination for",
							DefaultValue: "",
						},
						"destination": {
							Name:         "destination",
							Usage:        "The destination address",
							DefaultValue: "",
						},
					},
				},
				{
					RpcMethod: "SetValuation",
					Use:       "set-valuation",
					Short:     "Set the valuation for an NFT",
					FlagOptions: map[string]*autocliv1.FlagOptions{
						"nft_class_id": {
							Name:         "class-id",
							Usage:        "The class ID of the NFT",
							DefaultValue: "",
						},
						"nft_id": {
							Name:         "nft-id",
							Usage:        "The ID of the NFT",
							DefaultValue: "",
						},
						"valuation": {
							Name:         "valuation",
							Usage:        "The new valuation (format: 100udys)",
							DefaultValue: "",
						},
					},
				},
				{
					RpcMethod: "PlaceBid",
					Use:       "place-bid --nft-class-id=<class-id> --nft-id=<nft-id> --bid-amount=<amount>",
					Short:     "Place a bid on an NFT",
					FlagOptions: map[string]*autocliv1.FlagOptions{
						"nft_class_id": {
							Name:         "nft-class-id",
							Usage:        "The class ID of the NFT",
							DefaultValue: "",
						},
						"nft_id": {
							Name:         "nft-id",
							Usage:        "The ID of the NFT",
							DefaultValue: "",
						},
						"bid_amount": {
							Name:         "bid-amount",
							Usage:        "The amount to bid (format: 100udys)",
							DefaultValue: "",
						},
					},
				},
				{
					RpcMethod: "ClaimBid",
					Use:       "claim-bid --nft-class-id=<class-id> --nft-id=<nft-id>",
					Short:     "Claim an NFT after bid timeout has elapsed",
					FlagOptions: map[string]*autocliv1.FlagOptions{
						"nft_class_id": {
							Name:         "nft-class-id",
							Usage:        "The class ID of the NFT",
							DefaultValue: "",
						},
						"nft_id": {
							Name:         "nft-id",
							Usage:        "The ID of the NFT",
							DefaultValue: "",
						},
					},
				},
				{
					RpcMethod: "AcceptBid",
					Use:       "accept-bid --nft-class-id=<class-id> --nft-id=<nft-id>",
					Short:     "Accept a bid on an NFT",
					FlagOptions: map[string]*autocliv1.FlagOptions{
						"nft_class_id": {
							Name:         "nft-class-id",
							Usage:        "The class ID of the NFT",
							DefaultValue: "",
						},
						"nft_id": {
							Name:         "nft-id",
							Usage:        "The ID of the NFT",
							DefaultValue: "",
						},
					},
				},
				{
					RpcMethod: "RejectBid",
					Use:       "reject-bid --nft-class-id=<class-id> --nft-id=<nft-id>",
					Short:     "Reject a bid on an NFT",
					FlagOptions: map[string]*autocliv1.FlagOptions{
						"nft_class_id": {
							Name:         "nft-class-id",
							Usage:        "The class ID of the NFT",
							DefaultValue: "",
						},
						"nft_id": {
							Name:         "nft-id",
							Usage:        "The ID of the NFT",
							DefaultValue: "",
						},
					},
				},
				{
					RpcMethod: "SaveClass",
					Use:       "save-class --class-id=<class-id> --name=<name> --symbol=<symbol> --description=<description> --uri=<uri>",
					Short:     "Create or update an NFT class",
					FlagOptions: map[string]*autocliv1.FlagOptions{
						"class_id": {
							Name:         "class-id",
							Usage:        "The class ID to create",
							DefaultValue: "",
						},
						"name": {
							Name:         "name",
							Usage:        "The name of the class",
							DefaultValue: "",
						},
						"symbol": {
							Name:         "symbol",
							Usage:        "The symbol of the class",
							DefaultValue: "",
						},
						"description": {
							Name:         "description",
							Usage:        "The description of the class",
							DefaultValue: "",
						},
						"uri": {
							Name:         "uri",
							Usage:        "The URI for the class",
							DefaultValue: "",
						},
					},
				},
				{
					RpcMethod: "MintNFT",
					Use:       "mint-nft --class-id=<class-id> --nft-id=<nft-id> --uri=<uri>",
					Short:     "Mint a new NFT",
					FlagOptions: map[string]*autocliv1.FlagOptions{
						"class_id": {
							Name:         "class-id",
							Usage:        "The class ID of the NFT",
							DefaultValue: "",
						},
						"nft_id": {
							Name:         "nft-id",
							Usage:        "The ID of the NFT to mint",
							DefaultValue: "",
						},
						"uri": {
							Name:         "uri",
							Usage:        "The URI for the NFT",
							DefaultValue: "",
						},
					},
				},
				{
					RpcMethod: "MoveNft",
					Use:       "move-nft",
					Short:     "Force move an NFT between two accounts (requires signer to own the NFT class)",
					FlagOptions: map[string]*autocliv1.FlagOptions{
						"class_id": {
							Name:         "class-id",
							Usage:        "The NFT class ID",
							DefaultValue: "",
						},
						"nft_id": {
							Name:         "nft-id",
							Usage:        "The NFT ID",
							DefaultValue: "",
						},
						"to_address": {
							Name:         "to-address",
							Usage:        "Destination address (Bech32)",
							DefaultValue: "",
						},
					},
				},
				{
					RpcMethod: "SetNFTMetadata",
					Use:       "set-nft-metadata --class-id=<class-id> --nft-id=<nft-id> --metadata=<metadata>",
					Short:     "Set metadata for an NFT",
					FlagOptions: map[string]*autocliv1.FlagOptions{
						"class_id": {
							Name:         "class-id",
							Usage:        "The class ID of the NFT",
							DefaultValue: "",
						},
						"nft_id": {
							Name:         "nft-id",
							Usage:        "The ID of the NFT",
							DefaultValue: "",
						},
						"metadata": {
							Name:         "metadata",
							Usage:        "The metadata JSON string",
							DefaultValue: "",
						},
					},
				},
				{
					RpcMethod: "SetNFTClassExtraData",
					Use:       "set-nft-class-extra-data --class-id=<class-id> --extra-data=<extra-data>",
					Short:     "Set extra data for an NFT class",
					FlagOptions: map[string]*autocliv1.FlagOptions{
						"class_id": {
							Name:         "class-id",
							Usage:        "The class ID",
							DefaultValue: "",
						},
						"extra_data": {
							Name:         "extra-data",
							Usage:        "The extra data JSON string",
							DefaultValue: "",
						},
					},
				},
				{
					RpcMethod: "SetNFTClassAlwaysListed",
					Use:       "set-nft-class-always-listed --class-id=<class-id> --always-listed=<always-listed>",
					Short:     "Set the always_listed flag for an NFT class",
					FlagOptions: map[string]*autocliv1.FlagOptions{
						"class_id": {
							Name:         "class-id",
							Usage:        "The class ID",
							DefaultValue: "",
						},
						"always_listed": {
							Name:         "always-listed",
							Usage:        "Whether NFTs in this class should always be listed for sale",
							DefaultValue: "false",
						},
					},
				},
				{
					RpcMethod: "SetNFTClassAnnualPct",
					Use:       "set-nft-class-annual-pct --class-id=<class-id> --annual-pct=<annual-pct>",
					Short:     "Set the annual percentage rate for an NFT class",
					FlagOptions: map[string]*autocliv1.FlagOptions{
						"class_id": {
							Name:         "class-id",
							Usage:        "The class ID",
							DefaultValue: "",
						},
						"annual_pct": {
							Name:         "annual-pct",
							Usage:        "The annual percentage rate (0.0 to 100.0)",
							DefaultValue: "",
						},
					},
				},
				{
					RpcMethod: "SetListed",
					Use:       "set-listed --nft-class-id=<class-id> --nft-id=<nft-id> --listed=<listed>",
					Short:     "Set the listed status for a specific NFT",
					FlagOptions: map[string]*autocliv1.FlagOptions{
						"nft_class_id": {
							Name:         "nft-class-id",
							Usage:        "The class ID of the NFT",
							DefaultValue: "",
						},
						"nft_id": {
							Name:         "nft-id",
							Usage:        "The ID of the NFT",
							DefaultValue: "",
						},
						"listed": {
							Name:         "listed",
							Usage:        "Whether the NFT should be listed for sale (true/false)",
							DefaultValue: "false",
						},
					},
				},
				{
					RpcMethod: "Renew",
					Use:       "renew --nft-class-id=<class-id> --nft-id=<nft-id>",
					Short:     "Renew an NFT name registration",
					FlagOptions: map[string]*autocliv1.FlagOptions{
						"nft_class_id": {
							Name:         "nft-class-id",
							Usage:        "The class ID of the NFT to renew",
							DefaultValue: "",
						},
						"nft_id": {
							Name:         "nft-id",
							Usage:        "The ID of the NFT to renew",
							DefaultValue: "",
						},
					},
				},
			},
		},
	}
}
