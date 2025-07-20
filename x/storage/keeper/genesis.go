package keeper

import (
	"context"
	"fmt"

	storagev1 "dysonprotocol.com/x/storage/types"
	"github.com/cosmos/cosmos-sdk/types"
)

// InitGenesis initializes the storage module's state from a genesis state.
func (k Keeper) InitGenesis(ctx context.Context, genState *storagev1.GenesisState) {
	// Iterate through all the storage entries in the genesis state and set them
	for i, entry := range genState.Entries {
		fmt.Printf("Processing genesis entry %d: owner=%s, index=%s\n", i, entry.Owner, entry.Index)

		// Validate the owner address is properly formatted
		if _, err := types.AccAddressFromBech32(entry.Owner); err != nil {
			fmt.Printf("Failed to validate owner address %s: %v\n", entry.Owner, err)
			panic(err)
		}

		// Generate the combined key
		combinedKey := entry.Owner + "/" + entry.Index
		fmt.Printf("Generated key: %v\n", combinedKey)

		// Set the storage entry
		if err := k.StorageMap.Set(ctx, combinedKey, storagev1.Storage{
			Owner: entry.Owner,
			Index: entry.Index,
			Data:  entry.Data,
		}); err != nil {
			fmt.Printf("Failed to set storage entry: %v\n", err)
			panic(err)
		}
		fmt.Printf("Successfully set storage entry\n")
	}
}

// ExportGenesis exports the storage module's state to a genesis state.
func (k Keeper) ExportGenesis(ctx context.Context) *storagev1.GenesisState {
	// Initialize an empty slice for entries
	entries := []storagev1.Storage{}

	// Iterate through all storage entries and add them to the slice
	entryRange, err := k.StorageMap.Iterate(ctx, nil)
	if err != nil {
		panic(err)
	}
	defer entryRange.Close()

	for ; entryRange.Valid(); entryRange.Next() {
		value, err := entryRange.Value()
		if err != nil {
			// Skip entries that can't be read (shouldn't happen)
			continue
		}
		entries = append(entries, value)
	}

	// Create and return a new genesis state with the entries
	return &storagev1.GenesisState{
		Entries: entries,
	}
}
