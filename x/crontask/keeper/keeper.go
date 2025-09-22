package keeper

import (
	"context"
	"encoding/binary"
	"encoding/json"
	"errors"
	"fmt"
	"strings"

	"cosmossdk.io/collections"
	"cosmossdk.io/core/store"
	errorsmod "cosmossdk.io/errors"
	"cosmossdk.io/log"
	sdkmath "cosmossdk.io/math"
	storetypes "cosmossdk.io/store/types"
	abci "github.com/cometbft/cometbft/abci/types"
	"github.com/cosmos/cosmos-sdk/baseapp"
	"github.com/cosmos/cosmos-sdk/codec"
	cdctypes "github.com/cosmos/cosmos-sdk/codec/types"
	"github.com/cosmos/cosmos-sdk/runtime"
	sdk "github.com/cosmos/cosmos-sdk/types"
	"github.com/tidwall/gjson"

	"dysonprotocol.com/x/crontask"
	crontasktypes "dysonprotocol.com/x/crontask/types"
	scripttypes "dysonprotocol.com/x/script/types"
)

var (
	// TasksKey is the prefix for the tasks collection
	TasksKey = collections.NewPrefix(0)

	// NextTaskIDKey is the key for the next task ID
	NextTaskIDKey = collections.NewPrefix(1)

	// ParamsKey is the prefix for the module parameters
	ParamsKey = collections.NewPrefix(2)

	// Task index prefixes
	TasksByAddressPrefix         = collections.NewPrefix(3)
	TasksByStatusTimestampPrefix = collections.NewPrefix(4)
	TasksByStatusGasPricePrefix  = collections.NewPrefix(5)

	// MetricsKey is the key for the metrics singleton
	MetricsKey = collections.NewPrefix(6)

	// Subscriptions map and sequence prefixes
	SubscriptionsKey      = collections.NewPrefix(7)
	NextSubscriptionIDKey = collections.NewPrefix(8)

	// Manual raw KV index prefixes (single-byte for simplicity)
	indexAddrPrefix             = []byte{0xA1}
	indexStatusTsPrefix         = []byte{0xA2}
	indexStatusGasPrefix        = []byte{0xA3}
	indexSubCreatorPrefix       = []byte{0xB1}
	indexSubStatusTypePrefix    = []byte{0xB2}
	indexSubCreatorStatusPrefix = []byte{0xB3}
)

type Keeper struct {
	cdc           codec.Codec
	storeService  store.KVStoreService
	bankKeeper    crontasktypes.BankKeeper
	accountKeeper crontasktypes.AccountKeeper
	config        crontask.Config

	// Services from the app's depinject setup
	MsgRouterService *baseapp.MsgServiceRouter
	Logger           log.Logger

	Schema collections.Schema

	// Tasks is the primary collection for tasks
	Tasks collections.Map[uint64, crontasktypes.Task]

	// NextTaskID is a sequence for task IDs
	NextTaskID collections.Sequence

	// Params stores module parameters
	Params collections.Item[crontasktypes.Params]

	// Metrics stores the aggregate metrics singleton
	Metrics collections.Item[crontasktypes.Metrics]

	// Subscriptions is the primary collection for event subscriptions
	Subscriptions collections.Map[uint64, crontasktypes.Subscription]
	// NextSubscriptionID sequence
	NextSubscriptionID collections.Sequence
}

