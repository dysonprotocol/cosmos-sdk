#!/usr/bin/make -f

VERSION ?= $(shell git symbolic-ref -q --short HEAD || git describe --tags --exact-match)
COMMIT ?= $(shell git rev-parse --short HEAD)
BUILDDIR ?= $(CURDIR)/build
CURRENT_DIR = $(shell pwd)

###############################################################################
###                                Build Tags                               ###
###############################################################################

# Build tags
build_tags = netgo
ifeq ($(LEDGER_ENABLED),true)
  ifeq ($(OS),Windows_NT)
    GCCEXE = $(shell where gcc.exe 2> NUL)
    ifeq ($(GCCEXE),)
      $(error gcc.exe not installed for ledger support, please install or set LEDGER_ENABLED=false)
    else
      build_tags += ledger
    endif
  else
    UNAME_S = $(shell uname -s)
    ifeq ($(UNAME_S),OpenBSD)
      $(warning OpenBSD detected, disabling ledger support (https://github.com/cosmos/cosmos-sdk/issues/1988))
    else
      GCC = $(shell command -v gcc 2> /dev/null)
      ifeq ($(GCC),)
        $(error gcc not installed for ledger support, please install or set LEDGER_ENABLED=false)
      else
        build_tags += ledger
      endif
    endif
  endif
endif

# Handle rocksdb
ifeq ($(ROCKSDB_ENABLED),true)
  CGO_ENABLED=1
  build_tags += rocksdb
endif


build_tags += $(BUILD_TAGS)
build_tags := $(strip $(build_tags))


# look for depinject in BUILD_TAGS or add app_v1
ifeq ($(findstring app_v2,$(BUILD_TAGS)),)
  ifeq ($(findstring app_v1,$(BUILD_TAGS)),)
    build_tags += app_v1
  endif
endif

whitespace :=
whitespace += $(whitespace)
comma := ,
build_tags_comma_sep := $(subst $(whitespace),$(comma),$(build_tags))

# Linker flags
ldflags = -X github.com/cosmos/cosmos-sdk/version.Name=dyson \
		  -X github.com/cosmos/cosmos-sdk/version.AppName=dysond \
		  -X github.com/cosmos/cosmos-sdk/version.Version=$(VERSION) \
		  -X github.com/cosmos/cosmos-sdk/version.Commit=$(COMMIT) \
		  -X "github.com/cosmos/cosmos-sdk/version.BuildTags=$(build_tags_comma_sep)"

ifeq ($(LINK_STATICALLY),true)
	ldflags += -linkmode=external -extldflags "-Wl,-z,muldefs -static"
endif
ldflags := $(strip $(ldflags))

BUILD_FLAGS := -tags "$(build_tags)" -ldflags '$(ldflags)'
# check for nostrip option
ifeq (,$(findstring nostrip,$(COSMOS_BUILD_OPTIONS)))
  BUILD_FLAGS += -trimpath
endif

  

# Check for debug option
ifeq (debug,$(findstring debug,$(COSMOS_BUILD_OPTIONS)))
  BUILD_FLAGS += -gcflags "all=-N -l"
endif

###############################################################################
###                                Building                                 ###
###############################################################################


build:
	@echo "Building dysond binary..."
	@mkdir -p $(BUILDDIR)
	@go build -mod=readonly $(BUILD_FLAGS) -o $(BUILDDIR)/dysond ./dysond

install:
	@echo "Installing dysond binary..."
	@go install -mod=readonly $(BUILD_FLAGS) ./dysond
	@dysond version --long | tail -n 8

###############################################################################
###                                Testing                                  ###
###############################################################################

test: install
	@echo "--> running pytest"
	DEFAULT_BASE_DIR=/tmp/test-dysonchains python -m pytest -xs --showlocals --nf --ff ./tests/$(TEST_PATTERN) $(PYTEST_ARGS)

###############################################################################
###                                Scripts                                  ###
###############################################################################

init:
	@echo "--> Running reset_dev script (Python version)"
	./scripts/chainnet.py generate --chains 1 --nodes 2 
	./scripts/chainnet.py setup --config-file /tmp/dysonchains/chains.json --force
	

start: install
	@echo "--> Starting dyson"
	./scripts/chainnet.py start --config-file /tmp/dysonchains/chains.json --block-speed 500ms --logs --no-blocks-timeout 3


# The 'watch' target monitors .go files and restarts the application on changes.
watch:
	@echo "Watching for changes in Go files..."
	@while sleep 1; do \
		find . -name '*.go' | entr -r -c -n -d make start; \
	done

init-localnet: 
	@echo "--> Initializing dyson chain net"
	./scripts/chainnet.py generate --chains 2 --nodes 1 --hermes-config
	./scripts/chainnet.py setup --force


start-localnet: install
	@echo "--> Starting dyson chain net"
	./scripts/chainnet.py start --config-file /tmp/dysonchains/chains.json --block-speed 500ms

###############################################################################
###                                Protobuf                                 ###
###############################################################################
DOCKER := $(shell which docker)

protoVer=0.16.0
protoImageName=ghcr.io/cosmos/proto-builder:$(protoVer)
protoImage=$(DOCKER) run --rm -v $(CURDIR):/workspace --workdir /workspace $(protoImageName)

# Custom protobuf image with jsonschema support
customProtoImageName=dyson-proto-builder:$(protoVer)
customProtoImage=$(DOCKER) run --rm -v $(CURDIR):/workspace --workdir /workspace $(customProtoImageName)

proto-all: proto-format proto-lint proto-gen

# Build custom protobuf Docker image with jsonschema support
proto-build-image:
	@echo "Building custom protobuf Docker image with jsonschema support"
	@$(DOCKER) build -t $(customProtoImageName) -f Dockerfile.protobuf .

proto-gen: proto-build-image
	@echo "Generating Protobuf files"
	@$(customProtoImage) sh ./scripts/protocgen.sh

proto-update:
	@echo "Updating dependencies in ./proto"
	@$(protoImage) sh -c "buf dep update ./proto"

# Remove custom protobuf Docker image
proto-clean-image:
	@echo "Removing custom protobuf Docker image"
	@$(DOCKER) rmi $(customProtoImageName) 2>/dev/null || true

###############################################################################
###                                DYSVM                                    ###
###############################################################################

# DYSVM related paths
DYSVM_SCRIPTS_DIR := $(CURRENT_DIR)/scripts

# Main DYSVM target - runs patch, build, and embed in sequence
dysvm:
	@echo "Running complete DYSVM process..."
	@$(DYSVM_SCRIPTS_DIR)/dysvm.sh

# Apply patch to CPython submodule
dysvm-patch:
	@echo "Running DYSVM patch operation..."
	@$(DYSVM_SCRIPTS_DIR)/dysvm-patch.sh

# Build custom Python distributions
dysvm-build:
	@echo "Running DYSVM build operation..."
	@$(DYSVM_SCRIPTS_DIR)/dysvm-build.sh

# Prepare Python for go-embed-python
dysvm-embed:
	@echo "Running DYSVM embed operation..."
	@$(DYSVM_SCRIPTS_DIR)/dysvm-embed.sh

# Clean DYSVM build artifacts
dysvm-clean:
	@echo "Running DYSVM clean operation..."
	@$(DYSVM_SCRIPTS_DIR)/dysvm-clean.sh


.PHONY:  build install test init localnet start watch proto-all proto-gen proto-format proto-lint proto-update proto-build-image proto-clean-image dysvm dysvm-patch dysvm-build dysvm-embed dysvm-clean
