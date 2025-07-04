# Crontask Module

The `crontask` module enables scheduled execution of transactions on the Dyson Protocol blockchain. It allows users to create tasks that will be executed at a specific time in the future, with an expiration deadline.

## Commands

### Query Commands

The following commands are available for querying the state of the crontask module:

```bash
dysond query crontask [command]
```

#### Available Query Commands

| Command | Description |
|---------|-------------|
| `params` | Query the current crontask module parameters |
| `task-by-id` | Query a task by its unique identifier |
| `tasks-by-address` | Query all tasks created by a specific address |
| `tasks-by-status-gas-price` | Query tasks filtered by status and ordered by gas price |
| `tasks-by-status-timestamp` | Query tasks filtered by status and ordered by timestamp |

#### Example: Query Module Parameters

```bash
$ dysond query crontask params -o json | jq
{
  "params": {
    "block_gas_limit": "500000",
    "expiry_limit": "86400",
    "max_scheduled_time": "86400"
  }
}
```

The module parameters include:
- `block_gas_limit`: Maximum gas that can be consumed by scheduled tasks in a single block
- `expiry_limit`: Maximum time (in seconds) that a task can be scheduled for before expiration
- `max_scheduled_time`: Maximum time (in seconds) in the future that a task can be scheduled

#### Example: Query Tasks by Status

```bash
$ dysond query crontask tasks-by-status-timestamp "SCHEDULED" -o json | jq
{
  "tasks": [
    {
      "task_id": "15",
      "creator": "dys21q845fkkj4aev36r59fzy26x2d9gej6r4uvreg0",
      "scheduled_timestamp": "1741022904",
      "expiry_timestamp": "1741107504",
      "task_gas_limit": "200000",
      "task_gas_price": {
        "denom": "udys",
        "amount": "1"
      },
      "msgs": [
        {
          "type": "/cosmos.bank.v1beta1.MsgSend",
          "value": {
            "from_address": "dys21q845fkkj4aev36r59fzy26x2d9gej6r4uvreg0",
            "to_address": "dys21q845fkkj4aev36r59fzy26x2d9gej6r4uvreg0",
            "amount": [
              {
                "denom": "udys",
                "amount": "1"
              }
            ]
          }
        }
      ],
      "status": "SCHEDULED",
      "creation_time": "1741021112"
    }
  ]
}
```

This returns all tasks with the status "SCHEDULED" ordered by their execution timestamp.

#### Example: Query Task by ID

```bash
$ dysond query crontask task-by-id 15 -o json | jq
{
  "task": {
    "task_id": "15",
    "creator": "dys21q845fkkj4aev36r59fzy26x2d9gej6r4uvreg0",
    "scheduled_timestamp": "1741022904",
    "expiry_timestamp": "1741107504",
    "task_gas_limit": "200000",
    "task_gas_price": {
      "denom": "udys",
      "amount": "1"
    },
    "msgs": [
      {
        "type": "/cosmos.bank.v1beta1.MsgSend",
        "value": {
          "from_address": "dys21q845fkkj4aev36r59fzy26x2d9gej6r4uvreg0",
          "to_address": "dys21q845fkkj4aev36r59fzy26x2d9gej6r4uvreg0",
          "amount": [
            {
              "denom": "udys",
              "amount": "1"
            }
          ]
        }
      }
    ],
    "status": "SCHEDULED",
    "creation_time": "1741021112"
  }
}
```

### Transaction Commands

The following commands are available for creating and managing crontasks:

```bash
dysond tx crontask [command]
```

#### Available Transaction Commands

| Command | Description |
|---------|-------------|
| `create-task` | Create a new scheduled task |
| `delete-task` | Delete a scheduled task |

> **Note**: Always use `dysond q wait-tx` to wait for transactions to be committed to the blockchain before proceeding. This ensures your transaction has been processed successfully.

#### Example: Create a Scheduled Task

