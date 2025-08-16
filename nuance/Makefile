# Makefile

# Default to Alice's address if none is set in the environment
NAME ?= "alice"
ADDRESS ?= $(shell dysond keys show $$NAME --output json | jq -r .address)
# Default API port
API_PORT ?= 1317

.PHONY: watch handle-change update-script upload-file create-script update generate-sri hashes publish-lorem publish-lorem-tagged publish-post set-settings

watch:
	@while sleep 1; do \
		find script.py storage -type f | entr -dp -s 'make handle-change FILE="$$0"' ; \
	done


handle-change:
	@echo "File changed: $(FILE)"
ifneq ($(FILE),)

	@if [ "$(FILE)" = `pwd`/"script.py" ]; then \
		$(MAKE) update-script; \
	else \
		$(MAKE) upload-file FILE="$(FILE)"; \
	fi
else
	@echo "No FILE specified, ignoring change."
endif

update-script:
	@echo "Updating script [$(NAME)] at address: $(ADDRESS)"
	@dysond tx script update \
		--from "$$NAME" \
		--gas-adjustment 2 \
		--gas auto \
		-y -o json \
		--code-path script.py \
	| jq -r .txhash \
	| xargs dysond q wait-tx -o json \
	| jq

upload-file:
	@index=$$(echo "$$FILE" | sed 's|.*storage/||') && \
	echo "Uploading file '$$index'..."; \
	dysond tx storage set \
		--gas-adjustment 2 \
		--gas auto \
		--from "$$NAME" \
		--index "$$index" \
		--data "$$(cat "$$FILE")" \
		-y -o json \
	| jq -r .txhash \
	| xargs dysond q wait-tx -o json \
	| jq

update-all:
	@echo "Updating script and uploading all storage files..."
	@$(MAKE) update-script
	@echo "Uploading all storage files..."
	@find storage -type f | while read -r file; do \
		$(MAKE) upload-file FILE="$$file"; \
	done
	@echo "Update complete!"

# Generate SRI hashes and update importmap.json
generate-sri-hashes:
	@echo "Updating integrity hashes in importmap.json..."
	@set -e; \
	if [ ! -f storage/static/importmap.json ]; then \
	  echo "ERROR: importmap.json not found" >&2; exit 1; \
	fi; \
	jq -r '.imports | to_entries[] | "\(.key) \(.value)"' storage/static/importmap.json | while read -r name url; do \
	  echo "  -> $$name"; \
	  tmp=$$(mktemp); \
	  if ! curl -fsSL "$$url" -o "$$tmp"; then \
	    echo "Failed to download $$url" >&2; rm -f "$$tmp"; exit 1; \
	  fi; \
	  hash=$$(openssl dgst -sha384 -binary "$$tmp" | openssl base64 -A); \
	  rm -f "$$tmp"; \
	  newjson=$$(jq --arg url "$$url" --arg hash "sha384-$$hash" '.integrity[$$url] = $$hash' storage/static/importmap.json); \
	  echo "$$newjson" > storage/static/importmap.json; \
	done; \
	echo "Integrity hashes updated successfully."

set-settings:
	@echo "Setting BASE_DOMAIN in storage for address: $(ADDRESS)"
	@dysond tx storage set \
		--gas-adjustment 2 \
		--gas auto \
		--from "$$NAME" \
		--index "settings" \
		--data '{"BASE_DOMAIN":"http://$(ADDRESS).localhost:$(API_PORT)"}' \
		-y -o json \
	| jq -r .txhash \
	| xargs dysond q wait-tx -o json \
	| jq
