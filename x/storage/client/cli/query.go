package cli

import (
	"context"
	"encoding/base64"
	"fmt"

	"github.com/spf13/cobra"

	"github.com/cosmos/cosmos-sdk/client"
	"github.com/cosmos/cosmos-sdk/client/flags"

	storagetypes "dysonprotocol.com/x/storage/types"
)

// NewQueryCmd returns a root CLI command handler for all x/storage query commands.
func NewQueryCmd() *cobra.Command {
	queryCmd := &cobra.Command{
		Use:                        "storage",
		Short:                      "Querying commands for the storage module",
		DisableFlagParsing:         true,
		SuggestionsMinimumDistance: 2,
		RunE:                       client.ValidateCmd,
	}

	queryCmd.AddCommand(NewQueryStorageGetCmd())
	queryCmd.AddCommand(NewQueryStorageListCmd())

	return queryCmd
}

// NewQueryStorageGetCmd returns the CLI command handler for querying a specific storage entry.
func NewQueryStorageGetCmd() *cobra.Command {
	cmd := &cobra.Command{
		Use:   "get <owner> --index <index>",
		Short: "Query the value of an index in the storage by owner",
		Long: `Query a specific storage entry by owner address and index.

Examples:
  # Get a storage entry
  $ dysond query storage get dys21... --index "config/settings"
  
  # Get a storage entry with JSON output
  $ dysond query storage get dys21... --index "user/profile" --output json
  
  # Extract a specific field from the storage data
  $ dysond query storage get dys21... --index "user/profile" --extract "email"
  
  # Extract a nested field
  $ dysond query storage get dys21... --index "config/app" --extract "database.connection.host"`,
		Args: cobra.ExactArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			clientCtx, err := client.GetClientQueryContext(cmd)
			if err != nil {
				return err
			}

			owner := args[0]
			index, err := cmd.Flags().GetString("index")
			if err != nil {
				return err
			}
			extract, err := cmd.Flags().GetString("extract")
			if err != nil {
				return err
			}

			if index == "" {
				return fmt.Errorf("--index flag is required")
			}

			queryClient := storagetypes.NewQueryClient(clientCtx)

			req := &storagetypes.QueryStorageGetRequest{
				Owner:   owner,
				Index:   index,
				Extract: extract,
			}

			res, err := queryClient.StorageGet(context.Background(), req)
			if err != nil {
				return err
			}

			return clientCtx.PrintProto(res)
		},
	}

	cmd.Flags().String("index", "", "The index/key to query (required)")
	cmd.Flags().String("extract", "", "Optional GJSON path to extract sub-field from data")
	_ = cmd.MarkFlagRequired("index")

	flags.AddQueryFlagsToCmd(cmd)

	return cmd
}

// NewQueryStorageListCmd returns the CLI command handler for listing storage entries.
func NewQueryStorageListCmd() *cobra.Command {
	cmd := &cobra.Command{
		Use:   "list <owner> [--index-prefix <prefix>]",
		Short: "List all storage entries for an owner, optionally filtered by index prefix",
		Long: `List all storage entries for a given owner address, with optional filtering by index prefix.

Examples:
  # List all storage entries for an owner
  $ dysond query storage list dys21...
  
  # List storage entries with a specific prefix
  $ dysond query storage list dys21... --index-prefix "config/"
  
  # List with pagination
  $ dysond query storage list dys21... --limit 10 --offset 20
  
  # Filter entries where data.status equals "active"
  $ dysond query storage list dys21... --filter "status==active"
  
  # Filter entries where data.count is greater than 10
  $ dysond query storage list dys21... --filter "count>10"
  
  # Extract only the 'name' field from each entry's data
  $ dysond query storage list dys21... --extract "name"
  
  # Combine prefix, filter, and extract
  $ dysond query storage list dys21... --index-prefix "user/" --filter "active==true" --extract "profile.username"
  
  # Filter with complex conditions (e.g., name contains "test")
  $ dysond query storage list dys21... --filter 'name%"*test*"'`,
		Args: cobra.ExactArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			clientCtx, err := client.GetClientQueryContext(cmd)
			if err != nil {
				return err
			}

			owner := args[0]
			indexPrefix, err := cmd.Flags().GetString("index-prefix")
			if err != nil {
				return err
			}
			filter, err := cmd.Flags().GetString("filter")
			if err != nil {
				return err
			}
			extract, err := cmd.Flags().GetString("extract")
			if err != nil {
				return err
			}

			queryClient := storagetypes.NewQueryClient(clientCtx)

			pageReq, err := client.ReadPageRequest(cmd.Flags())
			if err != nil {
				return err
			}

			// Decode base64 page key if provided (CLI sends base64, keeper expects raw bytes)
			if len(pageReq.Key) > 0 {
				// Try to decode as base64, if it fails, assume it's already raw bytes
				if decoded, decodeErr := base64.StdEncoding.DecodeString(string(pageReq.Key)); decodeErr == nil {
					pageReq.Key = decoded
				}
			}

			req := &storagetypes.QueryStorageListRequest{
				Owner:       owner,
				IndexPrefix: indexPrefix,
				Filter:      filter,
				Extract:     extract,
				Pagination:  pageReq,
			}

			res, err := queryClient.StorageList(context.Background(), req)
			if err != nil {
				return err
			}

			return clientCtx.PrintProto(res)
		},
	}

	cmd.Flags().String("index-prefix", "", "Filter entries by index prefix")
	cmd.Flags().String("filter", "", "Optional GJSON query; entry included only if query matches. Supports ==, !=, <, <=, >, >=, %, !% operators")
	cmd.Flags().String("extract", "", "Optional GJSON path to extract sub-field from each entry's data")
	flags.AddQueryFlagsToCmd(cmd)
	flags.AddPaginationFlagsToCmd(cmd, "storage entries")

	return cmd
}
