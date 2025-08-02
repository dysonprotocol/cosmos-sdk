# Dyson Protocol – Make Dwapps, Get Paid

**Host Python scripts, serve decentralized websites, and run scheduled tasks with trustless, censorship-resistant execution. Trade names in a dynamic on-chain market, mint custom tokens and NFTs, and store arbitrary data—all fully on-chain.**

---

## What & Why

- **Problem**  
  - Blockchain DApp UIs still load from centralized servers—developers host them off-chain, and end-users can't self-host or audit the code.

- **Solution**  
  - Store HTML/CSS/JS assets in the chain's storage so browsers load UI from the ledger.  
  - Push application logic on-chain and execute periodic jobs (crontasks) without any off-chain trigger.  
  - Run a dynamic on-chain name market using Harberger-style fees.  
  - Mint custom tokens and NFT classes based on on-chain names.  
  - Store arbitrary data in the chain’s storage module.

- **Key Use Cases**  
  - **Autonomous payouts**: schedule hourly dividend distributions without users having to claim.  
  - **Timed auctions**: start and end bids exactly on-chain, with no external cron.  
  - **Game rounds**: progress players automatically through time-boxed stages.  
  - **Price oracles**: post market data at fixed intervals, fully on-chain.  
  - **Nameservice-driven assets**: register and trade domain-backed NFTs in a live marketplace.

- **Outcome**  
  - **A spectrum of security**: from fully trustless script and web UI, to fully centralized, depending on your needs.


## Installation




### 0. Build the dysvm dependencies



