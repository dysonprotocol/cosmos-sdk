package keeper

import (
	"dysonprotocol.com/x/whaleswap/types"
	sdk "github.com/cosmos/cosmos-sdk/types"
)

// InitGenesis initializes state from genesis
func (k Keeper) InitGenesis(ctx sdk.Context, gs *types.GenesisState) {
	// params
	_ = k.SetParams(ctx, gs.Params)
}

// ExportGenesis exports current module state
func (k Keeper) ExportGenesis(ctx sdk.Context) *types.GenesisState {
	return &types.GenesisState{Params: k.GetParams(ctx)}
}
