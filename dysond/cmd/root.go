//go:build app_v1

package cmd

import (
	"os"

	"fmt"

	"cosmossdk.io/log"
	dbm "github.com/cosmos/cosmos-db"
	"github.com/spf13/cobra"
	"github.com/spf13/viper"

	"dysonprotocol.com"

	"github.com/cosmos/cosmos-sdk/client"
	"github.com/cosmos/cosmos-sdk/client/config"
	nodeservice "github.com/cosmos/cosmos-sdk/client/grpc/node"
	"github.com/cosmos/cosmos-sdk/server"
	simtestutil "github.com/cosmos/cosmos-sdk/testutil/sims"
	"github.com/cosmos/cosmos-sdk/types/tx/signing"
	"github.com/cosmos/cosmos-sdk/x/auth/tx"
	authtxconfig "github.com/cosmos/cosmos-sdk/x/auth/tx/config"
	"github.com/cosmos/cosmos-sdk/x/auth/types"

	sdk "github.com/cosmos/cosmos-sdk/types"

	dysonprotocolparams "dysonprotocol.com/dysond/params"
)

// NewRootCmd creates a new root command for simd. It is called once in the
// main function.
func NewRootCmd() *cobra.Command {

	cfg := sdk.GetConfig()
	cfg.SetBech32PrefixForAccount("dys2", "dys2pub")                     // account addresses
	cfg.SetBech32PrefixForValidator("dys2valoper", "dys2valoperpub")     // validator operator addresses
	cfg.SetBech32PrefixForConsensusNode("dys2valcons", "dys2valconspub") // consensus addresses

	// we "pre"-instantiate the application for getting the injected/configured encoding configuration
	dysApp := dysonprotocol.NewDysApp(log.NewNopLogger(), dbm.NewMemDB(), nil, true, simtestutil.NewAppOptionsWithFlagHome(dysonprotocol.DefaultNodeHome))
	encodingConfig := dysonprotocolparams.EncodingConfig{
		InterfaceRegistry: dysApp.InterfaceRegistry(),
		Codec:             dysApp.AppCodec(),
		TxConfig:          dysApp.TxConfig(),
		Amino:             dysApp.LegacyAmino(),
	}

	initClientCtx := client.Context{}.
		WithCodec(encodingConfig.Codec).
		WithInterfaceRegistry(encodingConfig.InterfaceRegistry).
		WithTxConfig(encodingConfig.TxConfig).
		WithLegacyAmino(encodingConfig.Amino).
		WithInput(os.Stdin).
		WithAccountRetriever(types.AccountRetriever{}).
		WithHomeDir(dysonprotocol.DefaultNodeHome).
		WithViper("dyson") // uses by default the binary name as prefix

	rootCmd := &cobra.Command{
		Use:           "dysond",
		Short:         "Dyson Protocol application",
		SilenceErrors: true,
		PersistentPreRunE: func(cmd *cobra.Command, _ []string) error {
			// set the default command outputs
			cmd.SetOut(cmd.OutOrStdout())
			cmd.SetErr(cmd.ErrOrStderr())

			initClientCtx = initClientCtx.WithCmdContext(cmd.Context())
			initClientCtx, err := client.ReadPersistentCommandFlags(initClientCtx, cmd.Flags())
			if err != nil {
				return err
			}

			initClientCtx, err = config.ReadFromClientConfig(initClientCtx)
			if err != nil {
				return err
			}

			// This needs to go after ReadFromClientConfig, as that function
			// sets the RPC client needed for SIGN_MODE_TEXTUAL. This sign mode
			// is only available if the client is online.
			if !initClientCtx.Offline {
				enabledSignModes := append(tx.DefaultSignModes, signing.SignMode_SIGN_MODE_TEXTUAL)
				txConfigOpts := tx.ConfigOptions{
					EnabledSignModes:           enabledSignModes,
					TextualCoinMetadataQueryFn: authtxconfig.NewGRPCCoinMetadataQueryFn(initClientCtx),
				}
				txConfig, err := tx.NewTxConfigWithOptions(
					initClientCtx.Codec,
					txConfigOpts,
				)
				if err != nil {
					return err
				}

				initClientCtx = initClientCtx.WithTxConfig(txConfig)
			}

			if err := client.SetCmdClientContextHandler(initClientCtx, cmd); err != nil {
				return err
			}

			customAppTemplate, customAppConfig := initAppConfig()
			customCMTConfig := initCometBFTConfig()

			if err := server.InterceptConfigsPreRunHandler(cmd, customAppTemplate, customAppConfig, customCMTConfig); err != nil {
				return err
			}

			// DWApp config visibility: show viper resolution for public-host-template
			isSet := viper.IsSet("dwapp.public-host-template")
			val := viper.GetString("dwapp.public-host-template")
			// Print to stdout to ensure visibility regardless of logger setup
			fmt.Printf("DWApp config: dwapp.public-host-template is_set=%v value=%q\n", isSet, val)

			// Also print from the server context's viper (the one used by Cosmos server)
			svrCtx := server.GetServerContextFromCmd(cmd)
			if svrCtx != nil && svrCtx.Viper != nil {
				serverV := svrCtx.Viper
				fmt.Printf("DWApp (server viper): config_file=%q\n", serverV.ConfigFileUsed())
				fmt.Printf(
					"DWApp (server viper): dwapp.public-host-template is_set=%v value=%q\n",
					serverV.IsSet("dwapp.public-host-template"),
					serverV.GetString("dwapp.public-host-template"),
				)
				// In case older configs used custom.dwapp.* keys, surface those too
				fmt.Printf(
					"DWApp (server viper): custom.dwapp.public-host-template is_set=%v value=%q\n",
					serverV.IsSet("custom.dwapp.public-host-template"),
					serverV.GetString("custom.dwapp.public-host-template"),
				)
			}

			return nil
		},
	}

	initRootCmd(rootCmd, encodingConfig.TxConfig, dysApp.BasicModuleManager)

	// add keyring to autocli opts
	autoCliOpts := dysApp.AutoCliOpts()
	autoCliOpts.ClientCtx = initClientCtx

	nodeCmds := nodeservice.NewNodeCommands()
	autoCliOpts.ModuleOptions[nodeCmds.Name()] = nodeCmds.AutoCLIOptions()

	if err := autoCliOpts.EnhanceRootCommand(rootCmd); err != nil {
		panic(err)
	}

	return rootCmd
}
