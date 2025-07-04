package cmd

import (
	"errors"
	"io"

	cmtcfg "github.com/cometbft/cometbft/config"
	dbm "github.com/cosmos/cosmos-db"
	"github.com/spf13/cobra"
	"github.com/spf13/viper"

	"cosmossdk.io/log"

	"dysonprotocol.com"
	"dysonprotocol.com/dysond/server/dwapp"

	confixcmd "cosmossdk.io/tools/confix/cmd"

	"github.com/cosmos/cosmos-sdk/client"
	"github.com/cosmos/cosmos-sdk/client/debug"
	"github.com/cosmos/cosmos-sdk/client/keys"
	"github.com/cosmos/cosmos-sdk/client/pruning"
	"github.com/cosmos/cosmos-sdk/client/rpc"
	"github.com/cosmos/cosmos-sdk/client/snapshot"
	"github.com/cosmos/cosmos-sdk/server"
	serverconfig "github.com/cosmos/cosmos-sdk/server/config"
	servertypes "github.com/cosmos/cosmos-sdk/server/types"
	"github.com/cosmos/cosmos-sdk/types/module"
	authcmd "github.com/cosmos/cosmos-sdk/x/auth/client/cli"
	banktypes "github.com/cosmos/cosmos-sdk/x/bank/types"
	genutilcli "github.com/cosmos/cosmos-sdk/x/genutil/client/cli"
)

// initCometBFTConfig helps to override default CometBFT Config values.
// return cmtcfg.DefaultConfig if no custom configuration is required for the application.
func initCometBFTConfig() *cmtcfg.Config {
	// Initialize with default CometBFT configuration
	cfg := cmtcfg.DefaultConfig()

	// these values put a higher strain on node memory
	// Uncomment to adjust peer connection limits if needed
	// cfg.P2P.MaxNumInboundPeers = 100
	// cfg.P2P.MaxNumOutboundPeers = 40

	return cfg
}

// initAppConfig helps to override default appConfig template and configs.
// It returns a custom app.toml template and default configuration values.
// return "", nil if no custom configuration is required for the application.
func initAppConfig() (string, interface{}) {
	// The following defines custom configuration options for the Dyson protocol

	// CustomConfig defines an arbitrary custom config to extend app.toml.
	// If you don't need it, you can remove it.
	// If you wish to add fields that correspond to flags that aren't in the SDK server config,
	// this custom config can as well help.
	type CustomConfig struct {
		DwApp struct {
			ScriptAddressOrNamePattern string `mapstructure:"script-address-or-name-pattern"`
		} `mapstructure:"dwapp"`
	}

	// CustomAppConfig combines the standard SDK config with our custom extensions
	type CustomAppConfig struct {
		serverconfig.Config `mapstructure:",squash"`

		Custom CustomConfig `mapstructure:"custom"`
	}

	// Optionally allow the chain developer to overwrite the SDK's default
	// server config.
	srvCfg := serverconfig.DefaultConfig()
	// The SDK's default minimum gas price is set to "" (empty value) inside
	// app.toml. If left empty by validators, the node will halt on startup.
	// However, the chain developer can set a default app.toml value for their
	// validators here.
	//
	// In summary:
	// - if you leave srvCfg.MinGasPrices = "", all validators MUST tweak their
	//   own app.toml config,
	// - if you set srvCfg.MinGasPrices non-empty, validators CAN tweak their
	//   own app.toml to override, or use this default value.
	//
	// In dysapp, we set the min gas prices to 0.
	srvCfg.MinGasPrices = "0udys"
	// srvCfg.BaseConfig.IAVLDisableFastNode = true // disable fastnode by default

	// Set API Swagger to be enabled by default
	srvCfg.API.Swagger = true
	srvCfg.API.Enable = true

	// Now we set the custom config default values.
	customAppConfig := CustomAppConfig{
		Config: *srvCfg,
		Custom: CustomConfig{
			DwApp: struct {
				ScriptAddressOrNamePattern string `mapstructure:"script-address-or-name-pattern"`
			}{
				ScriptAddressOrNamePattern: dwapp.DefaultDwAppPattern,
			},
		},
	}

	// The default SDK app template is defined in serverconfig.DefaultConfigTemplate.
	// We append the custom config template to the default one.
	// And we set the default config to the custom app template.
	customAppTemplate := serverconfig.DefaultConfigTemplate + `

[dwapp]
# Regular expression pattern for extracting script address or name from hostname.
# This pattern must be a valid TOML string literal
script-address-or-name-pattern = '{{ .Custom.DwApp.ScriptAddressOrNamePattern }}'
`

	return customAppTemplate, customAppConfig
}

