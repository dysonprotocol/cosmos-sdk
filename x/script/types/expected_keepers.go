package types

import (
	"context"
	"time"

	"cosmossdk.io/core/address"
	sdk "github.com/cosmos/cosmos-sdk/types"
	"github.com/cosmos/cosmos-sdk/x/authz"
)

// AccountKeeper defines the expected interface for the account keeper
type AccountKeeper interface {
	AddressCodec() address.Codec

	// NewAccount returns a new account with the next account number. Does not save the new account to the store.
	NewAccount(context.Context, sdk.AccountI) sdk.AccountI

	// GetAccount retrieves an account from the store.
	GetAccount(ctx context.Context, addr sdk.AccAddress) sdk.AccountI

	// SetAccount sets an account in the store.
	SetAccount(context.Context, sdk.AccountI)

	// RemoveAccount Remove an account in the store.
	RemoveAccount(ctx context.Context, acc sdk.AccountI)

	GetModuleAccount(ctx context.Context, moduleName string) sdk.ModuleAccountI
}

// BankKeeper defines the expected interface needed to retrieve account balances.
type BankKeeper interface {
	SpendableCoins(ctx context.Context, addr sdk.AccAddress) sdk.Coins
}

// NameserviceKeeper defines the expected interface for the nameservice module
// to resolve names to addresses
type NameserviceKeeper interface {
	// ResolveNameOrAddress resolves a name or address to a valid address
	ResolveNameOrAddress(ctx context.Context, nameOrAddress string) (string, error)
}

// BranchKeeper defines the expected interface for branched execution with gas limit
type BranchKeeper interface {
	// ExecuteWithGasLimit runs fn with a specific gas limit returning gas used, a write function, and any error
	ExecuteWithGasLimit(ctx context.Context, gasLimit uint64, fn func(ctx context.Context) error) (uint64, func(), error)
}

// AuthzKeeper defines the expected interface for the authz module
type AuthzKeeper interface {
	// SaveGrant saves an authorization grant to the grantee on behalf of the granter
	SaveGrant(ctx context.Context, grantee, granter sdk.AccAddress, authorization authz.Authorization, expiration *time.Time) error
}
