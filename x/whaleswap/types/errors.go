package types

import (
	sdkerrors "cosmossdk.io/errors"
)

// x/whaleswap module sentinel errors
var (
	ErrUnimplemented    = sdkerrors.Register("whaleswap", 1, "unimplemented")
	ErrInvalidAuthority = sdkerrors.Register("whaleswap", 2, "invalid authority")
)