```bash
# Set required variables
export ADDRESS=$(dysond keys show -a alice)
export SCHEDULED_TIME=$(date -v+30M +%s)  # 30 minutes from now
export EXPIRY_TIME=$(date -v+1d +%s)      # 1 day from now
export MSG_JSON='{"@type":"/cosmos.bank.v1beta1.MsgSend","from_address":"'$ADDRESS'","to_address":"'$ADDRESS'","amount":[{"denom":"udys","amount":"1"}]}'

# Create the task and wait for transaction to be committed
dysond tx crontask create-task \
  --scheduled-timestamp $SCHEDULED_TIME \
  --expiry-timestamp $EXPIRY_TIME \
  --task-gas-limit 200000 \
  --task-gas-fee 200000dys \
  --msgs "$MSG_JSON" \
  --from $ADDRESS -y -o json | jq .txhash -r | xargs dysond q wait-tx -o json | jq
```

Note that the gas price is calculated automatically by dividing the task_gas_fee by the task_gas_limit. You don't need to specify it manually.

Output Example:
```json
{
  "height": "8744",
  "txhash": "B040E2A2C4FA71B31135047D954DC72043E086458A824A42A72687D9DB2CA1DE",
  "codespace": "",
  "code": 0,
  "data": "",
  "raw_log": "",
  "logs": [],
  "info": "",
  "gas_wanted": "200000",
  "gas_used": "50994",
  "tx": null,
  "timestamp": "",
  "events": [
    {
      "type": "tx",
      "attributes": [
        {
          "key": "fee",
          "value": "",
          "index": true
        },
        {
          "key": "fee_payer",
          "value": "dys21q845fkkj4aev36r59fzy26x2d9gej6r4uvreg0",
          "index": true
        }
      ]
    },
    {
      "type": "tx",
      "attributes": [
        {
          "key": "acc_seq",
          "value": "dys21q845fkkj4aev36r59fzy26x2d9gej6r4uvreg0/0",
          "index": true
        }
      ]
    },
    {
      "type": "tx",
      "attributes": [
        {
          "key": "signature",
          "value": "WJ4sg0fhipuv0wCLkpwJ60hfqALJWNVLgRH4YZk4ln1A0+qmBmF9lUFOKyTQUoCYKkzhaJpN+KMXR19FJ1Py8Q==",
          "index": true
        }
      ]
    },
    {
      "type": "dysonprotocol.crontask.v1.EventTaskCreated",
      "attributes": [
        {
          "key": "creator",
          "value": "\"dys21q845fkkj4aev36r59fzy26x2d9gej6r4uvreg0\"",
          "index": true
        },
        {
          "key": "scheduled_timestamp",
          "value": "\"0\"",
          "index": true
        },
        {
          "key": "task_id",
          "value": "\"15\"",
          "index": true
        }
      ]
    },
    {
      "type": "message",
      "attributes": [
        {
          "key": "action",
          "value": "/dysonprotocol.crontask.v1.MsgCreateTask",
          "index": true
        },
        {
          "key": "module",
          "value": "crontask",
          "index": true
        }
      ]
    }
  ]
}
```

## Task Status

Tasks can have the following status values:
- `SCHEDULED`: Task is scheduled for execution in the future
- `DONE`: Task has been successfully executed (called `EXECUTED` in some contexts)
- `EXPIRED`: Task wasn't executed before its expiry time
- `FAILED`: Task execution attempt failed

Note that internally, the module uses enum values for task status, so you should always use the exact string values shown above when querying by status.

## Pagination

Most query commands support pagination flags to handle large result sets. Here's an example of using pagination with the `tasks-by-status-timestamp` query:

```bash
# Get the first 5 scheduled tasks
dysond query crontask tasks-by-status-timestamp "SCHEDULED" --page-limit 5 -o json | jq

# Get the next page using the next_key
NEXT_KEY=$(dysond query crontask tasks-by-status-timestamp "SCHEDULED" --page-limit 5 -o json | jq -r .pagination.next_key)
dysond query crontask tasks-by-status-timestamp "SCHEDULED" --page-limit 5 --page-key "$NEXT_KEY" -o json | jq
```

Available pagination flags:
```bash
--page-count-total         # Count total number of records in query result
--page-key string          # Pagination key (base64 encoded)
--page-limit uint          # Maximum number of records per page
--page-offset uint         # Pagination offset (alternative to page-key)
--page-reverse             # Results in reverse order (latest first)
```

## Additional Flags

Most commands support the following flags:

```bash
--output, -o string   # Output format (text|json) (default "text")
--height int          # Use a specific height to query state at
--node string         # <host>:<port> to CometBFT RPC interface
--help, -h            # Help for the command
```