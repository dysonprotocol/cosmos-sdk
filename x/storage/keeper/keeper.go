package keeper

import (
	"context"

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
var ParamsKey = collections.NewPrefix(1)

type Keeper struct {
	config    storage.Config
	cdc       codec.Codec
	accKeeper storage.AccountKeeper
	authority string // the address that is authorized to update module parameters

	Schema collections.Schema

	// The robust store-level map ({owner}/{index})->Storage
	StorageMap collections.Map[string, storagev1.Storage]
	params     collections.Item[storagev1.Params]
}

func NewKeeper(
	storeService store.KVStoreService,
	cdc codec.Codec,
	accKeeper storage.AccountKeeper,
	config storage.Config,
	authority string,

) Keeper {
	sb := collections.NewSchemaBuilder(storeService)
	k := Keeper{
		config:    config,
		cdc:       cdc,
		accKeeper: accKeeper,
		authority: authority,
		StorageMap: collections.NewMap(
			sb,
			StoragePrefix, // prefix partition
			"storage_map", // name
			collections.StringKey,
			codec.CollValue[storagev1.Storage](cdc),
		),
		params: collections.NewItem(
			sb,
			ParamsKey,
			"params",
			codec.CollValue[storagev1.Params](cdc),
		),
	}
	schema, err := sb.Build()
	if err != nil {
		panic(err)
	}
	k.Schema = schema

	return k
}

// GetAuthority returns the module authority
func (k Keeper) GetAuthority() string {
	return k.authority
}

// GetParams returns the current module parameters
func (k Keeper) GetParams(ctx context.Context) (params storagev1.Params) {
	params, err := k.params.Get(ctx)
	if err != nil {
		// If params don't exist, return defaults
		return storagev1.DefaultParams()
	}
	return params
}

// SetParams sets the module parameters
func (k Keeper) SetParams(ctx context.Context, params storagev1.Params) error {
	if err := params.Validate(); err != nil {
		return err
	}
	return k.params.Set(ctx, params)
}

// Logger returns a module-specific logger
func (k Keeper) Logger(ctx sdk.Context) log.Logger {
	return ctx.Logger().With("module", "x/storage")
}
