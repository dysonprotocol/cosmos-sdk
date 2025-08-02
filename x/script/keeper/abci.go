package keeper

import (
	"context"
	"fmt"

	scripttypes "dysonprotocol.com/x/script/types"
	sdk "github.com/cosmos/cosmos-sdk/types"
)

// BeginBlocker enforces nodes to keep the required historical blocks
// It queries the module parameters to determine the maximum historical blocks
// that should be available and panics if the required blocks are not accessible
func (k Keeper) BeginBlocker(ctx context.Context) error {
	sdkCtx := sdk.UnwrapSDKContext(ctx)

	// Get module parameters to determine the maximum historical blocks
	params := k.GetParams(ctx)

	return k.validateHistoricalBlocks(sdkCtx, params)
}

// validateHistoricalBlocks checks if the required historical blocks are accessible
func (k Keeper) validateHistoricalBlocks(ctx sdk.Context, params scripttypes.Params) error {
	currentHeight := ctx.BlockHeight()

	// Skip validation for genesis block and very early blocks
	if currentHeight <= 1 {
		return nil
	}

	// Skip validation if maxRelativeHistoricalBlocks is disabled (0 or negative)
	if params.MaxRelativeHistoricalBlocks < 1 {
		return nil
	}

	// Calculate the oldest block we should be able to query using the AbsoluteHistoricalBlockCutoff
	// The oldest required height is the maximum of:
	// 1. current_height - max_relative_historical_blocks
	// 2. absolute_historical_block_cutoff (the absolute minimum we require)
	oldestFromBlocks := currentHeight - params.MaxRelativeHistoricalBlocks
	oldestRequiredHeight := params.AbsoluteHistoricalBlockCutoff
	if oldestFromBlocks > oldestRequiredHeight {
		oldestRequiredHeight = oldestFromBlocks
	}

	// Ensure we never try to query height 0 or negative heights
	if oldestRequiredHeight < 1 {
		oldestRequiredHeight = 1
	}

	// Try to create a query context for the oldest required height
	// This will fail if the node doesn't have the historical blocks
	_, err := k.App.CreateQueryContextWithCheckHeader(oldestRequiredHeight, false, false)
	if err != nil {
		// This is a critical error - the node doesn't have required historical blocks
		// Log the error instead of panicking
		warningMsg := fmt.Sprintf(`
## CRITICAL WARNING: Missing Historical Blocks ##

This node is likely STATE-SYNCing to join the network and is missing initial historical blocks.
This error _could_ prevent the this node from joining the network. 

Normally if you let the node accumulate blocks this warning will resolve itself without any action required.

REQUIREMENT:
- config.toml min-retain-blocks MUST be > max-relative-historical-blocks (%d)

STATE-SYNC RECOVERY OPTIONS:
A. WAIT - Let the node accumulate blocks naturally (safest)
B. REQUEST missing blocks from other validators
   and use "dysond snapshots load <block snapshot>.gz" to load the missing blocks and continue with state-sync.
C. FALLBACK to block-sync from genesis (time-consuming)

TECHNICAL DETAILS:
- Script module requires access to %d historical blocks
- Missing blocks: height %d
`,
			params.MaxRelativeHistoricalBlocks, // The script parameter
			params.MaxRelativeHistoricalBlocks, // Script requirement
			oldestRequiredHeight,               // Missing block height
		)

		k.Logger(ctx).Error(
			warningMsg,
			"current_height", currentHeight,
			"oldest_required_height", oldestRequiredHeight,
			"max_relative_historical_blocks", params.MaxRelativeHistoricalBlocks,
			"absolute_historical_block_cutoff", params.AbsoluteHistoricalBlockCutoff,
			"error", err,
		)
		// return err
	}

	// Log successful validation for monitoring
	k.Logger(ctx).Info(
		"Historical block retention validation passed",
		"current_height", currentHeight,
		"oldest_required_height", oldestRequiredHeight,
		"max_relative_historical_blocks", params.MaxRelativeHistoricalBlocks,
		"absolute_historical_block_cutoff", params.AbsoluteHistoricalBlockCutoff,
	)

	return nil
}

func (k Keeper) EndBlocker(ctx context.Context) error {
	return nil
}
