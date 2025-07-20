package keeper

import (
	"cosmossdk.io/collections"
	"cosmossdk.io/core/store"

	"cosmossdk.io/log"
	storage "dysonprotocol.com/x/storage"
	storagev1 "dysonprotocol.com/x/storage/types"
	"github.com/cosmos/cosmos-sdk/codec"
	sdk "github.com/cosmos/cosmos-sdk/types"
)

// We store each entry under "{owner}/{index}".
var StoragePrefix = collections.NewPrefix(0)

type Keeper struct {
	config    storage.Config
	cdc       codec.Codec
	accKeeper storage.AccountKeeper

	Schema collections.Schema

	// The robust store-level map ({owner}/{index})->Storage
	StorageMap collections.Map[string, storagev1.Storage]
}

func NewKeeper(
	storeService store.KVStoreService,
	cdc codec.Codec,
	accKeeper storage.AccountKeeper,
	config storage.Config,

) Keeper {
	sb := collections.NewSchemaBuilder(storeService)
	k := Keeper{
		config:    config,
		cdc:       cdc,
		accKeeper: accKeeper,
		StorageMap: collections.NewMap(
			sb,
			StoragePrefix, // prefix partition
			"storage_map", // name
			collections.StringKey,
			codec.CollValue[storagev1.Storage](cdc),
		),
	}
	schema, err := sb.Build()
	if err != nil {
		panic(err)
	}
	k.Schema = schema

	return k
}

// Logger returns a module-specific logger
func (k Keeper) Logger(ctx sdk.Context) log.Logger {
	return ctx.Logger().With("module", "x/storage")
}
