# TEW Thunder Makefile

# Variables
PYTHON := python3
THUNDER_SCRIPT := tew_thunder.py
TEST_SCRIPT := test_thunder.py
DEMO_SCRIPT := demo_thunder.py
L2_NODE := l2_node.py

# Default to Alice's address if none is set in the environment
ADDRESS ?= $(shell dysond keys show alice --output json | jq -r .address)

.PHONY: watch handle-change update-script deploy test clean help permissions l2-help

help:
	@echo "TEW Thunder - Available targets:"
	@echo "  make deploy       - Deploy/update the Thunder script to Alice's address"
	@echo "  make update-script ADDRESS=<addr> - Update script at specific address"
	@echo "  make test         - Run tests in tests/tew/thunder/"
	@echo "  make clean        - Clean up temporary files"
	@echo "  make watch        - Watch for changes and auto-deploy"

# Deploy or update Thunder script
deploy: update-script

update-script:
	@echo "Updating script at address: $(ADDRESS)"
	@dysond tx script update \
		--from "$(ADDRESS)" \
		--gas-adjustment 2 \
		--gas auto \
		-y -o json \
		--code-path tew_thunder.py \
	| jq -r .txhash \
	| xargs dysond q wait-tx -o json \
	| jq

# Watch for changes
watch:
	@while sleep 1; do \
		find tew_thunder.py -type f | entr -dp -s 'make update-script' ; \
	done

# Run tests
test:
	@echo "Running TEW Thunder tests..."
	cd ../.. && python -m pytest tests/tew/thunder/ -v

# Clean temporary files
clean:
	rm -f *.pyc
	rm -rf __pycache__/
	rm -f /tmp/deposit.json

# Quick channel creation helper
create-channel:
ifndef ID
	@echo "Error: Please provide channel ID"
	@echo "Usage: make create-channel ID=channel_name"
	@exit 1
endif
	@echo "Creating channel $(ID) on script at $(ADDRESS)..."
	@ALICE=$$(dysond keys show alice -a) && \
	BOB=$$(dysond keys show bob -a) && \
	dysond tx script exec \
		--script-address $(ADDRESS) \
		--function-name create_tew \
		--args '[{"instance_id":"$(ID)","committee":["'$$ALICE'","'$$BOB'"],"timeout":300}]' \
		--from alice -y

# Show channel info
channel-info:
ifndef ID
	@echo "Error: Please provide channel ID"
	@echo "Usage: make channel-info ID=channel_name"
	@exit 1
endif
	@ALICE=$$(dysond keys show alice -a) && \
	dysond query script run \
		--executor-address $$ALICE \
		--script-address $(ADDRESS) \
		--function-name get_instance_info \
		--args '["$(ID)"]' \
		--kwargs '{}' \
		-o json | jq '.result | fromjson | .result'

# Set executable permissions
.PHONY: permissions
permissions:
	chmod +x $(THUNDER_SCRIPT) $(L2_NODE) $(TEST_SCRIPT) $(DEMO_SCRIPT)

# Show L2 node help
.PHONY: l2-help
l2-help:
	$(PYTHON) $(L2_NODE) --help