// NewKeeper creates a new crontask Keeper instance
func NewKeeper(
	cdc codec.Codec,
	storeService store.KVStoreService,
	accountKeeper crontasktypes.AccountKeeper,
	bankKeeper crontasktypes.BankKeeper,
	msgRouter *baseapp.MsgServiceRouter,
	config crontask.Config,
	logger log.Logger,
) Keeper {
	// Add the module name to the logger
	logger = logger.With(log.ModuleKey, "x/"+crontask.ModuleName)

	sb := collections.NewSchemaBuilder(storeService)

	// plain tasks map
	tasks := collections.NewMap(
		sb,
		TasksKey,
		"tasks",
		collections.Uint64Key,
		codec.CollValue[crontasktypes.Task](cdc),
	)

	nextTaskID := collections.NewSequence(
		sb,
		NextTaskIDKey,
		"next_task_id",
	)

	// Create a Item params item for parameters storage
	params := collections.NewItem(
		sb,
		ParamsKey,
		"params",
		codec.CollValue[crontasktypes.Params](cdc),
	)

	// Create metrics singleton item
	metrics := collections.NewItem(
		sb,
		MetricsKey,
		"metrics",
		codec.CollValue[crontasktypes.Metrics](cdc),
	)

	// Subscriptions map
	subscriptions := collections.NewMap(
		sb,
		SubscriptionsKey,
		"subscriptions",
		collections.Uint64Key,
		codec.CollValue[crontasktypes.Subscription](cdc),
	)

	// Next subscription id
	nextSubID := collections.NewSequence(
		sb,
		NextSubscriptionIDKey,
		"next_subscription_id",
	)

	schema, err := sb.Build()
	if err != nil {
		panic(err)
	}

	keeper := Keeper{
		cdc:                cdc,
		storeService:       storeService,
		bankKeeper:         bankKeeper,
		accountKeeper:      accountKeeper,
		config:             config,
		Tasks:              tasks,
		NextTaskID:         nextTaskID,
		Params:             params,
		Metrics:            metrics,
		Subscriptions:      subscriptions,
		NextSubscriptionID: nextSubID,
		Schema:             schema,
		Logger:             logger,
		MsgRouterService:   msgRouter,
	}

	// Add debug logging about keeper initialization
	logger.Debug("Crontask keeper initialized",
		"msg_router_service_set", keeper.MsgRouterService != nil,
		"bank_keeper_set", keeper.bankKeeper != nil,
		"account_keeper_set", keeper.accountKeeper != nil)

	return keeper
}

// GetNextTaskID gets and increments the global task ID counter
func (k Keeper) GetNextTaskID(ctx context.Context) (uint64, error) {
	return k.NextTaskID.Next(ctx)
}

// SetTask sets a task in the store
func (k Keeper) SetTask(ctx context.Context, task crontasktypes.Task) error {
	// If an existing task with the same ID is present, remove its current index
	// entries before writing the updated task. This guarantees that secondary
	// indexes are always in sync with the primary record and mirrors the cleanup
	// logic performed in RemoveTask.

	// Attempt to fetch the previous version of the task. We purposefully ignore
	// a collections.ErrNotFound error because that simply means this is a brand
	// new task.
	if prev, err := k.Tasks.Get(ctx, task.TaskId); err == nil {
		k.removeIndexes(ctx, prev)
	} else if !errors.Is(err, collections.ErrNotFound) {
		// Any other error (e.g. I/O problems) should be reported upstream.
		return err
	}

	// Write the new / updated task and create its secondary-index keys.
	if err := k.Tasks.Set(ctx, task.TaskId, task); err != nil {
		return err
	}

	k.addIndexes(ctx, task)
	return nil
}

// GetTask gets a task by ID
func (k Keeper) GetTask(ctx context.Context, id uint64) (crontasktypes.Task, error) {
	return k.Tasks.Get(ctx, id)
}

// DeleteTask deletes a task from the store
func (k Keeper) RemoveTask(ctx context.Context, id uint64) error {
	// Load the task first so we can clean up its secondary indexes. If the task
	// does not exist we simply propagate the original collections.ErrNotFound
	// so the caller can decide how to handle it.
	task, err := k.Tasks.Get(ctx, id)
	if err != nil {
		return err
	}

	// Delete secondary-index keys (address, status+timestamp, status+gasPrice)
	k.removeIndexes(ctx, task)

	// Finally remove the primary record from the `Tasks` map.
	return k.Tasks.Remove(ctx, id)
}

// SetParams sets the crontask module parameters
func (k Keeper) SetParams(ctx context.Context, params crontasktypes.Params) error {
	fmt.Printf("SetParams called with: BlockGasLimit=%d, ExpiryLimit=%d, MaxScheduledTime=%d\n",
		params.BlockGasLimit, params.ExpiryLimit, params.MaxScheduledTime)

	// Validate parameters before attempting to set them
	if err := params.Validate(); err != nil {
		fmt.Printf("SetParams validation error: %v\n", err)
		return fmt.Errorf("invalid parameters: %w", err)
	}

	err := k.Params.Set(ctx, params)
	if err != nil {
		fmt.Printf("SetParams error when setting params: %v\n", err)
		return err
	}

	fmt.Printf("SetParams completed successfully\n")
	return nil
}

