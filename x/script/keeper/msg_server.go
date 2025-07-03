package keeper

import (
	"context"
	"crypto/sha256"
	"fmt"

	cosmossdkerrors "cosmossdk.io/errors"
	scriptv1 "dysonprotocol.com/api/script/types"
	"dysonprotocol.com/x/script"
	scripttypes "dysonprotocol.com/x/script/types"
	sdk "github.com/cosmos/cosmos-sdk/types"
	sdkerrors "github.com/cosmos/cosmos-sdk/types/errors"
	"github.com/cosmos/cosmos-sdk/x/authz"
	govtypes "github.com/cosmos/cosmos-sdk/x/gov/types"
)

var _ scripttypes.MsgServer = Keeper{}

func (k Keeper) UpdateScript(ctx context.Context, msg *scripttypes.MsgUpdateScript) (*scripttypes.MsgUpdateScriptResponse, error) {
	var script scripttypes.Script
	sdkCtx := sdk.UnwrapSDKContext(ctx)
	exists, err := k.ScriptMap.Has(ctx, msg.Address)
	if err != nil {
		return nil, cosmossdkerrors.Wrap(err, "failed to check if script exists")
	}

	if !exists {
		script = scripttypes.Script{
			Address: msg.Address,
			Version: 0,
		}
	} else {
		script, err = k.ScriptMap.Get(ctx, msg.Address)
		if err != nil {
			return nil, cosmossdkerrors.Wrap(err, "failed to get existing script")
		}
	}

	// Format the code with black before setting it
	//formattedCode, err := dysvm.DysFormat(msg.Code)
	//if err != nil {
	//	k.Logger(sdkCtx).Error("failed to format code with dys_format", "error", err)
	//	formattedCode = msg.Code
	//}

	script.Code = msg.Code
	script.Version = script.Version + 1

	err = k.ScriptMap.Set(ctx, msg.Address, script)
	if err != nil {
		return nil, cosmossdkerrors.Wrap(err, "failed to set script")
	}

	// Get event manager from context
	err = sdkCtx.EventManager().EmitTypedEvent(
		&scriptv1.EventUpdateScript{
			Version: script.Version,
		})

	if err != nil {
		return nil, cosmossdkerrors.Wrap(err, "failed to emit update script event")
	}

	resp := scripttypes.MsgUpdateScriptResponse{
		Version: script.Version,
	}

	return &resp, nil
}

func (k Keeper) ExecScript(ctx context.Context, msg *scripttypes.MsgExec) (*scripttypes.MsgExecResponse, error) {
	resp := &scripttypes.MsgExecResponse{}
	var scriptObj scripttypes.Script

	// Resolve the script address using the nameservice keeper
	addr, resolvErr := k.NameserviceKeeper.ResolveNameOrAddress(ctx, msg.ScriptAddress)
	if resolvErr != nil {
		return nil, cosmossdkerrors.Wrap(resolvErr, fmt.Sprintf("failed to resolve script address: '%s'", msg.ScriptAddress))
	}

	exists, err := k.ScriptMap.Has(ctx, addr)
	if err != nil {
		return nil, cosmossdkerrors.Wrap(err, "failed to check if script exists")
	}

	if !exists {
		// create a new script
		scriptObj = scripttypes.Script{
			Address: addr,
			Version: 0,
			Code:    "",
		}
		err = k.ScriptMap.Set(ctx, addr, scriptObj)
		if err != nil {
			return nil, cosmossdkerrors.Wrap(err, "failed to set script")
		}
	} else {
		scriptObj, err = k.ScriptMap.Get(ctx, addr)
		if err != nil {
			return nil, cosmossdkerrors.Wrap(err, "failed to get script")
		}
	}

	scriptContext := ExecScriptContext{msg, &scriptObj, nil}

	// Replace BranchService with direct CacheContext usage
	sdkCtx := sdk.UnwrapSDKContext(ctx)

	// Create a cached context that creates an isolated context for the execution
	cacheCtx, write := sdkCtx.CacheContext()

	// Execute the function
	execErr := func() error {
		// Add panic recovery
		defer func() {
			if r := recover(); r != nil {
				err = fmt.Errorf("panic during script execution: %v", r)
			}
		}()

		execResp, err := k.execScript(cacheCtx, &scriptContext)
		if err != nil {
			k.Logger(sdkCtx).Error("failed to execute script", "error", err)
			return err
		}

		resp.Result = execResp.Result
		err = script.SetMsgExecResult(resp, scriptContext.AttachedMessageResults)
		if err != nil {
			k.Logger(sdkCtx).Error("failed to set msg exec result", "error", err)
			return err
		}

		// Get event manager from context
		evtCtx := sdk.UnwrapSDKContext(cacheCtx)
		evterr := evtCtx.EventManager().EmitTypedEvent(
			&scripttypes.EventExecScript{
				Request:  msg,
				Response: resp,
			})
		if evterr != nil {
			k.Logger(sdkCtx).Error("failed to emit event", "error", evterr)
			return evterr
		}

		return nil
	}()

	// If execution was successful, write state changes back to the parent context
	if execErr == nil {
		write()
	}

	return resp, execErr
}

