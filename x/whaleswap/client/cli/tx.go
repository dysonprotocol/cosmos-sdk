package cli

import (
	"fmt"
	"strings"

	"github.com/spf13/cobra"

	"github.com/cosmos/cosmos-sdk/client"
	"github.com/cosmos/cosmos-sdk/client/flags"
	"github.com/cosmos/cosmos-sdk/client/tx"

	whaleswaptypes "dysonprotocol.com/x/whaleswap/types"
)

// CmdTakeOffer provides a custom CLI for taking one or more offers using a repeatable
// string array flag. Each occurrence encodes a single TakeItem in a simple key=value format.
//
// Usage examples:
//
//	dysond tx whaleswap take-offer \
//	  --trades "offer_id=1" \
//	  --trades "offer_id=2,take_units=10" \
//	  --from alice
//
// Accepted keys per item:
//   - offer_id (required)
//   - take_units (optional; defaults to full remaining)
func CmdTakeOffer() *cobra.Command {
	cmd := &cobra.Command{
		Use:   "take-offer",
		Short: "Take one or more offers (batch)",
		RunE: func(cmd *cobra.Command, args []string) error {
			clientCtx, err := client.GetClientTxContext(cmd)
			if err != nil {
				return err
			}

			tradeSpecs, err := cmd.Flags().GetStringArray("trades")
			if err != nil {
				return err
			}
			if len(tradeSpecs) == 0 {
				return fmt.Errorf("at least one --trades entry is required; format 'offer_id=<id>[,take_units=<int>]' and repeat the flag per item")
			}

			items := make([]whaleswaptypes.TakeItem, 0, len(tradeSpecs))
			for _, spec := range tradeSpecs {
				spec = strings.TrimSpace(spec)
				if spec == "" {
					return fmt.Errorf("empty --trades entry")
				}
				var offerIDStr string
				var takeUnits string
				parts := strings.Split(spec, ",")
				for _, p := range parts {
					kv := strings.SplitN(strings.TrimSpace(p), "=", 2)
					if len(kv) != 2 {
						return fmt.Errorf("invalid --trades entry '%s' (want key=value pairs)", spec)
					}
					key := strings.TrimSpace(kv[0])
					val := strings.TrimSpace(kv[1])
					switch key {
					case "offer_id", "offerId":
						offerIDStr = val
					case "take_units", "takeUnits":
						takeUnits = val
					default:
						return fmt.Errorf("unknown key '%s' in --trades entry '%s'", key, spec)
					}
				}
				if offerIDStr == "" {
					return fmt.Errorf("offer_id is required in --trades entry '%s'", spec)
				}
				items = append(items, whaleswaptypes.TakeItem{OfferId: parseUintOrPanic(offerIDStr), TakeUnits: takeUnits})
			}

			msg := &whaleswaptypes.MsgTakeOffer{
				Taker:  clientCtx.GetFromAddress().String(),
				Trades: items,
			}
			return tx.GenerateOrBroadcastTxCLI(clientCtx, cmd.Flags(), msg)
		},
	}

	cmd.Flags().StringArray("trades", nil, "Repeatable; format 'offer_id=<id>[,take_units=<int>]' (repeat flag per item)")
	// take mode removed; TAKE_ALL implicit
	flags.AddTxFlagsToCmd(cmd)
	return cmd
}

func parseUintOrPanic(s string) uint64 {
	// Minimal, strict parse; we bubble errors as clear CLI messages above; this is defensive
	var u uint64
	for _, ch := range s {
		if ch < '0' || ch > '9' {
			panic(fmt.Errorf("invalid unsigned integer: %s", s))
		}
	}
	// Fast path since we validated digits only
	for i := 0; i < len(s); i++ {
		u = u*10 + uint64(s[i]-'0')
	}
	return u
}