// GetParams gets the crontask module parameters
func (k Keeper) GetParams(ctx context.Context) (crontasktypes.Params, error) {
	params, err := k.Params.Get(ctx)
	if err != nil {
		// For collections.ErrNotFound, return empty params similar to SDK modules
		if errors.Is(err, collections.ErrNotFound) {
			return crontasktypes.DefaultParams(), nil
		}
		// For any other error, propagate it upward
		return crontasktypes.Params{}, err
	}
	return params, nil
}

// GetModuleParams returns the current module parameters
func (k Keeper) GetModuleParams(ctx context.Context) crontasktypes.Params {
	return crontasktypes.Params{
		BlockGasLimit:    k.config.BlockGasLimit,
		ExpiryLimit:      k.config.ExpiryLimit,
		MaxScheduledTime: k.config.MaxScheduledTime,
	}
}

// GetMetrics returns the current metrics singleton. If not set, returns zero-value metrics.
func (k Keeper) GetMetrics(ctx context.Context) (crontasktypes.Metrics, error) {
	metrics, err := k.Metrics.Get(ctx)
	if err != nil {
		if errors.Is(err, collections.ErrNotFound) {
			return crontasktypes.Metrics{}, nil
		}
		return crontasktypes.Metrics{}, err
	}
	return metrics, nil
}

// SetMetrics persists the metrics singleton.
func (k Keeper) SetMetrics(ctx context.Context, m crontasktypes.Metrics) error {
	return k.Metrics.Set(ctx, m)
}

// AddMetricsForTask updates the metrics singleton with one executed task's data.
func (k Keeper) AddMetricsForTask(ctx context.Context, t crontasktypes.Task) error {
	metrics, err := k.GetMetrics(ctx)
	if err != nil {
		return err
	}

	// total gas
	metrics.ExecutedTotalGas += t.TaskGasConsumed

	// accumulate fees using sdk.Coins helpers
	metrics.ExecutedTotalFees = sdk.Coins(metrics.ExecutedTotalFees).Add(t.TaskGasFee)

	// counts
	metrics.ExecutedTaskCount += 1

	return k.SetMetrics(ctx, metrics)
}

// bigEndian encodes uint64 big-endian
func bigEndian(u uint64) []byte {
	var b [8]byte
	binary.BigEndian.PutUint64(b[:], u)
	return b[:]
}

// addIndexes writes secondary-index entries for a task
func (k Keeper) addIndexes(ctx context.Context, t crontasktypes.Task) {
	store := k.storeService.OpenKVStore(ctx)

	// address index: prefix | creator | id
	keyAddr := append(append(indexAddrPrefix, []byte(t.Creator)...), bigEndian(t.TaskId)...)
	_ = store.Set(keyAddr, []byte{})

	// status+timestamp index
	// For SCHEDULED use scheduled time; for PENDING use creation time; for terminal statuses use execution/expiry
	var tsForIndex uint64
	switch t.Status {
	case crontasktypes.TaskStatus_SCHEDULED:
		tsForIndex = uint64(t.ScheduledTimestamp)
	case crontasktypes.TaskStatus_PENDING:
		tsForIndex = uint64(t.CreationTime)
	case crontasktypes.TaskStatus_DONE, crontasktypes.TaskStatus_FAILED:
		tsForIndex = uint64(t.ExecutionTimestamp)
	case crontasktypes.TaskStatus_EXPIRED:
		tsForIndex = uint64(t.ExpiryTimestamp)
	default:
		// fallback to creation time
		tsForIndex = uint64(t.CreationTime)
	}
	tsKey := append(indexStatusTsPrefix, []byte(t.Status)...)
	tsKey = append(tsKey, bigEndian(tsForIndex)...)
	tsKey = append(tsKey, bigEndian(t.TaskId)...)
	_ = store.Set(tsKey, []byte{})

	// status+gasPrice index: use scaled decimal gas price to preserve ordering
	scaled := t.TaskGasPrice.Amount.MulInt64(1_000_000_000_000).TruncateInt()
	var scaledU64 uint64
	if scaled.IsUint64() {
		scaledU64 = scaled.Uint64()
	} else {
		// Cap to max uint64 if it overflows; preserves monotonic ordering
		scaledU64 = ^uint64(0)
	}
	gpKey := append(indexStatusGasPrefix, []byte(t.Status)...)
	gpKey = append(gpKey, bigEndian(scaledU64)...)
	gpKey = append(gpKey, bigEndian(t.TaskId)...)
	_ = store.Set(gpKey, []byte{})
}

