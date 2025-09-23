package module

import (
	"cosmossdk.io/core/appmodule"
	"cosmossdk.io/core/store"
	"cosmossdk.io/depinject"
	"cosmossdk.io/depinject/appconfig"
	"cosmossdk.io/log"
	modulev1 "dysonprotocol.com/api/crontask/module/v1"
	"dysonprotocol.com/x/crontask"
	"dysonprotocol.com/x/crontask/keeper"

	"github.com/cosmos/cosmos-sdk/baseapp"
	"github.com/cosmos/cosmos-sdk/codec"
	cdctypes "github.com/cosmos/cosmos-sdk/codec/types"
	authkeeper "github.com/cosmos/cosmos-sdk/x/auth/keeper"
	stakingkeeper "github.com/cosmos/cosmos-sdk/x/staking/keeper"
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

// CrontaskInputs is the input for the dep inject
type CrontaskInputs struct {
	depinject.In

	ModuleKey        depinject.OwnModuleKey
	Config           *modulev1.Module
	Cdc              codec.Codec
	AccountKeeper    authkeeper.AccountKeeper
	BankKeeper       crontask.BankKeeper
	StakingKeeper    *stakingkeeper.Keeper
	StoreService     store.KVStoreService
	Registry         cdctypes.InterfaceRegistry
	Logger           log.Logger
	MsgServiceRouter *baseapp.MsgServiceRouter
}

// CrontaskOutputs is the output for the dep inject
type CrontaskOutputs struct {
	depinject.Out

	Module         appmodule.AppModule
	CrontaskKeeper keeper.Keeper
}

// ProvideModule provides the app module
func ProvideModule(in CrontaskInputs) CrontaskOutputs {
	k := keeper.NewKeeper(
		in.Cdc,
		in.StoreService,
		in.AccountKeeper,
		in.BankKeeper,
		in.StakingKeeper,
		in.MsgServiceRouter,
		*crontask.DefaultConfig(),
		in.Logger,
	)

	m := NewAppModule(
		in.Cdc,
		k,
		in.AccountKeeper,
		in.Registry,
	)

	return CrontaskOutputs{
		Module:         m,
		CrontaskKeeper: k,
	}
}
