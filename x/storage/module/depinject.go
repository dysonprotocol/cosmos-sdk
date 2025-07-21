package module

import (
	"cosmossdk.io/core/appmodule"
	"cosmossdk.io/core/store"
	"cosmossdk.io/depinject"
	"cosmossdk.io/depinject/appconfig"
	modulev1 "dysonprotocol.com/api/storage/module/v1"
	"dysonprotocol.com/x/storage"
	"dysonprotocol.com/x/storage/keeper"
	authkeeper "github.com/cosmos/cosmos-sdk/x/auth/keeper"
	authtypes "github.com/cosmos/cosmos-sdk/x/auth/types"
	govtypes "github.com/cosmos/cosmos-sdk/x/gov/types"

	"github.com/cosmos/cosmos-sdk/codec"
	cdctypes "github.com/cosmos/cosmos-sdk/codec/types"
)

var _ depinject.OnePerModuleType = AppModule{}

// IsOnePerModuleType implements the depinject.OnePerModuleType interface.
func (am AppModule) IsOnePerModuleType() {}

func init() {
	appconfig.RegisterModule(
		&modulev1.Module{},
		appconfig.Provide(ProvideModule),
	)
}

type StorageInputs struct {
	depinject.In

	Cdc           codec.Codec
	StoreService  store.KVStoreService
	AccountKeeper authkeeper.AccountKeeper
	Registry      cdctypes.InterfaceRegistry
	Config        *modulev1.Module
}

type ModuleOutputs struct {
	depinject.Out

	StorageKeeper keeper.Keeper
	Module        appmodule.AppModule
}

func ProvideModule(in StorageInputs) ModuleOutputs {
	// Use the authority from the config if provided, otherwise default to gov module account
	authority := authtypes.NewModuleAddress(govtypes.ModuleName).String()

	// If authority is explicitly set in the config, use that instead
	if in.Config != nil && in.Config.Authority != "" {
		authority = in.Config.Authority
	}

	k := keeper.NewKeeper(
		in.StoreService,
		in.Cdc,
		in.AccountKeeper,
		storage.Config{},
		authority,
	)
	m := NewAppModule(in.Cdc, k, in.AccountKeeper, in.Registry)
	return ModuleOutputs{StorageKeeper: k, Module: m}
}