// removeIndexes deletes secondary-index entries for a task
func (k Keeper) removeIndexes(ctx context.Context, t crontasktypes.Task) {
	store := k.storeService.OpenKVStore(ctx)

	keyAddr := append(append(indexAddrPrefix, []byte(t.Creator)...), bigEndian(t.TaskId)...)
	_ = store.Delete(keyAddr)

	// status+timestamp index uses same timestamp selection logic as addIndexes
	var tsForIndex uint64
	switch t.Status {
	case crontasktypes.TaskStatus_SCHEDULED:
		tsForIndex = uint64(t.ScheduledTimestamp)
	case crontasktypes.TaskStatus_PENDING:
		tsForIndex = uint64(t.CreationTime)
	case crontasktypes.TaskStatus_DONE, crontasktypes.TaskStatus_FAILED:
		tsForIndex = uint64(t.ExecutionTimestamp)
	case crontasktypes.TaskStatus_EXPIRED:
		tsForIndex = uint64(t.ExpiryTimestamp)
	default:
		tsForIndex = uint64(t.CreationTime)
	}
	tsKey := append(indexStatusTsPrefix, []byte(t.Status)...)
	tsKey = append(tsKey, bigEndian(tsForIndex)...)
	tsKey = append(tsKey, bigEndian(t.TaskId)...)
	_ = store.Delete(tsKey)

	// Recompute scaled gas price key used for insertion to delete it
	scaled := t.TaskGasPrice.Amount.MulInt64(1_000_000_000_000).TruncateInt()
	var scaledU64 uint64
	if scaled.IsUint64() {
		scaledU64 = scaled.Uint64()
	} else {
		scaledU64 = ^uint64(0)
	}
	gpKey := append(indexStatusGasPrefix, []byte(t.Status)...)
	gpKey = append(gpKey, bigEndian(scaledU64)...)
	gpKey = append(gpKey, bigEndian(t.TaskId)...)
	_ = store.Delete(gpKey)
}

// addSubIndexes indexes a subscription by status+event_type and creator+status
func (k Keeper) addSubIndexes(ctx context.Context, s crontasktypes.Subscription) error {
	store := k.storeService.OpenKVStore(ctx)
	// status+event_type -> id
	key1 := append(indexSubStatusTypePrefix, []byte(s.Status)...)
	key1 = append(key1, '|')
	key1 = append(key1, []byte(s.EventType)...)
	key1 = append(key1, bigEndian(s.SubscriptionId)...)
	if err := store.Set(key1, []byte{}); err != nil {
		return errorsmod.Wrapf(err, "index write failed (status+type) for sub [%d]", s.SubscriptionId)
	}
	// creator+status -> id
	key2 := append(indexSubCreatorStatusPrefix, []byte(s.Creator)...)
	key2 = append(key2, '|')
	key2 = append(key2, []byte(s.Status)...)
	key2 = append(key2, bigEndian(s.SubscriptionId)...)
	if err := store.Set(key2, []byte{}); err != nil {
		return errorsmod.Wrapf(err, "index write failed (creator+status) for sub [%d]", s.SubscriptionId)
	}
	return nil
}

