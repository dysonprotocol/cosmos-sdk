package cli

import (
	"errors"
	"fmt"
	"os"

	"github.com/spf13/cobra"

	"github.com/cosmos/cosmos-sdk/client"
	"github.com/cosmos/cosmos-sdk/client/flags"
	"github.com/cosmos/cosmos-sdk/client/tx"

	storagetypes "dysonprotocol.com/x/storage/types"
)

// NewTxCmd returns a root CLI command handler for all x/storage transaction commands.
func NewTxCmd() *cobra.Command {
	txCmd := &cobra.Command{
		Use:                        "storage",
		Short:                      "Storage subcommands",
		DisableFlagParsing:         true,
		SuggestionsMinimumDistance: 2,
		RunE:                       client.ValidateCmd,
	}

	txCmd.AddCommand(NewStorageSetCmd())
	txCmd.AddCommand(NewStorageDeleteCmd())

	return txCmd
}

// NewStorageSetCmd returns the CLI command handler for setting/updating a storage entry.
func NewStorageSetCmd() *cobra.Command {
	cmd := &cobra.Command{
		Use:   "set --index <index> [--data <data> | --data-path <path to data file>]",
		Short: "Set or update a storage entry with the specified index and data",
		Long: `Set or update a storage entry with the specified index and data. The owner is automatically set to the transaction signer.

You must provide either --data or --data-path but not both.
An empty data string (--data "") is allowed.

Examples:
  # Set using a file
  $ dysond tx storage set --index "config/settings" --data-path ./settings.json --from myaccount

  # Set using inline data
  $ dysond tx storage set --index "user/profile" --data '{"name": "Alice", "age": 30}' --from myaccount
  
  # Set with empty data
  $ dysond tx storage set --index "placeholder" --data "" --from myaccount`,
		RunE: func(cmd *cobra.Command, args []string) error {
			clientCtx, err := client.GetClientTxContext(cmd)
			if err != nil {
				return err
			}

			// Get the required index flag
			index, err := cmd.Flags().GetString("index")
			if err != nil {
				return err
			}
			if index == "" {
				return errors.New("--index flag is required")
			}

			// Check which data flags are explicitly set
			dataProvided := cmd.Flags().Changed("data")
			dataPathProvided := cmd.Flags().Changed("data-path")

			// Validate both are not provided
			if dataProvided && dataPathProvided {
				return errors.New("cannot provide both --data and --data-path, use only one")
			}

			// Validate at least one is provided
			if !dataProvided && !dataPathProvided {
				return errors.New("either --data or --data-path must be provided")
			}

			// Get data content based on which flag was used
			var dataContent string
			if dataProvided {
				data, err := cmd.Flags().GetString("data")
				if err != nil {
					return err
				}
				dataContent = data // This can be empty, which is allowed
			} else {
				dataPath, err := cmd.Flags().GetString("data-path")
				if err != nil {
					return err
				}
				// Read file contents
				dataBytes, err := os.ReadFile(dataPath)
				if err != nil {
					return fmt.Errorf("failed to read file %s: %w", dataPath, err)
				}
				dataContent = string(dataBytes)
			}

			// Use the sender address as the owner
			owner := clientCtx.GetFromAddress().String()

			msg := &storagetypes.MsgStorageSet{
				Owner: owner,
				Index: index,
				Data:  dataContent,
			}

			return tx.GenerateOrBroadcastTxCLI(clientCtx, cmd.Flags(), msg)
		},
	}

	cmd.Flags().String("index", "", "The unique identifier/key for the storage entry (required)")
	cmd.Flags().String("data", "", "The data to store as a string")
	cmd.Flags().String("data-path", "", "Path to the data file")

	// Mark index as required
	_ = cmd.MarkFlagRequired("index")

	flags.AddTxFlagsToCmd(cmd)

	return cmd
}

// NewStorageDeleteCmd returns the CLI command handler for deleting storage entries.
func NewStorageDeleteCmd() *cobra.Command {
	cmd := &cobra.Command{
		Use:   "delete [--indexes <indexes> | --index-prefix <prefix> [--filter <filter>]]",
		Short: "Delete storage entries by specific indexes or by prefix with optional filter",
		Long: `Delete storage entries owned by the transaction signer. You can delete either:
1. Specific entries by providing a list of indexes (--indexes)
2. All entries matching a prefix, optionally filtered (--index-prefix and --filter)

These two modes are mutually exclusive - you must use either --indexes OR --index-prefix.

Examples:
  # Delete a single entry
  $ dysond tx storage delete --indexes "config/settings" --from myaccount

  # Delete multiple specific entries
  $ dysond tx storage delete --indexes "user/profile,temp/data,cache/item" --from myaccount
  
  # Delete all entries with a specific prefix
  $ dysond tx storage delete --index-prefix "temp/" --from myaccount
  
  # Delete entries with prefix and filter (using GJSON query syntax)
  $ dysond tx storage delete --index-prefix "users/" --filter 'status == "inactive"' --from myaccount
  
  # Using other GJSON query operators
  $ dysond tx storage delete --index-prefix "users/" --filter 'age > 30' --from myaccount
  $ dysond tx storage delete --index-prefix "items/" --filter 'name % "test*"' --from myaccount`,
		RunE: func(cmd *cobra.Command, args []string) error {
			clientCtx, err := client.GetClientTxContext(cmd)
			if err != nil {
				return err
			}

			// Get all the flags
			indexes, err := cmd.Flags().GetStringSlice("indexes")
			if err != nil {
				return err
			}

			indexPrefix, err := cmd.Flags().GetString("index-prefix")
			if err != nil {
				return err
			}

			filter, err := cmd.Flags().GetString("filter")
			if err != nil {
				return err
			}

			// Validate mutual exclusivity
			hasIndexes := len(indexes) > 0
			hasIndexPrefix := indexPrefix != ""

			if hasIndexes && hasIndexPrefix {
				return errors.New("cannot specify both --indexes and --index-prefix, they are mutually exclusive")
			}

			if !hasIndexes && !hasIndexPrefix {
				return errors.New("must specify either --indexes or --index-prefix")
			}

			// Validate filter is only used with index-prefix
			if filter != "" && !hasIndexPrefix {
				return errors.New("--filter can only be used with --index-prefix")
			}

			// Use the sender address as the owner
			owner := clientCtx.GetFromAddress().String()

			msg := &storagetypes.MsgStorageDelete{
				Owner:       owner,
				Indexes:     indexes,
				IndexPrefix: indexPrefix,
				Filter:      filter,
			}

			return tx.GenerateOrBroadcastTxCLI(clientCtx, cmd.Flags(), msg)
		},
	}

	cmd.Flags().StringSlice("indexes", []string{}, "Comma-separated list of specific indexes to delete")
	cmd.Flags().String("index-prefix", "", "Delete all entries with indexes starting with this prefix")
	cmd.Flags().String("filter", "", "Optional GJSON query expression to apply when using --index-prefix. Supports ==, !=, <, <=, >, >=, %, !% operators")

	flags.AddTxFlagsToCmd(cmd)

	return cmd
}