// initRootCmd initializes the root command for the Dyson blockchain application.
// It adds all subcommands and flags needed for the full node operation.
// Parameters:
// - rootCmd: The root command to initialize
// - txConfig: Transaction configuration for the app
// - basicManager: Module manager containing all registered modules
func initRootCmd(
	rootCmd *cobra.Command,
	txConfig client.TxConfig,
	basicManager module.BasicManager,
) {

	// Add essential commands for chain initialization and management
	rootCmd.AddCommand(
		genutilcli.InitCmd(basicManager, dysonprotocol.DefaultNodeHome),
		NewTestnetCmd(basicManager, banktypes.GenesisBalancesIterator{}),
		debug.Cmd(),
		confixcmd.ConfigCommand(),
		pruning.Cmd(newApp, dysonprotocol.DefaultNodeHome),
		snapshot.Cmd(newApp),
	)

	// Add commands to start the node with custom options
	server.AddCommandsWithStartCmdOptions(rootCmd, dysonprotocol.DefaultNodeHome, newApp, appExport, server.StartCmdOptions{
		//PostSetup:           setupApps,
		//PostSetupStandalone: setupApps,
	})

	// add keybase, auxiliary RPC, query, genesis, and tx child commands
	rootCmd.AddCommand(
		server.StatusCommand(),
		genesisCommand(txConfig, basicManager),
		queryCommand(),
		txCommand(),
		keys.Commands(),
	)
}

// genesisCommand builds genesis-related `simd genesis` command.
// Users may provide application specific commands as a parameter.
// Parameters:
// - txConfig: Transaction configuration for genesis operations
// - basicManager: Module manager with access to all modules for genesis creation
// - cmds: Optional additional commands to include under the genesis command
// Returns: A cobra.Command with all genesis-related functionality
func genesisCommand(txConfig client.TxConfig, basicManager module.BasicManager, cmds ...*cobra.Command) *cobra.Command {
	cmd := genutilcli.Commands(txConfig, basicManager, dysonprotocol.DefaultNodeHome)

	// Add any additional sub-commands provided by the application
	for _, subCmd := range cmds {
		cmd.AddCommand(subCmd)
	}
	return cmd
}

// queryCommand returns a root CLI command handler for all query commands in the application.
// It aggregates various query subcommands from different modules.
// Returns: A cobra.Command that serves as the parent for all query subcommands
func queryCommand() *cobra.Command {
	cmd := &cobra.Command{
		Use:                        "query",
		Aliases:                    []string{"q"},
		Short:                      "Querying subcommands",
		DisableFlagParsing:         false,
		SuggestionsMinimumDistance: 2,
		RunE:                       client.ValidateCmd,
	}

	// Add query subcommands from various modules
	cmd.AddCommand(
		rpc.WaitTxCmd(),               // Wait for a transaction to be included in a block
		server.QueryBlockCmd(),        // Query a block by height
		authcmd.QueryTxsByEventsCmd(), // Query transactions by events
		server.QueryBlocksCmd(),       // Query a range of blocks
		authcmd.QueryTxCmd(),          // Query a specific transaction by hash
		server.QueryBlockResultsCmd(), // Query block results (events, transactions)
	)

	return cmd
}

// txCommand returns a root CLI command handler for all transaction commands.
// This function creates a command tree for transaction operations in the application.
// Returns: A cobra.Command that serves as the parent for all transaction subcommands
func txCommand() *cobra.Command {
	cmd := &cobra.Command{
		Use:                        "tx",
		Short:                      "Transactions subcommands",
		DisableFlagParsing:         false,
		SuggestionsMinimumDistance: 2,
		RunE:                       client.ValidateCmd,
	}

	// Add transaction subcommands for signing, broadcasting, encoding/decoding
	cmd.AddCommand(
		authcmd.GetSignCommand(),               // Sign transactions
		authcmd.GetSignBatchCommand(),          // Sign multiple transactions at once
		authcmd.GetMultiSignCommand(),          // Multi-signature for transactions
		authcmd.GetMultiSignBatchCmd(),         // Multi-signature for multiple transactions
		authcmd.GetValidateSignaturesCommand(), // Validate transaction signatures
		authcmd.GetBroadcastCommand(),          // Broadcast signed transactions to the network
		authcmd.GetEncodeCommand(),             // Encode transactions to binary format
		authcmd.GetDecodeCommand(),             // Decode transactions from binary format
		authcmd.GetSimulateCmd(),               // Simulate transaction execution without committing
	)

	return cmd
}