// removeSubIndexes removes subscription indexes
func (k Keeper) removeSubIndexes(ctx context.Context, s crontasktypes.Subscription) error {
	store := k.storeService.OpenKVStore(ctx)
	key1 := append(indexSubStatusTypePrefix, []byte(s.Status)...)
	key1 = append(key1, '|')
	key1 = append(key1, []byte(s.EventType)...)
	key1 = append(key1, bigEndian(s.SubscriptionId)...)
	if err := store.Delete(key1); err != nil {
		return errorsmod.Wrapf(err, "index delete failed (status+type) for sub [%d]", s.SubscriptionId)
	}
	key2 := append(indexSubCreatorStatusPrefix, []byte(s.Creator)...)
	key2 = append(key2, '|')
	key2 = append(key2, []byte(s.Status)...)
	key2 = append(key2, bigEndian(s.SubscriptionId)...)
	if err := store.Delete(key2); err != nil {
		return errorsmod.Wrapf(err, "index delete failed (creator+status) for sub [%d]", s.SubscriptionId)
	}
	return nil
}

// SetSubscription persists the subscription and maintains all related indexes.
// If old is provided, its index entries are removed before adding the new ones.
func (k Keeper) SetSubscription(ctx context.Context, old *crontasktypes.Subscription, updated crontasktypes.Subscription) error {
	// If old not provided, attempt to load previous value to clean indexes
	if old == nil {
		if prev, err := k.Subscriptions.Get(ctx, updated.SubscriptionId); err == nil {
			old = &prev
		} else if !errors.Is(err, collections.ErrNotFound) {
			return errorsmod.Wrapf(err, "failed to read previous subscription [%d]", updated.SubscriptionId)
		}
	}
	if err := k.Subscriptions.Set(ctx, updated.SubscriptionId, updated); err != nil {
		return errorsmod.Wrapf(err, "failed to save subscription [%d]", updated.SubscriptionId)
	}
	if old != nil {
		if err := k.removeSubIndexes(ctx, *old); err != nil {
			return errorsmod.Wrapf(err, "failed to remove old indexes for subscription [%d]", updated.SubscriptionId)
		}
	}
	if err := k.addSubIndexes(ctx, updated); err != nil {
		return errorsmod.Wrapf(err, "failed to add new indexes for subscription [%d]", updated.SubscriptionId)
	}
	return nil
}

// kvStore returns module store adapter for iterator utils
func (k Keeper) kvStore(ctx context.Context) storetypes.KVStore {
	return runtime.KVStoreAdapter(k.storeService.OpenKVStore(ctx))
}

// iterateStatusTimestamp returns iterator over keys for given status, ordered asc/desc
func (k Keeper) iterateStatusTimestamp(ctx context.Context, status string, reverse bool) storetypes.Iterator {
	store := k.kvStore(ctx)
	prefix := append(indexStatusTsPrefix, []byte(status)...)
	if reverse {
		return storetypes.KVStoreReversePrefixIterator(store, prefix)
	}
	return storetypes.KVStorePrefixIterator(store, prefix)
}

// iterateStatusGas returns iterator over status+gasPrice index
func (k Keeper) iterateStatusGas(ctx context.Context, status string, reverse bool) storetypes.Iterator {
	store := k.kvStore(ctx)
	prefix := append(indexStatusGasPrefix, []byte(status)...)
	if reverse {
		return storetypes.KVStoreReversePrefixIterator(store, prefix)
	}
	return storetypes.KVStorePrefixIterator(store, prefix)
}

// iterateAddress returns iterator over address index
func (k Keeper) iterateAddress(ctx context.Context, addr string) storetypes.Iterator {
	store := k.kvStore(ctx)
	prefix := append(indexAddrPrefix, []byte(addr)...)
	return storetypes.KVStorePrefixIterator(store, prefix)
}

