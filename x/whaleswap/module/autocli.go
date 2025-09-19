package module

import (
	autocliv1 "cosmossdk.io/api/cosmos/autocli/v1"
	whaleswapapiv1 "dysonprotocol.com/api/whaleswap/types"
)

// AutoCLIOptions implements the autocli.HasAutoCLIConfig interface for whaleswap.
func (am AppModule) AutoCLIOptions() *autocliv1.ModuleOptions {
	return &autocliv1.ModuleOptions{
		Query: &autocliv1.ServiceCommandDescriptor{
			Service:              whaleswapapiv1.Query_ServiceDesc.ServiceName,
			EnhanceCustomCommand: true,
			RpcCommandOptions: []*autocliv1.RpcCommandOptions{
				{
					RpcMethod: "Params",
					Use:       "params",
					Short:     "Query the whaleswap module parameters",
					Long:      "Return all current module parameters including pfand_per_offer and auction knobs.",
					Example:   "dysond query whaleswap params",
				},
				{
					RpcMethod: "Pool",
					Use:       "pool <pool-id>",
					Short:     "Get a pool by ID",
					Long:      "Fetch a single AMM pool by its numeric ID.",
					Example:   "dysond query whaleswap pool 1",
					PositionalArgs: []*autocliv1.PositionalArgDescriptor{{
						ProtoField: "pool_id",
					}},
				},
				{
					RpcMethod: "Pools",
					Use:       "pools",
					Short:     "List pools with pagination",
					Long:      "List AMM pools. Use pagination flags to page through results.",
					Example:   "dysond query whaleswap pools --limit 50",
				},
				{
					RpcMethod: "Offer",
					Use:       "offer <offer-id>",
					Short:     "Get an offer by ID",
					Long:      "Fetch a single orderbook offer by its numeric ID.",
					Example:   "dysond query whaleswap offer 42",
					PositionalArgs: []*autocliv1.PositionalArgDescriptor{{
						ProtoField: "offer_id",
					}},
				},
				{
					RpcMethod: "OffersByOwner",
					Use:       "offers-by-owner <owner>",
					Short:     "List offers by owner with optional status",
					Long:      "List all offers created by an owner address. Optionally filter by status (open/closed/cancelled).",
					Example:   "dysond query whaleswap offers-by-owner $(dysond keys show alice -a) --status=open",
					PositionalArgs: []*autocliv1.PositionalArgDescriptor{{
						ProtoField: "owner",
					}},
				},
				{
					RpcMethod: "Offers",
					Use:       "offers",
					Short:     "List offers with optional have/want filters",
					Long:      "List orderbook offers. Optionally filter by have_denom and/or want_denom. Use pagination flags for paging.",
					Example:   "dysond query whaleswap offers --have-denom=udys --want-denom=ufoo --limit 100",
				},
				{
					RpcMethod: "TradesByOffer",
					Use:       "trades-by-offer <offer-id>",
					Short:     "List trades for an offer",
					Long:      "List all trades executed against a specific offer.",
					Example:   "dysond query whaleswap trades-by-offer 42",
					PositionalArgs: []*autocliv1.PositionalArgDescriptor{{
						ProtoField: "offer_id",
					}},
				},
				{
					RpcMethod: "TradesByTaker",
					Use:       "trades-by-taker <taker>",
					Short:     "List trades by taker",
					Long:      "List all trades executed by the given taker address.",
					Example:   "dysond query whaleswap trades-by-taker $(dysond keys show bob -a)",
					PositionalArgs: []*autocliv1.PositionalArgDescriptor{{
						ProtoField: "taker",
					}},
				},
				{
					RpcMethod: "Auction",
					Use:       "auction <auction-id>",
					Short:     "Get an auction by ID",
					Long:      "Fetch a single auction by its numeric ID.",
					Example:   "dysond query whaleswap auction 7",
					PositionalArgs: []*autocliv1.PositionalArgDescriptor{{
						ProtoField: "auction_id",
					}},
				},
				{
					RpcMethod: "Auctions",
					Use:       "auctions",
					Short:     "List auctions with optional sell/bid filters",
					Long:      "List auctions. Optionally filter by sell_denom and/or bid_denom. Use pagination flags for paging.",
					Example:   "dysond query whaleswap auctions --sell-denom=udys --bid-denom=ufoo",
				},
			},
		},
		Tx: &autocliv1.ServiceCommandDescriptor{
			Service:              whaleswapapiv1.Msg_ServiceDesc.ServiceName,
			EnhanceCustomCommand: true,
			RpcCommandOptions: []*autocliv1.RpcCommandOptions{
				{
					RpcMethod: "CreatePool",
					Use:       "create-pool --coin-a=<amountdenom> --coin-b=<amountdenom> [--fee-pct=<dec>] [--min-price=<coins>] [--max-price=<coins>]",
					Short:     "Create a new AMM pool",
					Long:      "Create a new AMM pool. If no price band is set, the pool behaves as constant product (v2). If a band is set, concentrated liquidity (v3) math is used.",
					Example: "dysond tx whaleswap create-pool --coin-a=1000udys --coin-b=500ufoo --fee-pct=0.003\n" +
						"dysond tx whaleswap create-pool --coin-a=1000udys --coin-b=500ufoo --min-price=1udys,2ufoo --max-price=1udys,3ufoo",
				},
				{
					RpcMethod: "UpdatePoolConfig",
					Use:       "update-pool-config --pool-id=<id> [--fee-pct=<dec>] [--min-price=<coins>] [--max-price=<coins>]",
					Short:     "Update pool fee or price band",
					Long:      "Update an existing pool's fee percent and/or price band. Only the majority owner (>50% shares) may update.",
					Example:   "dysond tx whaleswap update-pool-config --pool-id=1 --fee-pct=0.0025",
				},
				{
					RpcMethod: "AddLiquidity",
					Use:       "add-liquidity --pool-id=<id> --amount1=<amountdenom> --amount2=<amountdenom>",
					Short:     "Add liquidity to a pool (owner-only)",
					Long:      "Provide both coins to add liquidity to the pool. Excess is refunded to maintain the pool ratio.",
					Example:   "dysond tx whaleswap add-liquidity --pool-id=1 --amount1=1000udys --amount2=600ufoo",
				},
				{
					RpcMethod: "RemoveLiquidity",
					Use:       "remove-liquidity --pool-id=<id> --shares=<amount>",
					Short:     "Remove liquidity and burn shares",
					Long:      "Burn the specified number of shares and receive the underlying coins proportionally (v2) or using band-aware math (v3).",
					Example:   "dysond tx whaleswap remove-liquidity --pool-id=1 --shares=100",
				},
				{
					RpcMethod: "PoolSwap",
					Use:       "swap --pool-id=<id> --input=<amountdenom> --minimum-out-amount=<amount> --out-denom=<denom>",
					Short:     "Swap against a single pool",
					Long:      "Execute a single-pool swap. To route across multiple pools, include multiple swap messages in the same tx or call the module multiple times from a script.",
					Example:   "dysond tx whaleswap swap --pool-id=1 --input=100udys --minimum-out-amount=90 --out-denom=ufoo",
				},
				{
					RpcMethod: "ConvertToLiquid",
					Use:       "convert-to-liquid --denom=<denom> --amount=<amount>",
					Short:     "Wrap a solid denom into its liquid wrapper",
					Long:      "Convert solid denom S into liquid L(S). Nameservice mint fee is skipped for module account minting.",
					Example:   "dysond tx whaleswap convert-to-liquid --denom=udys --amount=1000",
				},
				{
					RpcMethod: "ConvertToSolid",
					Use:       "convert-to-solid --liquid-denom=<liquid-denom> --amount=<amount>",
					Short:     "Unwrap a liquid denom back to solid",
					Long:      "Convert liquid L(S) back to solid S. Burns the liquid and releases the backed solid coin.",
					Example:   "dysond tx whaleswap convert-to-solid --liquid-denom=whaleswap.dys/coins/udys --amount=1000",
				},
				{
					RpcMethod: "MakeOffer",
					Use:       "make-offer --have=<amountdenom> --want=<amountdenom>",
					Short:     "Create an orderbook offer (normal or liquid mode)",
					Long:      "Create an offer. Normal mode escrows the base 'have' in the module. Liquid mode uses liquid have and locks pfand from params.",
					Example: "Normal: dysond tx whaleswap make-offer --have=100udys --want=50ufoo\n" +
						"Liquid: dysond tx whaleswap make-offer --have=100whaleswap.dys/coins/udys --want=50ufoo",
				},
				{
					RpcMethod: "TakeOffer",
					Use:       "take-offer --trades='[{\"offer_id\":1,\"take_units\":\"10\"}]'",
					Short:     "Take one or more offers (batch)",
					Long:      "Execute one or more takes in a single transaction. If the maker-have is liquid, it must be burned by the maker.",
					Example:   "dysond tx whaleswap take-offer --trades='[{\"offer_id\":1,\"take_units\":\"10\"}]'",
				},
				{
					RpcMethod: "CancelOffer",
					Use:       "cancel-offer --offer-id=<id>",
					Short:     "Cancel an offer",
					Long:      "Cancel an offer. The maker can always cancel. A third-party can cancel liquid offers if maker lacks 1 unit of liquid have (pfand rules).",
					Example:   "dysond tx whaleswap cancel-offer --offer-id=42",
				},
				{
					RpcMethod: "OpenAuction",
					Use:       "open-auction --seller=<addr> --bid-denom=<denom> --sell=<amountdenom>",
					Short:     "Open an auction by escrowing a solid coin",
					Long:      "Escrow a solid 'sell' coin and mint an auction NFT in class whaleswap.dys/auction/{bid_denom}. Only bids in bid_denom are allowed.",
					Example:   "dysond tx whaleswap open-auction --seller=$(dysond keys show alice -a) --bid-denom=ufoo --sell=100udys",
				},
				{
					RpcMethod: "RedeemAuction",
					Use:       "redeem-auction --auction-id=<id>",
					Short:     "Redeem auction escrow if no bidder",
					Long:      "Redeem an open auction only if there is no current bidder. Burns the NFT and releases the escrowed sell coin to the caller.",
					Example:   "dysond tx whaleswap redeem-auction --auction-id=7",
				},
				{
					RpcMethod: "UpdateParams",
					Use:       "update-params",
					Short:     "Update whaleswap module params (authority only)",
					Long:      "Update module parameters. Only the gov authority may execute this.",
					Example:   "dysond tx whaleswap update-params --from gov --pfand-per-offer=1udys",
				},
			},
		},
	}
}