// newApp creates a new instance of the Dyson application.
// This function is used to initialize the application during node startup.
// Parameters:
// - logger: Logger instance for application logging
// - db: Database instance for state persistence
// - traceStore: Writer for recording traces (if enabled)
// - appOpts: Application options for configuration
// Returns: A servertypes.Application instance ready for block processing
func newApp(
	logger log.Logger,
	db dbm.DB,
	traceStore io.Writer,
	appOpts servertypes.AppOptions,
) servertypes.Application {
	// Prepare baseapp options with default settings
	baseappOptions := server.DefaultBaseappOptions(appOpts)

	// Create and return a new Dyson application instance
	return dysonprotocol.NewDysApp(
		logger, db, traceStore, true, // true indicates this is a new application (not loading from existing state)
		appOpts,
		baseappOptions...,
	)
}

// appExport creates a new DysApp instance (optionally at a given height) and exports its state.
// This function is used for state export operations, such as upgrades or snapshots.
// Parameters:
// - logger: Logger instance for application logging
// - db: Database instance with chain state
// - traceStore: Writer for recording traces
// - height: The height at which to export state (-1 for latest height)
// - forZeroHeight: Whether to export state for block height 0
// - jailAllowedAddrs: List of addresses to not jail during export
// - appOpts: Application options for configuration
// - modulesToExport: List of specific modules to export (empty for all)
// Returns: Exported application state and error (if any)
func appExport(
	logger log.Logger,
	db dbm.DB,
	traceStore io.Writer,
	height int64,
	forZeroHeight bool,
	jailAllowedAddrs []string,
	appOpts servertypes.AppOptions,
	modulesToExport []string,
) (servertypes.ExportedApp, error) {
	// Ensure appOpts is the expected viper.Viper type
	viperAppOpts, ok := appOpts.(*viper.Viper)
	if !ok {
		return servertypes.ExportedApp{}, errors.New("appOpts is not viper.Viper")
	}

	// Set invariant check period to 1 for export operations
	viperAppOpts.Set(server.FlagInvCheckPeriod, 1)
	appOpts = viperAppOpts

	var dysApp *dysonprotocol.DysApp
	if height != -1 {
		// Initialize app at specific height for historical export
		dysApp = dysonprotocol.NewDysApp(logger, db, traceStore, false, appOpts)

		// Load state at the requested height
		if err := dysApp.LoadHeight(height); err != nil {
			return servertypes.ExportedApp{}, err
		}
	} else {
		// Initialize app with latest state
		dysApp = dysonprotocol.NewDysApp(logger, db, traceStore, true, appOpts)
	}

	// Export application state and validators
	return dysApp.ExportAppStateAndValidators(forZeroHeight, jailAllowedAddrs, modulesToExport)
}

/*
// setupDwApp initializes and starts the dwapp server for serving script web applications
func setupDwApp(svrCtx *server.Context, clientCtx client.Context, ctx context.Context, g *errgroup.Group) error {
	// Get the dwapp configuration from viper
	svrCtx.Logger.Info("Setting up dwapp server")
	dwappConfig := dwapp.DefaultConfig()

	// Try to get configuration from viper
	if v := svrCtx.Viper.Get("custom.dwapp"); v != nil {
		if err := svrCtx.Viper.UnmarshalKey("custom.dwapp", dwappConfig); err != nil {
			return fmt.Errorf("failed to parse dwapp config: %w", err)
		}
	}

	// Check CLI flag overrides
	if svrCtx.Viper.IsSet("dwapp.enable") {
		dwappConfig.Enable = svrCtx.Viper.GetBool("dwapp.enable")
	}

	if svrCtx.Viper.IsSet("dwapp.script-address-or-name-pattern") {
		dwappConfig.ScriptAddressOrNamePattern = svrCtx.Viper.GetString("dwapp.script-address-or-name-pattern")
	}

	// If dwapp is not enabled, don't start it
	if !dwappConfig.Enable {
		svrCtx.Logger.Info("dwapp server is disabled")
		return nil
	}

	// Create and start the dwapp server
	// We use client context for gRPC queries instead of direct app access
	dwappServer, err := dwapp.New(svrCtx.Logger, clientCtx, svrCtx.Viper)
	if err != nil {
		return fmt.Errorf("failed to create dwapp server: %w", err)
	}

	// Add to the errgroup to manage lifecycle
	g.Go(func() error {
		return dwappServer.Start(ctx)
	})

	return nil
}

// setupApps initializes and starts all servers: demo app and dwapp
func setupApps(svrCtx *server.Context, clientCtx client.Context, ctx context.Context, g *errgroup.Group) error {
	svrCtx.Logger.Info("Setting up application servers")

	// First set up the dwapp
	if err := setupDwApp(svrCtx, clientCtx, ctx, g); err != nil {
		return fmt.Errorf("failed to set up dw app: %w", err)
	}

	return nil

*/