// HandleBlockEvents receives all block events (begin, txs, end) aggregated
func (k Keeper) HandleBlockEventsWithTypes(ctx sdk.Context, eventsByType map[string][]abci.Event, typesSeen []string) {
	if len(typesSeen) == 0 {
		return
	}
	k.Logger.Info("crontask sink: HandleBlockEventsWithTypes", "types", len(typesSeen), "height", ctx.BlockHeight())

	now := ctx.BlockTime().Unix()

	// Iterate by types, loading only (status=enabled, type) via index
	for _, evType := range typesSeen {
		// iterator over keys: prefix|status|type|id for status=enabled
		store := k.kvStore(ctx)
		stPrefix := append(indexSubStatusTypePrefix, []byte("enabled")...)
		stPrefix = append(stPrefix, '|')
		stPrefix = append(stPrefix, []byte(evType)...)
		it := storetypes.KVStorePrefixIterator(store, stPrefix)
		for ; it.Valid(); it.Next() {
			key := it.Key()
			if len(key) < len(stPrefix)+8 {
				continue
			}
			id := binary.BigEndian.Uint64(key[len(key)-8:])
			sub, err := k.Subscriptions.Get(ctx, id)
			if err != nil {
				continue
			}

			// Only handle matching event types
			// We will loop events below, so just skip if all events in this block are of other types
			// Quick check: if none of the block events match this subscription type, skip updates
			// (We still evaluate per-event below.)

			// Preemptively expire
			if sub.ExpiryTimestamp > 0 && sub.ExpiryTimestamp <= now {
				old := sub
				sub.Status = "expired"
				sub.StatusMessage = fmt.Sprintf("expired at [%d]", sub.ExpiryTimestamp)
				if err := k.SetSubscription(ctx, &old, sub); err != nil {
					k.Logger.Error("failed to mark subscription expired", "id", id, "err", err)
				}
				continue
			}

			// Preemptively disable if creator lacks balance for fee
			creatorAddr, addrErr := sdk.AccAddressFromBech32(sub.Creator)
			if addrErr != nil {
				k.Logger.Error("invalid creator address in subscription; disabling", "id", id, "err", addrErr)
				old := sub
				sub.Status = "disabled"
				sub.StatusMessage = "invalid creator address"
				if err := k.SetSubscription(ctx, &old, sub); err != nil {
					k.Logger.Error("failed to persist disabled subscription", "id", id, "err", err)
					continue
				}
				continue
			}
			if !k.bankKeeper.HasBalance(ctx, creatorAddr, sub.TaskGasFee) {
				k.Logger.Info("disabling subscription due to insufficient balance", "id", id)
				old := sub
				sub.Status = "disabled"
				sub.StatusMessage = fmt.Sprintf("insufficient funds for fee [%s]", sub.TaskGasFee.String())
				if err := k.SetSubscription(ctx, &old, sub); err != nil {
					k.Logger.Error("failed to persist disabled subscription", "id", id, "err", err)
					continue
				}
				continue
			}

			if evs, ok := eventsByType[sub.EventType]; ok && len(evs) > 0 {
				for _, ev := range evs {
					if !eventMatchesFilter(ev, sub.Filter) {
						continue
					}
					if err := k.createTaskForSubscription(ctx, sub, ev); err != nil {
						k.Logger.Error("failed to create task for subscription", "id", id, "err", err)
						continue
					}
					sub.TrigerCount++
				}
			}
			// persist updated sub if changed
			old := sub
			if err := k.SetSubscription(ctx, &old, sub); err != nil {
				k.Logger.Error("failed to persist subscription update", "id", id, "err", err)
			}
		}
		it.Close()
	}
}

// eventMatchesFilter performs a basic match; placeholder to be replaced with GJSON
func eventMatchesFilter(ev abci.Event, filter string) bool {
	if filter == "" {
		return true
	}
	// Normalize event into JSON and run GJSON filter: wrap in array and use #(filter)
	// Build map[string]any for attributes, parsing JSON literal values when possible
	attrs := make(map[string]any)
	for _, a := range ev.Attributes {
		raw := a.Value
		var parsed any
		if err := json.Unmarshal([]byte(raw), &parsed); err == nil {
			attrs[a.Key] = parsed
		} else {
			attrs[a.Key] = raw
		}
	}
	obj := map[string]any{
		"type":       ev.Type,
		"attributes": attrs,
	}
	b, err := json.Marshal(obj)
	if err != nil {
		return false
	}
	wrapped := append([]byte("["), b...)
	wrapped = append(wrapped, ']')
	// Accept single-quoted literals by normalizing to double quotes for GJSON
	normalizedFilter := strings.ReplaceAll(filter, "'", "\"")
	res := gjson.GetBytes(wrapped, "#("+normalizedFilter+")")
	return res.Exists() && len(res.Array()) > 0
}