func (k Keeper) CreateNewScript(ctx context.Context, msg *scripttypes.MsgCreateNewScript) (*scripttypes.MsgCreateNewScriptResponse, error) {
	// Create a deterministic address from the creator's address and the script content
	creatorBytes, err := k.addressCodec.StringToBytes(msg.CreatorAddress)
	if err != nil {
		return nil, cosmossdkerrors.Wrapf(err, "invalid creator address: %s", msg.CreatorAddress)
	}

	// Create a hash of the creator + code to generate a deterministic script address
	contentToHash := append(creatorBytes, []byte(msg.Code)...)
	hasher := sha256.New()
	hasher.Write(contentToHash)
	scriptAddrBytes := hasher.Sum(nil)

	// Create bech32 address from the hash
	scriptAddr, err := sdk.Bech32ifyAddressBytes(sdk.GetConfig().GetBech32AccountAddrPrefix(), scriptAddrBytes[:20])
	if err != nil {
		return nil, cosmossdkerrors.Wrapf(err, "failed to create script address")
	}

	// Check if script with this address already exists
	exists, err := k.ScriptMap.Has(ctx, scriptAddr)
	if err != nil {
		return nil, cosmossdkerrors.Wrap(err, "failed to check if script exists")
	}

	if exists {
		return nil, cosmossdkerrors.Wrapf(sdkerrors.ErrInvalidRequest, "cannot create new script: a script with address %s already exists. Each script has a unique address derived from its creator and content", scriptAddr)
	}

	// Create a new script
	script := scripttypes.Script{
		Address: scriptAddr,
		Version: 1, // Start at version 1
		Code:    msg.Code,
	}

	// Save the script
	err = k.ScriptMap.Set(ctx, scriptAddr, script)
	if err != nil {
		return nil, cosmossdkerrors.Wrap(err, "failed to set script")
	}

	// Create an authz grant to allow the creator to update this script
	sdkCtx := sdk.UnwrapSDKContext(ctx)

	// Create a generic authorization for MsgUpdateScript
	// This allows the creator to update the script in the future
	msgTypeURL := sdk.MsgTypeURL(&scripttypes.MsgUpdateScript{})
	authorization := authz.NewGenericAuthorization(msgTypeURL)

	// Convert the addresses to the correct format
	creatorAddress := sdk.AccAddress(creatorBytes)
	scriptAddress, err := k.addressCodec.StringToBytes(scriptAddr)
	if err != nil {
		return nil, cosmossdkerrors.Wrapf(err, "failed to convert script address to bytes: %s", scriptAddr)
	}

	// In authz, the script (scriptAddress) is the GRANTER and the creator (creatorAddress) is the GRANTEE
	// This allows the creator to act on behalf of the script
	err = k.AuthzKeeper.SaveGrant(ctx, creatorAddress, sdk.AccAddress(scriptAddress), authorization, nil)
	if err != nil {
		return nil, cosmossdkerrors.Wrap(err, "failed to save authz grant")
	}

	// Emit event
	err = sdkCtx.EventManager().EmitTypedEvent(
		&scriptv1.EventCreateNewScript{
			ScriptAddress:  scriptAddr,
			CreatorAddress: msg.CreatorAddress,
			Version:        script.Version,
		})
	if err != nil {
		return nil, cosmossdkerrors.Wrap(err, "failed to emit create new script event")
	}

	return &scripttypes.MsgCreateNewScriptResponse{
		ScriptAddress: scriptAddr,
		Version:       script.Version,
	}, nil
}

// UpdateParams updates the module parameters
func (k Keeper) UpdateParams(ctx context.Context, msg *scripttypes.MsgUpdateParams) (*scripttypes.MsgUpdateParamsResponse, error) {
	// Validate authority
	if k.authority != msg.Authority {
		return nil, cosmossdkerrors.Wrapf(govtypes.ErrInvalidSigner, "invalid authority; expected %s, got %s", k.authority, msg.Authority)
	}

	// Validate the parameters
	if err := msg.Params.Validate(); err != nil {
		return nil, cosmossdkerrors.Wrap(err, "invalid parameters")
	}

	// Set the parameters
	if err := k.SetParams(ctx, msg.Params); err != nil {
		return nil, cosmossdkerrors.Wrap(err, "failed to set parameters")
	}

	return &scripttypes.MsgUpdateParamsResponse{}, nil
}

// HandleRunRecovery is an exported version of handleRunRecovery for testing
func HandleRunRecovery(r interface{}) error {
	return handleRunRecovery(r)
}

func handleRunRecovery(r interface{}) error {
	fmt.Printf("Handle recovery: %v\n", r)
	switch rec := r.(type) {
	case nil:
		// No panic, just return nil or handle gracefully
		return nil
	case error:
		if sdkerrors.ErrOutOfGas.Is(rec) {
			return cosmossdkerrors.Wrapf(sdkerrors.ErrOutOfGas,
				"script ran out of gas (original error: %v)", rec.Error(),
			)
		}
		// Additional checks for other error types
		// if cosmossdkerrors.Is(rec, sdkerrors.ErrXYZ) { ... }
		return sdkerrors.ErrPanic.Wrapf("script panic (error type): %v", rec.Error())
	default:
		// Panic with something that wasn't an error
		return sdkerrors.ErrPanic.Wrapf("script panic (non-error type): %v", rec)
	}
}
