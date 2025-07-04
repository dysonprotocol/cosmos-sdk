package main

import (
	"fmt"
	"os"

	"dysonprotocol.com"
	cmd "dysonprotocol.com/dysond/cmd"

	svrcmd "github.com/cosmos/cosmos-sdk/server/cmd"
	sdk "github.com/cosmos/cosmos-sdk/types"
)

func main() {
	cfg := sdk.GetConfig()
	cfg.SetBech32PrefixForAccount("dys2", "dys2pub")                     // account addresses
	cfg.SetBech32PrefixForValidator("dys2valoper", "dys2valoperpub")     // validator operator addresses
	cfg.SetBech32PrefixForConsensusNode("dys2valcons", "dys2valconspub") // consensus addresses

	rootCmd := cmd.NewRootCmd()
	// TODO: set the default node env prefix
	if err := svrcmd.Execute(rootCmd, "DYSON", dysonprotocol.DefaultNodeHome); err != nil {
		fmt.Fprintln(rootCmd.OutOrStderr(), err)
		os.Exit(1)
	}
}