// createTaskForSubscription creates a scheduled crontask for the event
func (k Keeper) createTaskForSubscription(ctx sdk.Context, sub crontasktypes.Subscription, ev abci.Event) error {
	// Charge per-trigger fee to fee_collector
	fee := sdk.NewCoins(sub.TaskGasFee)
	creatorAddr, err := sdk.AccAddressFromBech32(sub.Creator)
	if err != nil {
		return err
	}
	if err := k.bankKeeper.SendCoinsFromAccountToModule(ctx, creatorAddr, "fee_collector", fee); err != nil {
		return errorsmod.Wrapf(err, "fee deduction failed for creator [%s]", sub.Creator)
	}

	// Normalize event and merge into kwargs under key "event"
	// Parse attribute values as JSON when possible to avoid double-quoted literals
	attrs := make(map[string]any)
	for _, a := range ev.Attributes {
		raw := a.Value
		var parsed any
		if err := json.Unmarshal([]byte(raw), &parsed); err == nil {
			attrs[a.Key] = parsed
		} else {
			ctx.Logger().Error("Error parsing attribute value as JSON", "key", a.Key, "value", raw, "error", err)
			attrs[a.Key] = raw
		}
	}
	normalized := map[string]any{
		"type":       ev.Type,
		"attributes": attrs,
	}

	var kwargsMap map[string]any
	if len(sub.Kwargs) > 0 {
		if err := json.Unmarshal([]byte(sub.Kwargs), &kwargsMap); err != nil {
			return errorsmod.Wrapf(err, "invalid kwargs JSON for subscription [%d]", sub.SubscriptionId)
		}
	} else {
		kwargsMap = make(map[string]any)
	}
	kwargsMap["event"] = normalized
	mergedKwargsBytes, err := json.Marshal(kwargsMap)
	if err != nil {
		return errorsmod.Wrapf(err, "failed to encode merged kwargs for subscription [%d]", sub.SubscriptionId)
	}

	// Build script MsgExec Any
	exec := &scripttypes.MsgExec{
		ExecutorAddress: sub.Creator,
		ScriptAddress:   sub.ScriptAddress,
		FunctionName:    sub.Function,
		Args:            sub.Args,
		Kwargs:          string(mergedKwargsBytes),
	}
	anyExec, err := cdctypes.NewAnyWithValue(exec)
	if err != nil {
		return err
	}

	// Create Task
	now := ctx.BlockTime().Unix()
	scheduled := now
	if sub.TaskScheduledTimestamp > 0 {
		scheduled = sub.TaskScheduledTimestamp
	}
	expiry := scheduled + k.config.ExpiryLimit
	if sub.TaskExpiryTimestamp > 0 {
		expiry = sub.TaskExpiryTimestamp
	}
	taskID, err := k.GetNextTaskID(ctx)
	if err != nil {
		return err
	}
	task := crontasktypes.Task{
		TaskId:              taskID,
		Creator:             sub.Creator,
		ScheduledTimestamp:  scheduled,
		ExpiryTimestamp:     expiry,
		TaskGasLimit:        sub.TaskGasLimit,
		TaskGasFee:          sub.TaskGasFee,
		TaskGasPrice:        sdk.NewDecCoinFromDec(sub.TaskGasFee.Denom, sdkmath.LegacyNewDecFromInt(sub.TaskGasFee.Amount).QuoInt64(int64(sub.TaskGasLimit))),
		Msgs:                []*cdctypes.Any{anyExec},
		Status:              crontasktypes.TaskStatus_SCHEDULED,
		CreationTime:        now,
		CreationBlockHeight: ctx.BlockHeight(),
	}
	if sub.TaskGasPrice.Denom != "" {
		task.TaskGasPrice = sub.TaskGasPrice
	}
	if err := k.SetTask(ctx, task); err != nil {
		return err
	}
	// emit triggered event
	if err := ctx.EventManager().EmitTypedEvent(&crontasktypes.EventSubscriptionTriggered{SubscriptionId: sub.SubscriptionId, Creator: sub.Creator}); err != nil {
		return errorsmod.Wrap(err, "failed to emit subscription triggered event")
	}
	return nil
}
