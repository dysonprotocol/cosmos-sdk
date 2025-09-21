package keeper

import (
	"context"

	cosmossdkerrors "cosmossdk.io/errors"
	whaleswapv1 "dysonprotocol.com/x/whaleswap/types"
)

func (k Keeper) UpdateParams(ctx context.Context, msg *whaleswapv1.MsgUpdateParams) (*whaleswapv1.MsgUpdateParamsResponse, error) {
	if k.authority != msg.Authority {
		return nil, whaleswapv1.ErrInvalidAuthority
	}
	if err := k.SetParams(ctx, msg.Params); err != nil {
		return nil, cosmossdkerrors.Wrapf(err, "failed to set params")
	}
	return &whaleswapv1.MsgUpdateParamsResponse{}, nil
}