```bash
%%bash
make dysvm
```

    Running complete DYSVM process...


    +++ dirname /Users/user/dysonprotocol2/scripts/dysvm.sh
    ++ cd /Users/user/dysonprotocol2/scripts
    ++ pwd
    + SCRIPT_DIR=/Users/user/dysonprotocol2/scripts
    + verify_requirements
    + echo 'Verifying system requirements...'
    + local errors=0
    + check_go_version
    + command_exists go
    + command -v go


    Verifying system requirements...


    ++ go version
    ++ sed 's/go version go\([0-9.]*\).*/\1/'
    + local go_version=1.24.3
    + local required_version=1.24
    ++ echo 1.24.3
    ++ cut -d. -f1
    + local go_major=1
    ++ echo 1.24.3
    ++ cut -d. -f2
    + local go_minor=24
    ++ echo 1.24
    ++ cut -d. -f1
    + local req_major=1
    ++ echo 1.24
    ++ cut -d. -f2
    + local req_minor=24
    + '[' 1 -gt 1 ']'
    + '[' 1 -eq 1 ']'
    + '[' 24 -ge 24 ']'
    + echo '✓ Go version 1.24.3 (>= 1.24 required)'
    + return 0


    ✓ Go version 1.24.3 (>= 1.24 required)
    ✓ Git found
    ✓ Make found


    + command_exists git
    + command -v git
    + echo '✓ Git found'
    + command_exists make
    + command -v make
    + echo '✓ Make found'
    + check_python
    + local python_cmd=
    + for cmd in python3.12 python3
    + command_exists python3.12
    + command -v python3.12
    ++ python3.12 --version
    ++ grep -oE '[0-9]+\.[0-9]+'
    + local version=3.12
    ++ echo 3.12
    ++ cut -d. -f1
    + local major=3
    ++ echo 3.12
    ++ cut -d. -f2
    + local minor=12
    ++ echo 3.12
    ++ cut -d. -f1-2
    + [[ 3.12 == \3\.\1\2 ]]
    + python_cmd=python3.12
    + echo '✓ Python version 3.12 (>= 3.12 required) found at python3.12'
    + break


    ✓ Python version 3.12 (>= 3.12 required) found at python3.12


    + '[' -z python3.12 ']'
    + python3.12 -m venv --help
    + echo '✓ Python venv module available'
    + return 0
    + '[' 0 -gt 0 ']'


    ✓ Python venv module available
    ✅ All requirements verified successfully


    + echo '✅ All requirements verified successfully'
    + echo ''


    


    + echo 'Running DYSVM operations...'
    + /Users/user/dysonprotocol2/scripts/dysvm-patch.sh


    Running DYSVM operations...


    +++ dirname /Users/user/dysonprotocol2/scripts/dysvm-patch.sh
    ++ cd /Users/user/dysonprotocol2/scripts
    ++ pwd
    + SCRIPT_DIR=/Users/user/dysonprotocol2/scripts
    ++ cd /Users/user/dysonprotocol2/scripts/..
    ++ pwd
    + REPO_ROOT=/Users/user/dysonprotocol2
    + DYSVM_DIR=/Users/user/dysonprotocol2/dysvm
    + CPYTHON_DIR=/Users/user/dysonprotocol2/dysvm/cpython
    + PATCH_FILE=/Users/user/dysonprotocol2/dysvm/patch
    + echo 'Applying patch to CPython...'
    + cd /Users/user/dysonprotocol2/dysvm/cpython
    + git checkout -- .


    Applying patch to CPython...


    + cd /Users/user/dysonprotocol2/dysvm/cpython
    + patch -p1


    patching file 'Objects/bytesobject.c'
    patching file 'Objects/capsule.c'
    patching file 'Objects/cellobject.c'
    patching file 'Objects/classobject.c'
    patching file 'Objects/codeobject.c'
    patching file 'Objects/descrobject.c'
    patching file 'Objects/fileobject.c'
    patching file 'Objects/frameobject.c'
    patching file 'Objects/funcobject.c'
    patching file 'Objects/genobject.c'
    patching file 'Objects/memoryobject.c'
    patching file 'Objects/methodobject.c'
    patching file 'Objects/object.c'
    patching file 'Objects/typeobject.c'
    patching file 'Objects/unicodeobject.c'
    patching file 'Objects/weakrefobject.c'
    patching file 'Python/ceval.c'
    patching file 'Python/context.c'
    patching file 'Python/hamt.c'


    + echo 'Patch applied successfully'


    Patch applied successfully


    + /Users/user/dysonprotocol2/scripts/dysvm-build.sh
    +++ dirname /Users/user/dysonprotocol2/scripts/dysvm-build.sh
    ++ cd /Users/user/dysonprotocol2/scripts
    ++ pwd
    + SCRIPT_DIR=/Users/user/dysonprotocol2/scripts
    ++ cd /Users/user/dysonprotocol2/scripts/..
    ++ pwd
    + REPO_ROOT=/Users/user/dysonprotocol2
    + DYSVM_DIR=/Users/user/dysonprotocol2/dysvm
    + CPYTHON_DIR=/Users/user/dysonprotocol2/dysvm/cpython
    + PYTHON_BUILD_STANDALONE_DIR=/Users/user/dysonprotocol2/dysvm/python-build-standalone
    + source /Users/user/dysonprotocol2/scripts/dysvm.env
    ++ export PYTHON_VERSION=3.12.11
    ++ PYTHON_VERSION=3.12.11
    ++ export PYTHON_VERSION_SHORT=3.12
    ++ PYTHON_VERSION_SHORT=3.12
    ++ export PYTHON_CUSTOM_VERSION=custom
    ++ PYTHON_CUSTOM_VERSION=custom
    + echo 'Building custom Python distributions...'
    + EXTRA_CFLAGS='-fno-fast-math -ffp-contract=off'


    Building custom Python distributions...


    ++ uname -m
    + ARCH=arm64
    + '[' arm64 = x86_64 ']'
    + '[' arm64 = arm64 ']'
    + :
    + '[' -n '' ']'
    + export 'CFLAGS=-fno-fast-math -ffp-contract=off'
    + CFLAGS='-fno-fast-math -ffp-contract=off'
    ++ uname -s
    + '[' Darwin = Darwin ']'
    + cd /Users/user/dysonprotocol2/dysvm/python-build-standalone
    +++ uname -m
    ++ '[' arm64 = arm64 ']'
    ++ echo aarch64-apple-darwin
    + PYBUILD_PYTHON_VERSION=3.12.11
    + python3 build-macos.py --python cpython-3.12 --python-source /Users/user/dysonprotocol2/dysvm/cpython --target-triple aarch64-apple-darwin --options noopt


    Requirement already satisfied: attrs==24.3.0 in ./build/venv.macos/lib/python3.12/site-packages (from -r /Users/user/dysonprotocol2/dysvm/python-build-standalone/requirements.txt (line 3)) (24.3.0)
    Requirement already satisfied: certifi==2024.12.14 in ./build/venv.macos/lib/python3.12/site-packages (from -r /Users/user/dysonprotocol2/dysvm/python-build-standalone/requirements.txt (line 9)) (2024.12.14)
    Requirement already satisfied: charset-normalizer==3.4.1 in ./build/venv.macos/lib/python3.12/site-packages (from -r /Users/user/dysonprotocol2/dysvm/python-build-standalone/requirements.txt (line 13)) (3.4.1)
    Requirement already satisfied: docker==7.1.0 in ./build/venv.macos/lib/python3.12/site-packages (from -r /Users/user/dysonprotocol2/dysvm/python-build-standalone/requirements.txt (line 107)) (7.1.0)
    Requirement already satisfied: idna==3.10 in ./build/venv.macos/lib/python3.12/site-packages (from -r /Users/user/dysonprotocol2/dysvm/python-build-standalone/requirements.txt (line 111)) (3.10)
    Requirement already satisfied: jinja2==3.1.5 in ./build/venv.macos/lib/python3.12/site-packages (from -r /Users/user/dysonprotocol2/dysvm/python-build-standalone/requirements.txt (line 115)) (3.1.5)
    Requirement already satisfied: jsonschema==4.23.0 in ./build/venv.macos/lib/python3.12/site-packages (from -r /Users/user/dysonprotocol2/dysvm/python-build-standalone/requirements.txt (line 119)) (4.23.0)
    Requirement already satisfied: jsonschema-specifications==2024.10.1 in ./build/venv.macos/lib/python3.12/site-packages (from -r /Users/user/dysonprotocol2/dysvm/python-build-standalone/requirements.txt (line 123)) (2024.10.1)
    Requirement already satisfied: markupsafe==3.0.2 in ./build/venv.macos/lib/python3.12/site-packages (from -r /Users/user/dysonprotocol2/dysvm/python-build-standalone/requirements.txt (line 127)) (3.0.2)
    Requirement already satisfied: pyyaml==6.0.2 in ./build/venv.macos/lib/python3.12/site-packages (from -r /Users/user/dysonprotocol2/dysvm/python-build-standalone/requirements.txt (line 190)) (6.0.2)
    Requirement already satisfied: referencing==0.35.1 in ./build/venv.macos/lib/python3.12/site-packages (from -r /Users/user/dysonprotocol2/dysvm/python-build-standalone/requirements.txt (line 245)) (0.35.1)
    Requirement already satisfied: requests==2.32.3 in ./build/venv.macos/lib/python3.12/site-packages (from -r /Users/user/dysonprotocol2/dysvm/python-build-standalone/requirements.txt (line 251)) (2.32.3)
    Requirement already satisfied: rpds-py==0.22.3 in ./build/venv.macos/lib/python3.12/site-packages (from -r /Users/user/dysonprotocol2/dysvm/python-build-standalone/requirements.txt (line 255)) (0.22.3)
    Requirement already satisfied: six==1.17.0 in ./build/venv.macos/lib/python3.12/site-packages (from -r /Users/user/dysonprotocol2/dysvm/python-build-standalone/requirements.txt (line 362)) (1.17.0)
    Requirement already satisfied: tomli==2.2.1 in ./build/venv.macos/lib/python3.12/site-packages (from -r /Users/user/dysonprotocol2/dysvm/python-build-standalone/requirements.txt (line 366)) (2.2.1)
    Requirement already satisfied: urllib3==2.3.0 in ./build/venv.macos/lib/python3.12/site-packages (from -r /Users/user/dysonprotocol2/dysvm/python-build-standalone/requirements.txt (line 400)) (2.3.0)
    Requirement already satisfied: zstandard==0.23.0 in ./build/venv.macos/lib/python3.12/site-packages (from -r /Users/user/dysonprotocol2/dysvm/python-build-standalone/requirements.txt (line 406)) (0.23.0)


    
    [1m[[0m[34;49mnotice[0m[1;39;49m][0m[39;49m A new release of pip is available: [0m[31;49m25.0.1[0m[39;49m -> [0m[32;49m25.2[0m
    [1m[[0m[34;49mnotice[0m[1;39;49m][0m[39;49m To update, run: [0m[32;49m/Users/user/dysonprotocol2/dysvm/python-build-standalone/build/venv.macos/bin/python3.12 -m pip install --upgrade pip[0m


    make[1]: Nothing to be done for `default'.
    compressing Python archive to /Users/user/dysonprotocol2/dysvm/python-build-standalone/dist/cpython-3.12.11-aarch64-apple-darwin-noopt-20250612T0816.tar.zst
    /Users/user/dysonprotocol2/dysvm/python-build-standalone/dist/cpython-3.12.11-aarch64-apple-darwin-noopt-20250612T0816.tar.zst has SHA256 35fda279388bb8e8517c7e0ebe8f6c1bd2a50449f43ad6d540e3060d50c1ae48


    + echo 'Python distributions built successfully'


    Python distributions built successfully


    + /Users/user/dysonprotocol2/scripts/dysvm-embed.sh
    +++ dirname /Users/user/dysonprotocol2/scripts/dysvm-embed.sh
    ++ cd /Users/user/dysonprotocol2/scripts
    ++ pwd
    + SCRIPT_DIR=/Users/user/dysonprotocol2/scripts
    ++ cd /Users/user/dysonprotocol2/scripts/..
    ++ pwd
    + REPO_ROOT=/Users/user/dysonprotocol2
    + DYSVM_DIR=/Users/user/dysonprotocol2/dysvm
    + PYTHON_BUILD_STANDALONE_DIR=/Users/user/dysonprotocol2/dysvm/python-build-standalone
    + GO_EMBED_PYTHON_DIR=/Users/user/dysonprotocol2/dysvm/go-embed-python
    + TEMP_DIR=/tmp
    + PYTHON_VERSION=3.12.11
    + PYTHON_DIST_NAME=cpython-3.12.11
    + CUSTOM_VERSION=custom
    ++ uname -s
    + '[' Darwin = Darwin ']'
    ++ uname -m
    + '[' arm64 = arm64 ']'
    + OS=darwin
    + ARCH=arm64
    + DIST_PATTERN=apple-darwin-pgo+lto
    + DIST_FULL=apple-darwin-pgo+lto-full
    + ARCH_NAME=aarch64
    + echo 'Preparing custom Python for go-embed-python...'
    + mkdir -p /tmp/python-download


    Preparing custom Python for go-embed-python...


    ++ ls -t /Users/user/dysonprotocol2/dysvm/python-build-standalone/dist/cpython-3.12.11-aarch64-apple-darwin-pgo+lto-20250612T0816.tar.zst
    ++ head -1
    + DIST_FILE=/Users/user/dysonprotocol2/dysvm/python-build-standalone/dist/cpython-3.12.11-aarch64-apple-darwin-pgo+lto-20250612T0816.tar.zst
    + '[' -z /Users/user/dysonprotocol2/dysvm/python-build-standalone/dist/cpython-3.12.11-aarch64-apple-darwin-pgo+lto-20250612T0816.tar.zst ']'
    + TARGET_FILE=/tmp/python-download/cpython-3.12.11+custom-aarch64-apple-darwin-pgo+lto-full.tar.zst
    + EXTRACT_DIR=/tmp/python-download/cpython-3.12.11+custom-aarch64-apple-darwin-pgo+lto-full.tar.zst.extracted
    + echo 'Source file: /Users/user/dysonprotocol2/dysvm/python-build-standalone/dist/cpython-3.12.11-aarch64-apple-darwin-pgo+lto-20250612T0816.tar.zst'
    + echo 'Target file: /tmp/python-download/cpython-3.12.11+custom-aarch64-apple-darwin-pgo+lto-full.tar.zst'
    + cp /Users/user/dysonprotocol2/dysvm/python-build-standalone/dist/cpython-3.12.11-aarch64-apple-darwin-pgo+lto-20250612T0816.tar.zst /tmp/python-download/cpython-3.12.11+custom-aarch64-apple-darwin-pgo+lto-full.tar.zst


    Source file: /Users/user/dysonprotocol2/dysvm/python-build-standalone/dist/cpython-3.12.11-aarch64-apple-darwin-pgo+lto-20250612T0816.tar.zst
    Target file: /tmp/python-download/cpython-3.12.11+custom-aarch64-apple-darwin-pgo+lto-full.tar.zst


    + mkdir -p /tmp/python-download/cpython-3.12.11+custom-aarch64-apple-darwin-pgo+lto-full.tar.zst.extracted
    + zstd -d
    + tar -x -C /tmp/python-download/cpython-3.12.11+custom-aarch64-apple-darwin-pgo+lto-full.tar.zst.extracted
    + echo '🧹 Removing terminfo directory to avoid case-sensitivity conflicts...'
    + PYTHON_INSTALL_DIR=/tmp/python-download/cpython-3.12.11+custom-aarch64-apple-darwin-pgo+lto-full.tar.zst.extracted/python/install
    + '[' -d /tmp/python-download/cpython-3.12.11+custom-aarch64-apple-darwin-pgo+lto-full.tar.zst.extracted/python/install/share/terminfo ']'


    🧹 Removing terminfo directory to avoid case-sensitivity conflicts...
    ℹ️ No terminfo directory found


    + echo 'ℹ️ No terminfo directory found'
    + echo '📦 Repackaging cleaned Python distribution...'
    + cd /tmp/python-download/cpython-3.12.11+custom-aarch64-apple-darwin-pgo+lto-full.tar.zst.extracted


    📦 Repackaging cleaned Python distribution...


    + tar -cf - python
    + zstd
    + echo '✓ Repackaged successfully'
    + cd /Users/user/dysonprotocol2/dysvm/go-embed-python


    ✓ Repackaged successfully


    + go mod tidy
    + go run ./python/generate --python-standalone-version=custom --python-version=3.12.11 --prepare-path=/tmp/python-download --prepare=false
    time="2025-08-02T14:37:20+02:00" level=info msg="python-standalone-version=custom"
    time="2025-08-02T14:37:20+02:00" level=info msg="python-version=3.12.11"
    time="2025-08-02T14:37:20+02:00" level=info msg="copying to python/internal/data/windows-amd64 with 0 files"
    time="2025-08-02T14:37:20+02:00" level=info msg="copying to python/internal/data/linux-arm64 with 0 files"
    time="2025-08-02T14:37:20+02:00" level=info msg="copying to python/internal/data/linux-amd64 with 0 files"
    time="2025-08-02T14:37:20+02:00" level=info msg="copying to python/internal/data/darwin-amd64 with 0 files"
    time="2025-08-02T14:37:20+02:00" level=info msg="copying to python/internal/data/darwin-arm64 with 3769 files"
    + cd /Users/user/dysonprotocol2
    + go generate ./...


    Processing ./py-dyslang
      Installing build dependencies: started
      Installing build dependencies: finished with status 'done'
      Getting requirements to build wheel: started
      Getting requirements to build wheel: finished with status 'done'
      Preparing metadata (pyproject.toml): started
      Preparing metadata (pyproject.toml): finished with status 'done'
    Collecting black==25.1.0 (from -r requirements.txt (line 7))
      Using cached black-25.1.0-py3-none-any.whl.metadata (81 kB)
    Collecting certifi==2025.6.15 (from -r requirements.txt (line 9))
      Using cached certifi-2025.6.15-py3-none-any.whl.metadata (2.4 kB)
    Collecting charset-normalizer==3.4.2 (from -r requirements.txt (line 11))
      Using cached charset_normalizer-3.4.2-cp312-cp312-manylinux_2_17_aarch64.manylinux2014_aarch64.whl.metadata (35 kB)
    Collecting click==8.2.1 (from -r requirements.txt (line 13))
      Using cached click-8.2.1-py3-none-any.whl.metadata (2.5 kB)
    Collecting configargparse==1.7.1 (from -r requirements.txt (line 15))
      Using cached configargparse-1.7.1-py3-none-any.whl.metadata (24 kB)
    Collecting freezegun==1.5.2 (from -r requirements.txt (line 17))
      Using cached freezegun-1.5.2-py3-none-any.whl.metadata (13 kB)
    Collecting google-re2==1.1.20240702 (from -r requirements.txt (line 19))
      Using cached google_re2-1.1.20240702-1-cp312-cp312-manylinux_2_24_aarch64.manylinux_2_28_aarch64.whl.metadata (2.2 kB)
    Collecting idna==3.10 (from -r requirements.txt (line 21))
      Using cached idna-3.10-py3-none-any.whl.metadata (10 kB)
    Collecting iniconfig==2.1.0 (from -r requirements.txt (line 23))
      Using cached iniconfig-2.1.0-py3-none-any.whl.metadata (2.7 kB)
    Collecting mypy-extensions==1.1.0 (from -r requirements.txt (line 25))
      Using cached mypy_extensions-1.1.0-py3-none-any.whl.metadata (1.1 kB)
    Collecting orjson==3.10.18 (from -r requirements.txt (line 27))
      Using cached orjson-3.10.18-cp312-cp312-manylinux_2_17_aarch64.manylinux2014_aarch64.whl.metadata (41 kB)
    Collecting packaging==25.0 (from -r requirements.txt (line 29))
      Using cached packaging-25.0-py3-none-any.whl.metadata (3.3 kB)
    Collecting pathspec==0.12.1 (from -r requirements.txt (line 33))
      Using cached pathspec-0.12.1-py3-none-any.whl.metadata (21 kB)
    Collecting platformdirs==4.3.8 (from -r requirements.txt (line 35))
      Using cached platformdirs-4.3.8-py3-none-any.whl.metadata (12 kB)
    Collecting pluggy==1.6.0 (from -r requirements.txt (line 37))
      Using cached pluggy-1.6.0-py3-none-any.whl.metadata (4.8 kB)
    Collecting pygments==2.19.2 (from -r requirements.txt (line 41))
      Using cached pygments-2.19.2-py3-none-any.whl.metadata (2.5 kB)
    Collecting pytest==8.4.1 (from -r requirements.txt (line 43))
      Using cached pytest-8.4.1-py3-none-any.whl.metadata (7.7 kB)
    Collecting python-dateutil==2.9.0.post0 (from -r requirements.txt (line 45))
      Using cached python_dateutil-2.9.0.post0-py2.py3-none-any.whl.metadata (8.4 kB)
    Collecting python-forge==18.6.0 (from -r requirements.txt (line 47))
      Using cached python_forge-18.6.0-py35-none-any.whl.metadata (6.6 kB)
    Collecting requests==2.32.4 (from -r requirements.txt (line 49))
      Using cached requests-2.32.4-py3-none-any.whl.metadata (4.9 kB)
    Collecting six==1.17.0 (from -r requirements.txt (line 51))
      Using cached six-1.17.0-py2.py3-none-any.whl.metadata (1.7 kB)
    Collecting urllib3==2.5.0 (from -r requirements.txt (line 53))
      Using cached urllib3-2.5.0-py3-none-any.whl.metadata (6.5 kB)
    Using cached black-25.1.0-py3-none-any.whl (207 kB)
    Using cached certifi-2025.6.15-py3-none-any.whl (157 kB)
    Using cached charset_normalizer-3.4.2-cp312-cp312-manylinux_2_17_aarch64.manylinux2014_aarch64.whl (143 kB)
    Using cached click-8.2.1-py3-none-any.whl (102 kB)
    Using cached configargparse-1.7.1-py3-none-any.whl (25 kB)
    Using cached freezegun-1.5.2-py3-none-any.whl (18 kB)
    Using cached google_re2-1.1.20240702-1-cp312-cp312-manylinux_2_24_aarch64.manylinux_2_28_aarch64.whl (537 kB)
    Using cached idna-3.10-py3-none-any.whl (70 kB)
    Using cached iniconfig-2.1.0-py3-none-any.whl (6.0 kB)
    Using cached mypy_extensions-1.1.0-py3-none-any.whl (5.0 kB)
    Using cached orjson-3.10.18-cp312-cp312-manylinux_2_17_aarch64.manylinux2014_aarch64.whl (136 kB)
    Using cached packaging-25.0-py3-none-any.whl (66 kB)
    Using cached pathspec-0.12.1-py3-none-any.whl (31 kB)
    Using cached platformdirs-4.3.8-py3-none-any.whl (18 kB)
    Using cached pluggy-1.6.0-py3-none-any.whl (20 kB)
    Using cached pygments-2.19.2-py3-none-any.whl (1.2 MB)
    Using cached pytest-8.4.1-py3-none-any.whl (365 kB)
    Using cached python_dateutil-2.9.0.post0-py2.py3-none-any.whl (229 kB)
    Using cached python_forge-18.6.0-py35-none-any.whl (31 kB)
    Using cached requests-2.32.4-py3-none-any.whl (64 kB)
    Using cached six-1.17.0-py2.py3-none-any.whl (11 kB)
    Using cached urllib3-2.5.0-py3-none-any.whl (129 kB)
    Building wheels for collected packages: py-dyslang
      Building wheel for py-dyslang (pyproject.toml): started
      Building wheel for py-dyslang (pyproject.toml): finished with status 'done'
      Created wheel for py-dyslang: filename=py_dyslang-1.0.2-py3-none-any.whl size=28609 sha256=0d1a8b82e3ae9fa08ed8d07223ce274fa13fbb62f433f347dedfba928120387e
      Stored in directory: /Users/user/Library/Caches/pip/wheels/31/e8/ac/32ee20e45ff9c07acc124ae20566975855758ff81ab18946ed
    Successfully built py-dyslang
    Installing collected packages: python-forge, py-dyslang, urllib3, six, pygments, pluggy, platformdirs, pathspec, packaging, orjson, mypy-extensions, iniconfig, idna, google-re2, configargparse, click, charset-normalizer, certifi, requests, python-dateutil, pytest, black, freezegun
    Successfully installed black-25.1.0 certifi-2025.6.15 charset-normalizer-3.4.2 click-8.2.1 configargparse-1.7.1 freezegun-1.5.2 google-re2-1.1.20240702 idna-3.10 iniconfig-2.1.0 mypy-extensions-1.1.0 orjson-3.10.18 packaging-25.0 pathspec-0.12.1 platformdirs-4.3.8 pluggy-1.6.0 py-dyslang-1.0.2 pygments-2.19.2 pytest-8.4.1 python-dateutil-2.9.0.post0 python-forge-18.6.0 requests-2.32.4 six-1.17.0 urllib3-2.5.0


    
    [1m[[0m[34;49mnotice[0m[1;39;49m][0m[39;49m A new release of pip is available: [0m[31;49m24.3.1[0m[39;49m -> [0m[32;49m25.2[0m
    [1m[[0m[34;49mnotice[0m[1;39;49m][0m[39;49m To update, run: [0m[32;49m/tmp/python-pip-linux-arm64/bin/python3 -m pip install --upgrade pip[0m
    time="2025-08-02T14:37:30+02:00" level=info msg="copying to data/linux-arm64 with 911 files"


    Processing ./py-dyslang
      Installing build dependencies: started
      Installing build dependencies: finished with status 'done'
      Getting requirements to build wheel: started
      Getting requirements to build wheel: finished with status 'done'
      Preparing metadata (pyproject.toml): started
      Preparing metadata (pyproject.toml): finished with status 'done'
    Collecting black==25.1.0 (from -r requirements.txt (line 7))
      Using cached black-25.1.0-cp312-cp312-win_amd64.whl.metadata (81 kB)
    Collecting certifi==2025.6.15 (from -r requirements.txt (line 9))
      Using cached certifi-2025.6.15-py3-none-any.whl.metadata (2.4 kB)
    Collecting charset-normalizer==3.4.2 (from -r requirements.txt (line 11))
      Using cached charset_normalizer-3.4.2-cp312-cp312-win_amd64.whl.metadata (36 kB)
    Collecting click==8.2.1 (from -r requirements.txt (line 13))
      Using cached click-8.2.1-py3-none-any.whl.metadata (2.5 kB)
    Collecting configargparse==1.7.1 (from -r requirements.txt (line 15))
      Using cached configargparse-1.7.1-py3-none-any.whl.metadata (24 kB)
    Collecting freezegun==1.5.2 (from -r requirements.txt (line 17))
      Using cached freezegun-1.5.2-py3-none-any.whl.metadata (13 kB)
    Collecting google-re2==1.1.20240702 (from -r requirements.txt (line 19))
      Using cached google_re2-1.1.20240702-1-cp312-cp312-win_amd64.whl.metadata (2.2 kB)
    Collecting idna==3.10 (from -r requirements.txt (line 21))
      Using cached idna-3.10-py3-none-any.whl.metadata (10 kB)
    Collecting iniconfig==2.1.0 (from -r requirements.txt (line 23))
      Using cached iniconfig-2.1.0-py3-none-any.whl.metadata (2.7 kB)
    Collecting mypy-extensions==1.1.0 (from -r requirements.txt (line 25))
      Using cached mypy_extensions-1.1.0-py3-none-any.whl.metadata (1.1 kB)
    Collecting orjson==3.10.18 (from -r requirements.txt (line 27))
      Using cached orjson-3.10.18-cp312-cp312-win_amd64.whl.metadata (43 kB)
    Collecting packaging==25.0 (from -r requirements.txt (line 29))
      Using cached packaging-25.0-py3-none-any.whl.metadata (3.3 kB)
    Collecting pathspec==0.12.1 (from -r requirements.txt (line 33))
      Using cached pathspec-0.12.1-py3-none-any.whl.metadata (21 kB)
    Collecting platformdirs==4.3.8 (from -r requirements.txt (line 35))
      Using cached platformdirs-4.3.8-py3-none-any.whl.metadata (12 kB)
    Collecting pluggy==1.6.0 (from -r requirements.txt (line 37))
      Using cached pluggy-1.6.0-py3-none-any.whl.metadata (4.8 kB)
    Collecting pygments==2.19.2 (from -r requirements.txt (line 41))
      Using cached pygments-2.19.2-py3-none-any.whl.metadata (2.5 kB)
    Collecting pytest==8.4.1 (from -r requirements.txt (line 43))
      Using cached pytest-8.4.1-py3-none-any.whl.metadata (7.7 kB)
    Collecting python-dateutil==2.9.0.post0 (from -r requirements.txt (line 45))
      Using cached python_dateutil-2.9.0.post0-py2.py3-none-any.whl.metadata (8.4 kB)
    Collecting python-forge==18.6.0 (from -r requirements.txt (line 47))
      Using cached python_forge-18.6.0-py35-none-any.whl.metadata (6.6 kB)
    Collecting requests==2.32.4 (from -r requirements.txt (line 49))
      Using cached requests-2.32.4-py3-none-any.whl.metadata (4.9 kB)
    Collecting six==1.17.0 (from -r requirements.txt (line 51))
      Using cached six-1.17.0-py2.py3-none-any.whl.metadata (1.7 kB)
    Collecting urllib3==2.5.0 (from -r requirements.txt (line 53))
      Using cached urllib3-2.5.0-py3-none-any.whl.metadata (6.5 kB)
    Using cached black-25.1.0-cp312-cp312-win_amd64.whl (1.4 MB)
    Using cached certifi-2025.6.15-py3-none-any.whl (157 kB)
    Using cached charset_normalizer-3.4.2-cp312-cp312-win_amd64.whl (105 kB)
    Using cached click-8.2.1-py3-none-any.whl (102 kB)
    Using cached configargparse-1.7.1-py3-none-any.whl (25 kB)
    Using cached freezegun-1.5.2-py3-none-any.whl (18 kB)
    Using cached google_re2-1.1.20240702-1-cp312-cp312-win_amd64.whl (497 kB)
    Using cached idna-3.10-py3-none-any.whl (70 kB)
    Using cached iniconfig-2.1.0-py3-none-any.whl (6.0 kB)
    Using cached mypy_extensions-1.1.0-py3-none-any.whl (5.0 kB)
    Using cached orjson-3.10.18-cp312-cp312-win_amd64.whl (134 kB)
    Using cached packaging-25.0-py3-none-any.whl (66 kB)
    Using cached pathspec-0.12.1-py3-none-any.whl (31 kB)
    Using cached platformdirs-4.3.8-py3-none-any.whl (18 kB)
    Using cached pluggy-1.6.0-py3-none-any.whl (20 kB)
    Using cached pygments-2.19.2-py3-none-any.whl (1.2 MB)
    Using cached pytest-8.4.1-py3-none-any.whl (365 kB)
    Using cached python_dateutil-2.9.0.post0-py2.py3-none-any.whl (229 kB)
    Using cached python_forge-18.6.0-py35-none-any.whl (31 kB)
    Using cached requests-2.32.4-py3-none-any.whl (64 kB)
    Using cached six-1.17.0-py2.py3-none-any.whl (11 kB)
    Using cached urllib3-2.5.0-py3-none-any.whl (129 kB)
    Building wheels for collected packages: py-dyslang
      Building wheel for py-dyslang (pyproject.toml): started
      Building wheel for py-dyslang (pyproject.toml): finished with status 'done'
      Created wheel for py-dyslang: filename=py_dyslang-1.0.2-py3-none-any.whl size=28609 sha256=33b4062cc2e3181ffbf72258db1f1ad93730b240737dfa9a288d6d5a7fca3b5b
      Stored in directory: /Users/user/Library/Caches/pip/wheels/31/e8/ac/32ee20e45ff9c07acc124ae20566975855758ff81ab18946ed
    Successfully built py-dyslang
    Installing collected packages: python-forge, py-dyslang, urllib3, six, pygments, pluggy, platformdirs, pathspec, packaging, orjson, mypy-extensions, iniconfig, idna, google-re2, configargparse, click, charset-normalizer, certifi, requests, python-dateutil, pytest, black, freezegun
    Successfully installed black-25.1.0 certifi-2025.6.15 charset-normalizer-3.4.2 click-8.2.1 configargparse-1.7.1 freezegun-1.5.2 google-re2-1.1.20240702 idna-3.10 iniconfig-2.1.0 mypy-extensions-1.1.0 orjson-3.10.18 packaging-25.0 pathspec-0.12.1 platformdirs-4.3.8 pluggy-1.6.0 py-dyslang-1.0.2 pygments-2.19.2 pytest-8.4.1 python-dateutil-2.9.0.post0 python-forge-18.6.0 requests-2.32.4 six-1.17.0 urllib3-2.5.0


    
    [1m[[0m[34;49mnotice[0m[1;39;49m][0m[39;49m A new release of pip is available: [0m[31;49m24.3.1[0m[39;49m -> [0m[32;49m25.2[0m
    [1m[[0m[34;49mnotice[0m[1;39;49m][0m[39;49m To update, run: [0m[32;49m/tmp/python-pip-windows-amd64/bin/python3 -m pip install --upgrade pip[0m
    time="2025-08-02T14:37:36+02:00" level=info msg="copying to data/windows-amd64 with 944 files"


    Processing ./py-dyslang
      Installing build dependencies: started
      Installing build dependencies: finished with status 'done'
      Getting requirements to build wheel: started
      Getting requirements to build wheel: finished with status 'done'
      Preparing metadata (pyproject.toml): started
      Preparing metadata (pyproject.toml): finished with status 'done'
    Collecting black==25.1.0 (from -r requirements.txt (line 7))
      Using cached black-25.1.0-cp312-cp312-macosx_10_13_x86_64.whl.metadata (81 kB)
    Collecting certifi==2025.6.15 (from -r requirements.txt (line 9))
      Using cached certifi-2025.6.15-py3-none-any.whl.metadata (2.4 kB)
    Collecting charset-normalizer==3.4.2 (from -r requirements.txt (line 11))
      Using cached charset_normalizer-3.4.2-cp312-cp312-macosx_10_13_universal2.whl.metadata (35 kB)
    Collecting click==8.2.1 (from -r requirements.txt (line 13))
      Using cached click-8.2.1-py3-none-any.whl.metadata (2.5 kB)
    Collecting configargparse==1.7.1 (from -r requirements.txt (line 15))
      Using cached configargparse-1.7.1-py3-none-any.whl.metadata (24 kB)
    Collecting freezegun==1.5.2 (from -r requirements.txt (line 17))
      Using cached freezegun-1.5.2-py3-none-any.whl.metadata (13 kB)
    Collecting google-re2==1.1.20240702 (from -r requirements.txt (line 19))
      Using cached google_re2-1.1.20240702-1-cp312-cp312-macosx_12_0_x86_64.whl.metadata (2.2 kB)
    Collecting idna==3.10 (from -r requirements.txt (line 21))
      Using cached idna-3.10-py3-none-any.whl.metadata (10 kB)
    Collecting iniconfig==2.1.0 (from -r requirements.txt (line 23))
      Using cached iniconfig-2.1.0-py3-none-any.whl.metadata (2.7 kB)
    Collecting mypy-extensions==1.1.0 (from -r requirements.txt (line 25))
      Using cached mypy_extensions-1.1.0-py3-none-any.whl.metadata (1.1 kB)
    Collecting orjson==3.10.18 (from -r requirements.txt (line 27))
      Using cached orjson-3.10.18-cp312-cp312-macosx_10_15_x86_64.macosx_11_0_arm64.macosx_10_15_universal2.whl.metadata (41 kB)
    Collecting packaging==25.0 (from -r requirements.txt (line 29))
      Using cached packaging-25.0-py3-none-any.whl.metadata (3.3 kB)
    Collecting pathspec==0.12.1 (from -r requirements.txt (line 33))
      Using cached pathspec-0.12.1-py3-none-any.whl.metadata (21 kB)
    Collecting platformdirs==4.3.8 (from -r requirements.txt (line 35))
      Using cached platformdirs-4.3.8-py3-none-any.whl.metadata (12 kB)
    Collecting pluggy==1.6.0 (from -r requirements.txt (line 37))
      Using cached pluggy-1.6.0-py3-none-any.whl.metadata (4.8 kB)
    Collecting pygments==2.19.2 (from -r requirements.txt (line 41))
      Using cached pygments-2.19.2-py3-none-any.whl.metadata (2.5 kB)
    Collecting pytest==8.4.1 (from -r requirements.txt (line 43))
      Using cached pytest-8.4.1-py3-none-any.whl.metadata (7.7 kB)
    Collecting python-dateutil==2.9.0.post0 (from -r requirements.txt (line 45))
      Using cached python_dateutil-2.9.0.post0-py2.py3-none-any.whl.metadata (8.4 kB)
    Collecting python-forge==18.6.0 (from -r requirements.txt (line 47))
      Using cached python_forge-18.6.0-py35-none-any.whl.metadata (6.6 kB)
    Collecting requests==2.32.4 (from -r requirements.txt (line 49))
      Using cached requests-2.32.4-py3-none-any.whl.metadata (4.9 kB)
    Collecting six==1.17.0 (from -r requirements.txt (line 51))
      Using cached six-1.17.0-py2.py3-none-any.whl.metadata (1.7 kB)
    Collecting urllib3==2.5.0 (from -r requirements.txt (line 53))
      Using cached urllib3-2.5.0-py3-none-any.whl.metadata (6.5 kB)
    Using cached black-25.1.0-cp312-cp312-macosx_10_13_x86_64.whl (1.7 MB)
    Using cached certifi-2025.6.15-py3-none-any.whl (157 kB)
    Using cached charset_normalizer-3.4.2-cp312-cp312-macosx_10_13_universal2.whl (199 kB)
    Using cached click-8.2.1-py3-none-any.whl (102 kB)
    Using cached configargparse-1.7.1-py3-none-any.whl (25 kB)
    Using cached freezegun-1.5.2-py3-none-any.whl (18 kB)
    Using cached google_re2-1.1.20240702-1-cp312-cp312-macosx_12_0_x86_64.whl (491 kB)
    Using cached idna-3.10-py3-none-any.whl (70 kB)
    Using cached iniconfig-2.1.0-py3-none-any.whl (6.0 kB)
    Using cached mypy_extensions-1.1.0-py3-none-any.whl (5.0 kB)
    Using cached orjson-3.10.18-cp312-cp312-macosx_10_15_x86_64.macosx_11_0_arm64.macosx_10_15_universal2.whl (249 kB)
    Using cached packaging-25.0-py3-none-any.whl (66 kB)
    Using cached pathspec-0.12.1-py3-none-any.whl (31 kB)
    Using cached platformdirs-4.3.8-py3-none-any.whl (18 kB)
    Using cached pluggy-1.6.0-py3-none-any.whl (20 kB)
    Using cached pygments-2.19.2-py3-none-any.whl (1.2 MB)
    Using cached pytest-8.4.1-py3-none-any.whl (365 kB)
    Using cached python_dateutil-2.9.0.post0-py2.py3-none-any.whl (229 kB)
    Using cached python_forge-18.6.0-py35-none-any.whl (31 kB)
    Using cached requests-2.32.4-py3-none-any.whl (64 kB)
    Using cached six-1.17.0-py2.py3-none-any.whl (11 kB)
    Using cached urllib3-2.5.0-py3-none-any.whl (129 kB)
    Building wheels for collected packages: py-dyslang
      Building wheel for py-dyslang (pyproject.toml): started
      Building wheel for py-dyslang (pyproject.toml): finished with status 'done'
      Created wheel for py-dyslang: filename=py_dyslang-1.0.2-py3-none-any.whl size=28609 sha256=0069fcde9a5eb78a823d501933a39bcdb5a24925f92318c79c41028d833a7883
      Stored in directory: /Users/user/Library/Caches/pip/wheels/31/e8/ac/32ee20e45ff9c07acc124ae20566975855758ff81ab18946ed
    Successfully built py-dyslang
    Installing collected packages: python-forge, py-dyslang, urllib3, six, pygments, pluggy, platformdirs, pathspec, packaging, orjson, mypy-extensions, iniconfig, idna, google-re2, configargparse, click, charset-normalizer, certifi, requests, python-dateutil, pytest, black, freezegun
    Successfully installed black-25.1.0 certifi-2025.6.15 charset-normalizer-3.4.2 click-8.2.1 configargparse-1.7.1 freezegun-1.5.2 google-re2-1.1.20240702 idna-3.10 iniconfig-2.1.0 mypy-extensions-1.1.0 orjson-3.10.18 packaging-25.0 pathspec-0.12.1 platformdirs-4.3.8 pluggy-1.6.0 py-dyslang-1.0.2 pygments-2.19.2 pytest-8.4.1 python-dateutil-2.9.0.post0 python-forge-18.6.0 requests-2.32.4 six-1.17.0 urllib3-2.5.0


    
    [1m[[0m[34;49mnotice[0m[1;39;49m][0m[39;49m A new release of pip is available: [0m[31;49m24.3.1[0m[39;49m -> [0m[32;49m25.2[0m
    [1m[[0m[34;49mnotice[0m[1;39;49m][0m[39;49m To update, run: [0m[32;49m/tmp/python-pip-darwin-amd64/bin/python3 -m pip install --upgrade pip[0m
    time="2025-08-02T14:37:42+02:00" level=info msg="copying to data/darwin-amd64 with 941 files"


    Processing ./py-dyslang
      Installing build dependencies: started
      Installing build dependencies: finished with status 'done'
      Getting requirements to build wheel: started
      Getting requirements to build wheel: finished with status 'done'
      Preparing metadata (pyproject.toml): started
      Preparing metadata (pyproject.toml): finished with status 'done'
    Collecting black==25.1.0 (from -r requirements.txt (line 7))
      Using cached black-25.1.0-cp312-cp312-macosx_11_0_arm64.whl.metadata (81 kB)
    Collecting certifi==2025.6.15 (from -r requirements.txt (line 9))
      Using cached certifi-2025.6.15-py3-none-any.whl.metadata (2.4 kB)
    Collecting charset-normalizer==3.4.2 (from -r requirements.txt (line 11))
      Using cached charset_normalizer-3.4.2-cp312-cp312-macosx_10_13_universal2.whl.metadata (35 kB)
    Collecting click==8.2.1 (from -r requirements.txt (line 13))
      Using cached click-8.2.1-py3-none-any.whl.metadata (2.5 kB)
    Collecting configargparse==1.7.1 (from -r requirements.txt (line 15))
      Using cached configargparse-1.7.1-py3-none-any.whl.metadata (24 kB)
    Collecting freezegun==1.5.2 (from -r requirements.txt (line 17))
      Using cached freezegun-1.5.2-py3-none-any.whl.metadata (13 kB)
    Collecting google-re2==1.1.20240702 (from -r requirements.txt (line 19))
      Using cached google_re2-1.1.20240702-1-cp312-cp312-macosx_12_0_arm64.whl.metadata (2.2 kB)
    Collecting idna==3.10 (from -r requirements.txt (line 21))
      Using cached idna-3.10-py3-none-any.whl.metadata (10 kB)
    Collecting iniconfig==2.1.0 (from -r requirements.txt (line 23))
      Using cached iniconfig-2.1.0-py3-none-any.whl.metadata (2.7 kB)
    Collecting mypy-extensions==1.1.0 (from -r requirements.txt (line 25))
      Using cached mypy_extensions-1.1.0-py3-none-any.whl.metadata (1.1 kB)
    Collecting orjson==3.10.18 (from -r requirements.txt (line 27))
      Using cached orjson-3.10.18-cp312-cp312-macosx_10_15_x86_64.macosx_11_0_arm64.macosx_10_15_universal2.whl.metadata (41 kB)
    Collecting packaging==25.0 (from -r requirements.txt (line 29))
      Using cached packaging-25.0-py3-none-any.whl.metadata (3.3 kB)
    Collecting pathspec==0.12.1 (from -r requirements.txt (line 33))
      Using cached pathspec-0.12.1-py3-none-any.whl.metadata (21 kB)
    Collecting platformdirs==4.3.8 (from -r requirements.txt (line 35))
      Using cached platformdirs-4.3.8-py3-none-any.whl.metadata (12 kB)
    Collecting pluggy==1.6.0 (from -r requirements.txt (line 37))
      Using cached pluggy-1.6.0-py3-none-any.whl.metadata (4.8 kB)
    Collecting pygments==2.19.2 (from -r requirements.txt (line 41))
      Using cached pygments-2.19.2-py3-none-any.whl.metadata (2.5 kB)
    Collecting pytest==8.4.1 (from -r requirements.txt (line 43))
      Using cached pytest-8.4.1-py3-none-any.whl.metadata (7.7 kB)
    Collecting python-dateutil==2.9.0.post0 (from -r requirements.txt (line 45))
      Using cached python_dateutil-2.9.0.post0-py2.py3-none-any.whl.metadata (8.4 kB)
    Collecting python-forge==18.6.0 (from -r requirements.txt (line 47))
      Using cached python_forge-18.6.0-py35-none-any.whl.metadata (6.6 kB)
    Collecting requests==2.32.4 (from -r requirements.txt (line 49))
      Using cached requests-2.32.4-py3-none-any.whl.metadata (4.9 kB)
    Collecting six==1.17.0 (from -r requirements.txt (line 51))
      Using cached six-1.17.0-py2.py3-none-any.whl.metadata (1.7 kB)
    Collecting urllib3==2.5.0 (from -r requirements.txt (line 53))
      Using cached urllib3-2.5.0-py3-none-any.whl.metadata (6.5 kB)
    Using cached black-25.1.0-cp312-cp312-macosx_11_0_arm64.whl (1.5 MB)
    Using cached certifi-2025.6.15-py3-none-any.whl (157 kB)
    Using cached charset_normalizer-3.4.2-cp312-cp312-macosx_10_13_universal2.whl (199 kB)
    Using cached click-8.2.1-py3-none-any.whl (102 kB)
    Using cached configargparse-1.7.1-py3-none-any.whl (25 kB)
    Using cached freezegun-1.5.2-py3-none-any.whl (18 kB)
    Using cached google_re2-1.1.20240702-1-cp312-cp312-macosx_12_0_arm64.whl (465 kB)
    Using cached idna-3.10-py3-none-any.whl (70 kB)
    Using cached iniconfig-2.1.0-py3-none-any.whl (6.0 kB)
    Using cached mypy_extensions-1.1.0-py3-none-any.whl (5.0 kB)
    Using cached orjson-3.10.18-cp312-cp312-macosx_10_15_x86_64.macosx_11_0_arm64.macosx_10_15_universal2.whl (249 kB)
    Using cached packaging-25.0-py3-none-any.whl (66 kB)
    Using cached pathspec-0.12.1-py3-none-any.whl (31 kB)
    Using cached platformdirs-4.3.8-py3-none-any.whl (18 kB)
    Using cached pluggy-1.6.0-py3-none-any.whl (20 kB)
    Using cached pygments-2.19.2-py3-none-any.whl (1.2 MB)
    Using cached pytest-8.4.1-py3-none-any.whl (365 kB)
    Using cached python_dateutil-2.9.0.post0-py2.py3-none-any.whl (229 kB)
    Using cached python_forge-18.6.0-py35-none-any.whl (31 kB)
    Using cached requests-2.32.4-py3-none-any.whl (64 kB)
    Using cached six-1.17.0-py2.py3-none-any.whl (11 kB)
    Using cached urllib3-2.5.0-py3-none-any.whl (129 kB)
    Building wheels for collected packages: py-dyslang
      Building wheel for py-dyslang (pyproject.toml): started
      Building wheel for py-dyslang (pyproject.toml): finished with status 'done'
      Created wheel for py-dyslang: filename=py_dyslang-1.0.2-py3-none-any.whl size=28609 sha256=68a05a57251408b54e2ec404a201fa45a23aefe5d53b9c234d7d8e5228859efa
      Stored in directory: /Users/user/Library/Caches/pip/wheels/31/e8/ac/32ee20e45ff9c07acc124ae20566975855758ff81ab18946ed
    Successfully built py-dyslang
    Installing collected packages: python-forge, py-dyslang, urllib3, six, pygments, pluggy, platformdirs, pathspec, packaging, orjson, mypy-extensions, iniconfig, idna, google-re2, configargparse, click, charset-normalizer, certifi, requests, python-dateutil, pytest, black, freezegun
    Successfully installed black-25.1.0 certifi-2025.6.15 charset-normalizer-3.4.2 click-8.2.1 configargparse-1.7.1 freezegun-1.5.2 google-re2-1.1.20240702 idna-3.10 iniconfig-2.1.0 mypy-extensions-1.1.0 orjson-3.10.18 packaging-25.0 pathspec-0.12.1 platformdirs-4.3.8 pluggy-1.6.0 py-dyslang-1.0.2 pygments-2.19.2 pytest-8.4.1 python-dateutil-2.9.0.post0 python-forge-18.6.0 requests-2.32.4 six-1.17.0 urllib3-2.5.0


    
    [1m[[0m[34;49mnotice[0m[1;39;49m][0m[39;49m A new release of pip is available: [0m[31;49m24.3.1[0m[39;49m -> [0m[32;49m25.2[0m
    [1m[[0m[34;49mnotice[0m[1;39;49m][0m[39;49m To update, run: [0m[32;49m/tmp/python-pip-darwin-arm64/bin/python3 -m pip install --upgrade pip[0m
    time="2025-08-02T14:37:48+02:00" level=info msg="copying to data/darwin-arm64 with 941 files"


    Processing ./py-dyslang
      Installing build dependencies: started
      Installing build dependencies: finished with status 'done'
      Getting requirements to build wheel: started
      Getting requirements to build wheel: finished with status 'done'
      Preparing metadata (pyproject.toml): started
      Preparing metadata (pyproject.toml): finished with status 'done'
    Collecting black==25.1.0 (from -r requirements.txt (line 7))
      Using cached black-25.1.0-cp312-cp312-manylinux_2_17_x86_64.manylinux2014_x86_64.manylinux_2_28_x86_64.whl.metadata (81 kB)
    Collecting certifi==2025.6.15 (from -r requirements.txt (line 9))
      Using cached certifi-2025.6.15-py3-none-any.whl.metadata (2.4 kB)
    Collecting charset-normalizer==3.4.2 (from -r requirements.txt (line 11))
      Using cached charset_normalizer-3.4.2-cp312-cp312-manylinux_2_17_x86_64.manylinux2014_x86_64.whl.metadata (35 kB)
    Collecting click==8.2.1 (from -r requirements.txt (line 13))
      Using cached click-8.2.1-py3-none-any.whl.metadata (2.5 kB)
    Collecting configargparse==1.7.1 (from -r requirements.txt (line 15))
      Using cached configargparse-1.7.1-py3-none-any.whl.metadata (24 kB)
    Collecting freezegun==1.5.2 (from -r requirements.txt (line 17))
      Using cached freezegun-1.5.2-py3-none-any.whl.metadata (13 kB)
    Collecting google-re2==1.1.20240702 (from -r requirements.txt (line 19))
      Using cached google_re2-1.1.20240702-1-cp312-cp312-manylinux_2_24_x86_64.manylinux_2_28_x86_64.whl.metadata (2.2 kB)
    Collecting idna==3.10 (from -r requirements.txt (line 21))
      Using cached idna-3.10-py3-none-any.whl.metadata (10 kB)
    Collecting iniconfig==2.1.0 (from -r requirements.txt (line 23))
      Using cached iniconfig-2.1.0-py3-none-any.whl.metadata (2.7 kB)
    Collecting mypy-extensions==1.1.0 (from -r requirements.txt (line 25))
      Using cached mypy_extensions-1.1.0-py3-none-any.whl.metadata (1.1 kB)
    Collecting orjson==3.10.18 (from -r requirements.txt (line 27))
      Using cached orjson-3.10.18-cp312-cp312-manylinux_2_17_x86_64.manylinux2014_x86_64.whl.metadata (41 kB)
    Collecting packaging==25.0 (from -r requirements.txt (line 29))
      Using cached packaging-25.0-py3-none-any.whl.metadata (3.3 kB)
    Collecting pathspec==0.12.1 (from -r requirements.txt (line 33))
      Using cached pathspec-0.12.1-py3-none-any.whl.metadata (21 kB)
    Collecting platformdirs==4.3.8 (from -r requirements.txt (line 35))
      Using cached platformdirs-4.3.8-py3-none-any.whl.metadata (12 kB)
    Collecting pluggy==1.6.0 (from -r requirements.txt (line 37))
      Using cached pluggy-1.6.0-py3-none-any.whl.metadata (4.8 kB)
    Collecting pygments==2.19.2 (from -r requirements.txt (line 41))
      Using cached pygments-2.19.2-py3-none-any.whl.metadata (2.5 kB)
    Collecting pytest==8.4.1 (from -r requirements.txt (line 43))
      Using cached pytest-8.4.1-py3-none-any.whl.metadata (7.7 kB)
    Collecting python-dateutil==2.9.0.post0 (from -r requirements.txt (line 45))
      Using cached python_dateutil-2.9.0.post0-py2.py3-none-any.whl.metadata (8.4 kB)
    Collecting python-forge==18.6.0 (from -r requirements.txt (line 47))
      Using cached python_forge-18.6.0-py35-none-any.whl.metadata (6.6 kB)
    Collecting requests==2.32.4 (from -r requirements.txt (line 49))
      Using cached requests-2.32.4-py3-none-any.whl.metadata (4.9 kB)
    Collecting six==1.17.0 (from -r requirements.txt (line 51))
      Using cached six-1.17.0-py2.py3-none-any.whl.metadata (1.7 kB)
    Collecting urllib3==2.5.0 (from -r requirements.txt (line 53))
      Using cached urllib3-2.5.0-py3-none-any.whl.metadata (6.5 kB)
    Using cached black-25.1.0-cp312-cp312-manylinux_2_17_x86_64.manylinux2014_x86_64.manylinux_2_28_x86_64.whl (1.8 MB)
    Using cached certifi-2025.6.15-py3-none-any.whl (157 kB)
    Using cached charset_normalizer-3.4.2-cp312-cp312-manylinux_2_17_x86_64.manylinux2014_x86_64.whl (148 kB)
    Using cached click-8.2.1-py3-none-any.whl (102 kB)
    Using cached configargparse-1.7.1-py3-none-any.whl (25 kB)
    Using cached freezegun-1.5.2-py3-none-any.whl (18 kB)
    Using cached google_re2-1.1.20240702-1-cp312-cp312-manylinux_2_24_x86_64.manylinux_2_28_x86_64.whl (546 kB)
    Using cached idna-3.10-py3-none-any.whl (70 kB)
    Using cached iniconfig-2.1.0-py3-none-any.whl (6.0 kB)
    Using cached mypy_extensions-1.1.0-py3-none-any.whl (5.0 kB)
    Using cached orjson-3.10.18-cp312-cp312-manylinux_2_17_x86_64.manylinux2014_x86_64.whl (133 kB)
    Using cached packaging-25.0-py3-none-any.whl (66 kB)
    Using cached pathspec-0.12.1-py3-none-any.whl (31 kB)
    Using cached platformdirs-4.3.8-py3-none-any.whl (18 kB)
    Using cached pluggy-1.6.0-py3-none-any.whl (20 kB)
    Using cached pygments-2.19.2-py3-none-any.whl (1.2 MB)
    Using cached pytest-8.4.1-py3-none-any.whl (365 kB)
    Using cached python_dateutil-2.9.0.post0-py2.py3-none-any.whl (229 kB)
    Using cached python_forge-18.6.0-py35-none-any.whl (31 kB)
    Using cached requests-2.32.4-py3-none-any.whl (64 kB)
    Using cached six-1.17.0-py2.py3-none-any.whl (11 kB)
    Using cached urllib3-2.5.0-py3-none-any.whl (129 kB)
    Building wheels for collected packages: py-dyslang
      Building wheel for py-dyslang (pyproject.toml): started
      Building wheel for py-dyslang (pyproject.toml): finished with status 'done'
      Created wheel for py-dyslang: filename=py_dyslang-1.0.2-py3-none-any.whl size=28609 sha256=1d15c771038095375cdbd41b5a703f6258aa07f6e2742274af1ca15606aa4b56
      Stored in directory: /Users/user/Library/Caches/pip/wheels/31/e8/ac/32ee20e45ff9c07acc124ae20566975855758ff81ab18946ed
    Successfully built py-dyslang
    Installing collected packages: python-forge, py-dyslang, urllib3, six, pygments, pluggy, platformdirs, pathspec, packaging, orjson, mypy-extensions, iniconfig, idna, google-re2, configargparse, click, charset-normalizer, certifi, requests, python-dateutil, pytest, black, freezegun
    Successfully installed black-25.1.0 certifi-2025.6.15 charset-normalizer-3.4.2 click-8.2.1 configargparse-1.7.1 freezegun-1.5.2 google-re2-1.1.20240702 idna-3.10 iniconfig-2.1.0 mypy-extensions-1.1.0 orjson-3.10.18 packaging-25.0 pathspec-0.12.1 platformdirs-4.3.8 pluggy-1.6.0 py-dyslang-1.0.2 pygments-2.19.2 pytest-8.4.1 python-dateutil-2.9.0.post0 python-forge-18.6.0 requests-2.32.4 six-1.17.0 urllib3-2.5.0


    
    [1m[[0m[34;49mnotice[0m[1;39;49m][0m[39;49m A new release of pip is available: [0m[31;49m24.3.1[0m[39;49m -> [0m[32;49m25.2[0m
    [1m[[0m[34;49mnotice[0m[1;39;49m][0m[39;49m To update, run: [0m[32;49m/tmp/python-pip-linux-amd64/bin/python3 -m pip install --upgrade pip[0m
    time="2025-08-02T14:37:54+02:00" level=info msg="copying to data/linux-amd64 with 941 files"
    + echo 'DYSVM operations completed successfully'


    DYSVM operations completed successfully


### 1. Build the Dyson Protocol binary



```bash
%%bash
make install
```

    Installing dysond binary...
    build_tags: netgo,app_v1
    commit: 132ac87
    cosmos_sdk_version: v0.53.0
    go: go version go1.24.3 darwin/arm64
    name: dyson
    server_name: dysond
    version: develop
    



```bash
%%bash
dysond version --long | tail

```

    - rsc.io/qr@v0.2.0
    - sigs.k8s.io/yaml@v1.6.0
    build_tags: netgo,app_v1
    commit: 132ac87
    cosmos_sdk_version: v0.53.0
    go: go version go1.24.3 darwin/arm64
    name: dyson
    server_name: dysond
    version: develop
    


### 2. Create new accounts


```bash
%%bash
dysond keys add alice 
```

    


    - address: dys21ldyd2ngz4ttkmvud40pshksz9g0yx9lzjy9py5
      name: alice
      pubkey: '{"@type":"/cosmos.crypto.secp256k1.PubKey","key":"AjenBZPnfrfFQtvFT1KiGI5YFfKAENEfPLOZafBlPwuN"}'
      type: local
    


    
    **Important** write this mnemonic phrase in a safe place.
    It is the only way to recover your account if you ever forget your password.
    
    useful garbage divorce found surface like jump oven bitter maze ranch switch stomach rough head soap front infant camera twin renew casino olive spot


### 2. Update the On-chain Python Script

This example uploads a Python script that demonstrates storage operations. The full script is available at [examples/storage_example.py](examples/storage_example.py).

**Key Functions in the Script** (excerpt):

```python
def save_message(message):
    # the account that signed the transaction
    caller = get_executor_address()
    _msg({"@type":"/dysonprotocol.storage.v1.MsgStorageSet","owner": get_script_address() ,"index":f"greetings/{caller}","data": json.dumps({"greeting": message})})

def wsgi(environ, start_response):
    # Define response status and headers
    status_code = "200 OK"
    headers = [("Content-Type", "text/html")]
    start_response(status_code, headers)

    # Prepare the query parameters
    query_params = {
        "@type":"/dysonprotocol.storage.v1.QueryStorageListRequest",
        "owner": get_script_address(),
        "index_prefix":"greetings/"
    }
    
# ... more code in the full example ...
```

Let's see the full script:


```bash
%%bash
cat examples/storage_example.py
```

    import json
    from html import escape
    from dys import get_script_address, get_executor_address, _msg, _query
    
    
    def save_message(message):
        # the account that signed the transaction
        caller = get_executor_address()
        return _msg(
            {
                "@type": "/dysonprotocol.storage.v1.MsgStorageSet",
                "owner": get_script_address(),
                "index": f"greetings/{caller}",
                "data": json.dumps({"greeting": message}),
            }
        )
    
    
    def wsgi(environ, start_response):
        # Define response status and headers
        status_code = "200 OK"
        headers = [("Content-Type", "text/html")]
        start_response(status_code, headers)
    
        # Prepare the query parameters
        query_params = {
            "@type": "/dysonprotocol.storage.v1.QueryStorageListRequest",
            "owner": get_script_address(),
            "index_prefix": "greetings/",
        }
    
        # Get messages from storage
        storage_result = _query(query_params)
    
        # Start building HTML output
        output = "<html><body>\n"
        output += "<h2>Storage Messages</h2>\n"
    
        # Process each entry from storage
        for entry in storage_result["entries"]:
            # Parse the JSON data
            data = json.loads(entry["data"])
            # Extract the address from the index (format: greetings/{address})
            sender_address = entry["index"].split("/")[1]
            output += f"<p>Message from {escape(sender_address)}: {escape(data['greeting'])}</p>\n"
        else:
            output += "<p>No messages found</p>\n"
    
        # Add the full storage query result for debugging
        output += "<h3>Storage Query Result</h3>\n"
        output += "<pre>" + escape(json.dumps(storage_result, indent=2)) + "</pre>\n"
        output += "<h3>Environment</h3>\n"
        output += (
            "<pre>"
            + escape(json.dumps(environ, indent=2, sort_keys=True, default=str))
            + "</pre>\n"
        )
        output += "</body></html>"
    
        return [output.encode()]


Now let's upload the script to the chain using Alice's address:


```bash
%%bash
ALICE_ADDRESS=$(dysond keys show -a alice)
dysond tx script update --from alice -y -o json --gas 500000 --code "$(cat examples/storage_example.py)" |  dysond q wait-tx -o json | jq '{height, txhash, code, gas_wanted, gas_used, "script_version": .events[] | select(.type=="dysonprotocol.script.v1.EventUpdateScript") | .attributes[] | select(.key=="version") | .value}'

```

    Usage:
      dysond tx script update [--code <code> | --code-path <path to source code>] [flags]
    
    Flags:
      -a, --account-number uint         The account number of the signing account (offline mode only)
          --aux                         Generate aux signer data instead of sending a tx
      -b, --broadcast-mode string       Transaction broadcasting mode (sync|async) (default "sync")
          --chain-id string             The network chain ID
          --code string                 Source code as a string
          --code-path string            Path to the source code file
          --dry-run                     ignore the --gas flag and perform a simulation of a transaction, but don't broadcast it (when enabled, the local Keybase is not accessible)
          --fee-granter string          Fee granter grants fees for the transaction
          --fee-payer string            Fee payer pays fees for the transaction instead of deducting from the signer
          --fees string                 Fees to pay along with transaction; eg: 10uatom
          --from string                 Name or address of private key with which to sign
          --gas string                  gas limit to set per-transaction; set to "auto" to calculate sufficient gas automatically. Note: "auto" option doesn't always report accurate results. Set a valid coin value to adjust the result. Can be used instead of "fees". (default 200000)
          --gas-adjustment float        adjustment factor to be multiplied against the estimate returned by the tx simulation; if the gas limit is set manually this flag is ignored  (default 1)
          --gas-prices string           Gas prices in decimal format to determine the transaction fee (e.g. 0.1uatom)
          --generate-only               Build an unsigned transaction and write it to STDOUT (when enabled, the local Keybase only accessed when providing a key name)
      -h, --help                        help for update
          --keyring-backend string      Select keyring's backend (os|file|kwallet|pass|test|memory) (default "os")
          --keyring-dir string          The client Keyring directory; if omitted, the default 'home' directory will be used
          --ledger                      Use a connected Ledger device
          --node string                 <host>:<port> to CometBFT rpc interface for this chain (default "tcp://localhost:26657")
          --note string                 Note to add a description to the transaction (previously --memo)
          --offline                     Offline mode (does not allow any online functionality)
      -o, --output string               Output format (text|json) (default "json")
      -s, --sequence uint               The sequence number of the signing account (offline mode only)
          --sign-mode string            Choose sign mode (direct|amino-json|direct-aux|textual), this is an advanced feature
          --timeout-duration duration   TimeoutDuration is the duration the transaction will be considered valid in the mempool. The transaction's unordered nonce will be set to the time of transaction creation + the duration value passed. If the transaction is still in the mempool, and the block time has passed the time of submission + TimeoutTimestamp, the transaction will be rejected.
          --timeout-height uint         DEPRECATED: Please use --timeout-duration instead. Set a block timeout height to prevent the tx from being committed past a certain height
          --tip string                  Tip is the amount that is going to be transferred to the fee payer on the target chain. This flag is only valid when used with --aux, and is ignored if the target chain didn't enable the TipDecorator
          --unordered                   Enable unordered transaction delivery; must be used in conjunction with --timeout-duration
      -y, --yes                         Skip tx broadcasting prompt confirmation
    
    Global Flags:
          --home string         directory for config and data (default "/Users/user/.dysonprotocol")
          --log_format string   The logging format (json|plain) (default "plain")
          --log_level string    The logging level (trace|debug|info|warn|error|fatal|panic|disabled or '*:<level>,<key>:<level>') (default "info")
          --log_no_color        Disable colored logs
          --trace               print out full stack trace on errors
    
    rpc error: code = NotFound desc = rpc error: code = NotFound desc = account dys21ldyd2ngz4ttkmvud40pshksz9g0yx9lzjy9py5 not found: key not found
    Usage:
      dysond query wait-tx [hash] [flags]
    
    Aliases:
      wait-tx, event-query-tx-for
    
    Examples:
    By providing the transaction hash:
    $ dysond q wait-tx [hash]
    
    Or, by piping a "tx" command:
    $ dysond tx [flags] | dysond q wait-tx
    
    
    Flags:
          --grpc-addr string   the gRPC endpoint to use for this chain
          --grpc-insecure      allow gRPC over insecure channels, if not the server must use TLS
          --height int         Use a specific height to query state at (this can error if the node is pruning state)
      -h, --help               help for wait-tx
          --node string        <host>:<port> to CometBFT RPC interface for this chain (default "tcp://localhost:26657")
      -o, --output string      Output format (text|json) (default "text")
          --timeout duration   The maximum time to wait for the transaction to be included in a block (default 15s)
    
    Global Flags:
          --home string         directory for config and data (default "/Users/user/.dysonprotocol")
          --log_format string   The logging format (json|plain) (default "plain")
          --log_level string    The logging level (trace|debug|info|warn|error|fatal|panic|disabled or '*:<level>,<key>:<level>') (default "info")
          --log_no_color        Disable colored logs
          --trace               print out full stack trace on errors
    
    txhash not found


### 3. Execute the Script Function

Invoke the `save_message` function using Bob's account, passing `"my name is bob"` as an argument:


```bash
%%bash
ALICE_ADDRESS=$(dysond keys show -a alice)
# Save the message to the storage
dysond tx script exec-script --from bob --script-address $ALICE_ADDRESS --function-name save_message --args '["my name is <b>bob</b>"]' -y  | dysond query wait-tx -o json | ./scripts/parse_exec_script_tx.py | jq 
```

    Usage:
      dysond query wait-tx [hash] [flags]
    
    Aliases:
      wait-tx, event-query-tx-for
    
    Examples:
    By providing the transaction hash:
    $ dysond q wait-tx [hash]
    
    Or, by piping a "tx" command:
    $ dysond tx [flags] | dysond q wait-tx
    
    
    Flags:
          --grpc-addr string   the gRPC endpoint to use for this chain
          --grpc-insecure      allow gRPC over insecure channels, if not the server must use TLS
          --height int         Use a specific height to query state at (this can error if the node is pruning state)
      -h, --help               help for wait-tx
          --node string        <host>:<port> to CometBFT RPC interface for this chain (default "tcp://localhost:26657")
      -o, --output string      Output format (text|json) (default "text")
          --timeout duration   The maximum time to wait for the transaction to be included in a block (default 15s)
    
    Global Flags:
          --home string         directory for config and data (default "/Users/user/.dysonprotocol")
          --log_format string   The logging format (json|plain) (default "plain")
          --log_level string    The logging level (trace|debug|info|warn|error|fatal|panic|disabled or '*:<level>,<key>:<level>') (default "info")
          --log_no_color        Disable colored logs
          --trace               print out full stack trace on errors
    
    dial tcp [::1]:26657: connect: connection refused
    Usage:
      dysond tx script [flags]
      dysond tx script [command]
    
    Available Commands:
      create-new-script Creates a new script with a deterministic address derived from creator and code
      exec              Executes a script at a given address with optional input data and parameters
      grant-exec        Grant a custom ScriptExecAuthorization to a grantee (via authz)
      update            Updates the script at the sender's address with new code and increments the version
    
    Flags:
      -h, --help   help for script
    
    Global Flags:
          --home string         directory for config and data (default "/Users/user/.dysonprotocol")
          --log_format string   The logging format (json|plain) (default "plain")
          --log_level string    The logging level (trace|debug|info|warn|error|fatal|panic|disabled or '*:<level>,<key>:<level>') (default "info")
          --log_no_color        Disable colored logs
          --trace               print out full stack trace on errors
    
    Use "dysond tx script [command] --help" for more information about a command.
    
    unknown command "exec-script" for "script"
    jq: parse error: Invalid numeric literal at line 1, column 6



    ---------------------------------------------------------------------------

    CalledProcessError                        Traceback (most recent call last)

    Cell In[13], line 1
    ----> 1 get_ipython().run_cell_magic('bash', '', 'ALICE_ADDRESS=$(dysond keys show -a alice)\n# Save the message to the storage\ndysond tx script exec-script --from bob --script-address $ALICE_ADDRESS --function-name save_message --args \'["my name is <b>bob</b>"]\' -y  | dysond query wait-tx -o json | ./scripts/parse_exec_script_tx.py | jq \n')


    File ~/.pyenv/versions/3.12.11/lib/python3.12/site-packages/IPython/core/interactiveshell.py:2549, in InteractiveShell.run_cell_magic(self, magic_name, line, cell)
       2547 with self.builtin_trap:
       2548     args = (magic_arg_s, cell)
    -> 2549     result = fn(*args, **kwargs)
       2551 # The code below prevents the output from being displayed
       2552 # when using magics with decorator @output_can_be_silenced
       2553 # when the last Python token in the expression is a ';'.
       2554 if getattr(fn, magic.MAGIC_OUTPUT_CAN_BE_SILENCED, False):


    File ~/.pyenv/versions/3.12.11/lib/python3.12/site-packages/IPython/core/magics/script.py:159, in ScriptMagics._make_script_magic.<locals>.named_script_magic(line, cell)
        157 else:
        158     line = script
    --> 159 return self.shebang(line, cell)


    File ~/.pyenv/versions/3.12.11/lib/python3.12/site-packages/IPython/core/magics/script.py:336, in ScriptMagics.shebang(self, line, cell)
        331 if args.raise_error and p.returncode != 0:
        332     # If we get here and p.returncode is still None, we must have
        333     # killed it but not yet seen its return code. We don't wait for it,
        334     # in case it's stuck in uninterruptible sleep. -9 = SIGKILL
        335     rc = p.returncode or -9
    --> 336     raise CalledProcessError(rc, cell)


    CalledProcessError: Command 'b'ALICE_ADDRESS=$(dysond keys show -a alice)\n# Save the message to the storage\ndysond tx script exec-script --from bob --script-address $ALICE_ADDRESS --function-name save_message --args \'["my name is <b>bob</b>"]\' -y  | dysond query wait-tx -o json | ./scripts/parse_exec_script_tx.py | jq \n'' returned non-zero exit status 5.


### 4. Query the WSGI Endpoint

Finally, confirm the data is stored and accessible via an HTTP request to the script's WSGI endpoint:


```bash
%%bash
ALICE_ADDRESS=$(dysond keys show -a alice)
DWAPP_SERVER_ADDRESS=$(dysond config get app dwapp.address | tr -d '"')
DWAPP_URL="http://$ALICE_ADDRESS.$DWAPP_SERVER_ADDRESS/some-path?query=some-query"
curl -v $DWAPP_URL
```

## Notes & Edge Cases
- Always escape user generated content when rendering it in the browser.
- Ensure that you have a valid account (e.g., `alice`, `bob`) with sufficient balance to pay for gas fees.
- Always verify that you're interacting with the right script address.
- Make sure to provide sufficient gas for script updates (as seen in the example, we used `--gas 500000`).

## Conclusion

This example demonstrates how to:
1. Update on-chain Python code.
2. Execute a function that stores data on the Dyson Protocol.
3. Retrieve data via a WSGI endpoint.

Feel free to adapt the `save_message` function or the WSGI application for more advanced use cases, such as multi-key storage or complex business logic.

## More Documentation

For more detailed information about specific modules, please refer to the following documentation:

### Module Guides

- [Script Module](notebooks/scripting_guide.md): Comprehensive guide to the Script module for on-chain Python execution
- [Storage Module](notebooks/storage_guide.md): Detailed documentation on the Storage module for on-chain data persistence
- [Crontask Module](notebooks/crontask_guide.md): Complete guide to the Crontask module for scheduled transaction execution
- [Nameservice Module](notebooks/nameservice_guide.md): Guide to the Nameservice module for registering names and creating NFTs
- [DysLang Guide](notebooks/dyslang_guide.md): Complete programming reference for the Dyson Language

### Interactive Notebooks

The same guides are also available as interactive Jupyter notebooks in the `notebooks/` directory:

- [Script Module Notebook](notebooks/scripting_guide.ipynb)
- [Storage Module Notebook](notebooks/storage_guide.ipynb)
- [Crontask Module Notebook](notebooks/crontask_guide.ipynb)
- [Nameservice Module Notebook](notebooks/nameservice_guide.ipynb)
- [DysLang Guide Notebook](notebooks/dyslang_guide.ipynb)

### Code Examples

Explore practical examples in the `examples/` directory:

- [Storage Example](examples/storage_example.py): Basic storage operations and WSGI endpoint
- [Crontask Example](examples/crontask_countdown.py): Scheduled task countdown implementation
- [Crontask Script](examples/crontask_script.py): Advanced scheduled transaction execution
- [DysLang Example](examples/dyslang_example.py): Comprehensive language feature demonstration
- [Balance Example](examples/balance_example.py): Account balance querying
- [WSGI Example](examples/simple_wsgi_example.py): Simple web application server
- [AST Explorer](examples/ast_explorer.py): Python Abstract Syntax Tree exploration
- [ICA Example](examples/ica_e2e.py): Inter-Chain Account end-to-end example
- [ICA Module](examples/ica.py): Inter-Chain Account implementation
- [Script Query Height](examples/script_query_height.py): Query blockchain height from scripts

