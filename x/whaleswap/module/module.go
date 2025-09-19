package module

import (
	"context"
	"encoding/json"
	"fmt"

	whaleswap "dysonprotocol.com/x/whaleswap"
	"dysonprotocol.com/x/whaleswap/keeper"
	whaleswaptypes "dysonprotocol.com/x/whaleswap/types"

	autocliv1 "cosmossdk.io/client/v2/autocli"
	"cosmossdk.io/core/appmodule"
	gwruntime "github.com/grpc-ecosystem/grpc-gateway/runtime"
	"github.com/spf13/cobra"

	sdkclient "github.com/cosmos/cosmos-sdk/client"
	"github.com/cosmos/cosmos-sdk/codec"
	cdctypes "github.com/cosmos/cosmos-sdk/codec/types"
	sdk "github.com/cosmos/cosmos-sdk/types"
	"github.com/cosmos/cosmos-sdk/types/module"
)

const ConsensusVersion = 1

var (
	_ module.AppModuleBasic        = AppModuleBasic{}
	_ module.AppModule             = AppModule{}
	_ module.HasServices           = AppModule{}
	_ module.HasGenesis            = AppModule{}
	_ appmodule.AppModule          = AppModule{}
	_ autocliv1.HasCustomTxCommand = AppModule{}
)

type AppModuleBasic struct{}

func (AppModuleBasic) Name() string { return whaleswap.ModuleName }
func (AppModuleBasic) RegisterLegacyAminoCodec(cdc *codec.LegacyAmino) {
	whaleswap.RegisterLegacyAminoCodec(cdc)
}
func (b AppModuleBasic) RegisterInterfaces(registry cdctypes.InterfaceRegistry) {
	whaleswap.RegisterInterfaces(registry)
}
func (AppModuleBasic) DefaultGenesis(cdc codec.JSONCodec) json.RawMessage {
	return cdc.MustMarshalJSON(whaleswap.DefaultGenesis())
}
func (AppModuleBasic) ValidateGenesis(cdc codec.JSONCodec, _ sdkclient.TxEncodingConfig, bz json.RawMessage) error {
	var data whaleswaptypes.GenesisState
	if err := cdc.UnmarshalJSON(bz, &data); err != nil {
		return fmt.Errorf("failed to unmarshal %s genesis state: %w", whaleswap.ModuleName, err)
	}
	return whaleswap.ValidateGenesisState(data)
}
func (AppModuleBasic) RegisterGRPCGatewayRoutes(clientCtx sdkclient.Context, mux *gwruntime.ServeMux) {
	if err := whaleswaptypes.RegisterQueryHandlerClient(context.Background(), mux, whaleswaptypes.NewQueryClient(clientCtx)); err != nil {
		panic(err)
	}
}
func (am AppModule) GetTxCmd() *cobra.Command    { return &cobra.Command{Use: whaleswap.ModuleName} }
func (am AppModule) GetQueryCmd() *cobra.Command { return &cobra.Command{Use: whaleswap.ModuleName} }

type AppModule struct {
	cdc      codec.Codec
	registry cdctypes.InterfaceRegistry
	keeper   keeper.Keeper
}

func NewAppModule(cdc codec.Codec, keeper keeper.Keeper, registry cdctypes.InterfaceRegistry) AppModule {
	return AppModule{cdc: cdc, keeper: keeper, registry: registry}
}

func (AppModule) IsAppModule()    {}
func (am AppModule) Name() string { return whaleswap.ModuleName }
func (am AppModule) DefaultGenesis(cdc codec.JSONCodec) json.RawMessage {
	return cdc.MustMarshalJSON(whaleswap.DefaultGenesis())
}
func (am AppModule) ValidateGenesis(cdc codec.JSONCodec, _ sdkclient.TxEncodingConfig, bz json.RawMessage) error {
	var data whaleswaptypes.GenesisState
	if err := cdc.UnmarshalJSON(bz, &data); err != nil {
		return fmt.Errorf("failed to unmarshal %s genesis state: %w", whaleswap.ModuleName, err)
	}
	return whaleswap.ValidateGenesisState(data)
}
func (am AppModule) ExportGenesis(ctx sdk.Context, cdc codec.JSONCodec) json.RawMessage {
	gs := am.keeper.ExportGenesis(ctx)
	return cdc.MustMarshalJSON(gs)
}
func (am AppModule) InitGenesis(ctx sdk.Context, cdc codec.JSONCodec, bz json.RawMessage) {
	var data whaleswaptypes.GenesisState
	if err := cdc.UnmarshalJSON(bz, &data); err != nil {
		panic(fmt.Errorf("failed to unmarshal %s genesis state: %w", whaleswap.ModuleName, err))
	}
	am.keeper.InitGenesis(ctx, &data)
}
func (AppModule) RegisterInterfaces(registrar cdctypes.InterfaceRegistry) {
	whaleswap.RegisterInterfaces(registrar)
}
func (am AppModule) RegisterServices(cfg module.Configurator) {
	whaleswaptypes.RegisterMsgServer(cfg.MsgServer(), am.keeper)
	whaleswaptypes.RegisterQueryServer(cfg.QueryServer(), am.keeper)
}
func (AppModule) RegisterMigrations() error          { return nil }
func (AppModule) ConsensusVersion() uint64           { return ConsensusVersion }
func (AppModule) EndBlock(ctx context.Context) error { return nil }
func (AppModule) RegisterGRPCGatewayRoutes(clientCtx sdkclient.Context, mux *gwruntime.ServeMux) {
	if err := whaleswaptypes.RegisterQueryHandlerClient(context.Background(), mux, whaleswaptypes.NewQueryClient(clientCtx)); err != nil {
		panic(err)
	}
}
func (AppModule) RegisterLegacyAminoCodec(registrar *codec.LegacyAmino) {
	whaleswap.RegisterLegacyAminoCodec(registrar)
}
