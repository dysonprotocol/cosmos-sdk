package keeper

import (
	"context"

	"cosmossdk.io/errors"
	storetypes "cosmossdk.io/store/types"
	"dysonprotocol.com/x/nft"

	"github.com/cosmos/cosmos-sdk/runtime"
	sdkerrors "github.com/cosmos/cosmos-sdk/types/errors"
)

// SaveClass defines a method for creating a new nft class
func (k Keeper) SaveClass(ctx context.Context, class nft.Class) error {
	if k.HasClass(ctx, class.Id) {
		return errors.Wrap(nft.ErrClassExists, class.Id)
	}
	bz, err := k.cdc.Marshal(&class)
	if err != nil {
		return errors.Wrap(err, "Marshal nft.Class failed")
	}
	store := k.storeService.OpenKVStore(ctx)
	return store.Set(classStoreKey(class.Id), bz)
}

// UpdateClass defines a method for updating an exist nft class
func (k Keeper) UpdateClass(ctx context.Context, class nft.Class) error {
	if !k.HasClass(ctx, class.Id) {
		return errors.Wrap(nft.ErrClassNotExists, class.Id)
	}
	bz, err := k.cdc.Marshal(&class)
	if err != nil {
		return errors.Wrap(err, "Marshal nft.Class failed")
	}
	store := k.storeService.OpenKVStore(ctx)
	return store.Set(classStoreKey(class.Id), bz)
}

// GetClass defines a method for returning the class information of the specified id
func (k Keeper) GetClass(ctx context.Context, classID string) (nft.Class, bool) {
	store := k.storeService.OpenKVStore(ctx)
	var class nft.Class

	bz, err := store.Get(classStoreKey(classID))
	if err != nil {
		return class, false
	}

	if len(bz) == 0 {
		return class, false
	}
	k.cdc.MustUnmarshal(bz, &class)
	return class, true
}

// GetClasses defines a method for returning all classes information
func (k Keeper) GetClasses(ctx context.Context) (classes []*nft.Class) {
	store := k.storeService.OpenKVStore(ctx)
	iterator := storetypes.KVStorePrefixIterator(runtime.KVStoreAdapter(store), ClassKey)
	defer iterator.Close()
	for ; iterator.Valid(); iterator.Next() {
		var class nft.Class
		k.cdc.MustUnmarshal(iterator.Value(), &class)
		classes = append(classes, &class)
	}
	return
}

// HasClass determines whether the specified classID exist
func (k Keeper) HasClass(ctx context.Context, classID string) bool {
	store := k.storeService.OpenKVStore(ctx)
	has, err := store.Has(classStoreKey(classID))
	if err != nil {
		panic(err)
	}
	return has
}

// RemoveClass deletes an existing NFT class. It requires the class to be empty
// (no NFTs) to avoid orphaning NFTs without a class.
func (k Keeper) RemoveClass(ctx context.Context, classID string) error {
	if !k.HasClass(ctx, classID) {
		return errors.Wrapf(sdkerrors.ErrNotFound, "class not found: %s", classID)
	}
	// Ensure the class has no NFTs
	if total := k.GetTotalSupply(ctx, classID); total != 0 {
		return errors.Wrapf(sdkerrors.ErrInvalidRequest, "cannot delete non-empty class %s: %d NFTs exist", classID, total)
	}

	store := k.storeService.OpenKVStore(ctx)
	// Delete class metadata entry
	if err := store.Delete(classStoreKey(classID)); err != nil {
		return err
	}
	// Delete total supply key if present
	if err := store.Delete(classTotalSupply(classID)); err != nil {
		return err
	}
	return nil
}
