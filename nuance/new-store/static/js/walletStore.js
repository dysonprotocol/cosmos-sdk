// walletStore.js (remade with tx management, mempool watch, modal persistence, retry, toast demo)
import { DirectSecp256k1HdWallet, makeSignDoc, makeSignBytes, executeKdf, extractKdfConfiguration } from "@cosmjs/proto-signing";
import { getChainInfo, sendMsgs, runScript, signData, encodeAndDecodeTx } from "./dysonTxUtils.js";
import { Tx, TxBody, AuthInfo, TxRaw } from "cosmjs-types/cosmos/tx/v1beta1/tx.js";
import { toBase64, fromBase64 } from "@cosmjs/encoding";

const DEFAULT_CHAIN_INFO = {
    restUrl: 'http://localhost:1317', //window.location.origin,
    bech32Prefix: "dys2",
};

const COSMJS_WALLET_TYPE = "cosmjs";

// Simple ID counter
// getNextId is now a method of walletStore to access txHistory.length

document.addEventListener("alpine:init", () => {
    Alpine.store("walletStore", {
        // Persisted & ephemeral state
        restUrl: DEFAULT_CHAIN_INFO.restUrl,
        chainId: "",
        localCosmJsWallets: Alpine.$persist([]),
        gasPrice: Alpine.$persist(0.00000),
        activeWalletMeta: Alpine.$persist(null),
        activeWalletInstance: null,
        isLoading: true,
        denomMetadatas: [],
        selectedAuthorIdentity: Alpine.$persist(null),
        addressNames: {},
        txHistory: Alpine.$persist([]), // [{txId, txHash, status, progress:0-100, timestamp, msgs, memo, fee, result, error}]
        lastTxChoices: Alpine.$persist({ gasPrice: 0.00000, memo: '', authorIdentity: null }), // Persist choices
        toasts: [], // For demo: [{id, message, type: 'info/success/error', timeoutId}]

        async init() {
            console.log('WalletStore: Initializing...');
            console.log('WalletStore: REST URL:', this.restUrl);

            try {
                await this.loadChainIdFromApi();
                console.log('WalletStore: Chain ID loaded:', this.chainId);

                if (this.activeWalletMeta) {
                    console.log('WalletStore: Found existing wallet meta:', this.activeWalletMeta.type, this.activeWalletMeta.name);

                    if (this.activeWalletMeta.type === "keplr") {
                        const provider = window.keplr;
                        if (!provider) {
                            console.error("WalletStore: Keplr not found, disconnecting wallet");
                            this.disconnectWallet();
                        } else {
                            console.log('WalletStore: Reconnecting to Keplr wallet');
                            const offlineSigner = provider.getOfflineSigner(this.chainId);
                            this.activeWalletInstance = offlineSigner;
                            await this.restoreAuthorIdentity();
                            console.log('WalletStore: Keplr wallet reconnected successfully');
                        }
                    } else if (this.activeWalletMeta.type === COSMJS_WALLET_TYPE) {
                        const walletData = this.localCosmJsWallets.find((w) => w.name === this.activeWalletMeta.name);
                        if (walletData && walletData._pass && walletData._pass.trim() !== "") {
                            try {
                                console.log('WalletStore: Reconnecting to CosmJS wallet:', this.activeWalletMeta.name);
                                await this.connectNamedCosmJsWallet(walletData.name, walletData._pass);
                                await this.restoreAuthorIdentity();
                                console.log('WalletStore: CosmJS wallet reconnected successfully');
                            } catch (error) {
                                console.error("WalletStore: Reconnect failed", error);
                            }
                        } else {
                            console.warn('WalletStore: CosmJS wallet data incomplete, cannot reconnect');
                        }
                    }
                } else {
                    console.log('WalletStore: No existing wallet found');
                }

                // TODO: remove default wallet creation
                if (this.localCosmJsWallets.length === 0) {
                    console.log('WalletStore: Creating default Alice wallet...');
                    const seed = "public feature teach face federal matrix throw legend bridge brass diary beach typical doll evoke weapon among crane regret trust enact swarm brother outside";
                    await this.importNamedCosmJsWallet("alice", seed, "password");
                    await this.connectNamedCosmJsWallet("alice", "password");
                    console.log('WalletStore: Default Alice wallet created and connected');
                }

                this.isLoading = false;
                console.log('WalletStore: Initialization complete');

                // Start automatic pending transaction refresh
                this.startPendingTxRefreshTimer();
            } catch (error) {
                console.error('WalletStore: Initialization failed:', error);
                this.isLoading = false;
                throw error;
            }
        },

        startPendingTxRefreshTimer() {
            console.log('WalletStore: Starting automatic pending transaction refresh timer');

            // Refresh every 10 seconds
            setInterval(() => {
                const pendingCount = this.getPendingTxHistory().length;
                if (pendingCount > 0) {
                    console.log('WalletStore: Auto-refreshing pending transactions, count:', pendingCount);
                    this.refreshPendingTxs();
                }
            }, 10000);

            // Auto-refresh timer handles checking status only - progress stays null for animated bars
        },

        getSignerAddress() {
            if (!this.activeWalletMeta?.address) {
                console.error('WalletStore: getSignerAddress() called with no wallet');
                throw new Error("No wallet");
            }
            console.log('WalletStore: getSignerAddress():', this.activeWalletMeta.address);
            return this.activeWalletMeta.address;
        },

        getNextId() {
            return this.txHistory.length + 1;
        },

        isWalletConnected() {
            const connected = !!this.activeWalletMeta?.address;
            console.log('WalletStore: isWalletConnected():', connected);
            return connected;
        },

        getAuthorIdentity() {
            if (!this.isWalletConnected()) {
                console.error('WalletStore: getAuthorIdentity() called with no wallet');
                throw new Error("No wallet");
            }
            const identity = this.selectedAuthorIdentity || this.getSignerAddress();
            console.log('WalletStore: getAuthorIdentity():', identity);
            return identity;
        },

        async setAuthorIdentity(identity) {
            console.log('WalletStore: setAuthorIdentity():', identity);
            if (!this.isWalletConnected()) {
                console.error('WalletStore: setAuthorIdentity() called with no wallet');
                throw new Error("No wallet");
            }
            if (identity !== this.getSignerAddress()) {
                console.log('WalletStore: Validating identity:', identity);
                const isValid = await this.validateNameForCurrentWallet(identity);
                if (!isValid) {
                    console.error('WalletStore: Invalid identity:', identity);
                    throw new Error(`Invalid identity "${identity}"`);
                }
                console.log('WalletStore: Identity validation passed');
            }
            this.selectedAuthorIdentity = identity;
            this.lastTxChoices.authorIdentity = identity; // Persist
            console.log('WalletStore: Author identity set to:', identity);
        },

        async getAvailableAuthorIdentities() {
            if (!this.isWalletConnected()) {
                console.log('WalletStore: getAvailableAuthorIdentities() - no wallet connected');
                return [];
            }

            console.log('WalletStore: Fetching available author identities...');
            const address = this.getSignerAddress();
            const names = await this.fetchNamesByDestination(address);
            const identities = [address];
            names.forEach(name => {
                if (name !== address && !identities.includes(name)) identities.push(name);
            });
            console.log('WalletStore: Available identities:', identities);
            return identities;
        },

        getDisplayTextForIdentity(identity) {
            const address = this.getSignerAddress();
            if (identity === address) {
                if (identity.length <= 13) return identity;
                return identity.slice(0, 8) + '...' + identity.slice(-5);
            }
            return identity;
        },

        async restoreAuthorIdentity() {
            console.log('WalletStore: Restoring author identity...');
            if (this.selectedAuthorIdentity) {
                console.log('WalletStore: Found stored identity:', this.selectedAuthorIdentity);
                try {
                    if (this.selectedAuthorIdentity !== this.getSignerAddress()) {
                        console.log('WalletStore: Validating stored identity...');
                        const isValid = await this.validateNameForCurrentWallet(this.selectedAuthorIdentity);
                        if (!isValid) {
                            console.warn("WalletStore: Invalid stored identity, reset to address");
                            this.selectedAuthorIdentity = this.getSignerAddress();
                            return;
                        }
                        console.log('WalletStore: Stored identity validated successfully');
                    }
                } catch (error) {
                    console.warn("WalletStore: Validation error, reset to address:", error);
                    this.selectedAuthorIdentity = this.getSignerAddress();
                }
            } else {
                console.log('WalletStore: No stored identity, using signer address');
                this.selectedAuthorIdentity = this.getSignerAddress();
            }
            console.log('WalletStore: Author identity restored to:', this.selectedAuthorIdentity);
        },

        async validateNameForCurrentWallet(name) {
            console.log('WalletStore: Validating name for current wallet:', name);
            if (!this.isWalletConnected()) {
                console.warn('WalletStore: Validation failed - no wallet connected');
                return false;
            }
            try {
                const address = this.getSignerAddress();
                const names = await this.fetchNamesByDestination(address);
                const isValid = names.includes(name);
                console.log('WalletStore: Name validation result:', isValid);
                return isValid;
            } catch (error) {
                console.error("WalletStore: Validation error:", error);
                return false;
            }
        },

        async fetchNamesByDestination(address) {
            console.log('WalletStore: Fetching names for address:', address);
            if (this.addressNames[address]) {
                console.log('WalletStore: Using cached names:', this.addressNames[address]);
                return this.addressNames[address];
            }
            try {
                const url = `${this.restUrl}/dysonprotocol/nameservice/v1/names_by_destination/${address}`;
                console.log('WalletStore: Fetching from URL:', url);
                const resp = await fetch(url);
                if (!resp.ok) {
                    console.warn(`WalletStore: Fetch names failed: ${resp.status}`);
                    this.addressNames[address] = [];
                    return [];
                }
                const json = await resp.json();
                const names = json.names || [];
                this.addressNames[address] = names;
                console.log('WalletStore: Names fetched successfully:', names);
                return names;
            } catch (error) {
                console.error("WalletStore: Fetch error:", error);
                this.addressNames[address] = [];
                return [];
            }
        },

        async connectNamedCosmJsWallet(name, password) {
            console.log('WalletStore: Connecting to CosmJS wallet:', name);
            const walletData = this.localCosmJsWallets.find((w) => w.name === name);
            if (!walletData) {
                console.error('WalletStore: Wallet not found:', name);
                throw new Error(`No wallet "${name}"`);
            }
            if (!password.trim()) {
                console.error('WalletStore: Password required for wallet:', name);
                throw new Error("Password required");
            }

            try {
                console.log('WalletStore: Extracting KDF configuration...');
                const kdfConf = extractKdfConfiguration(walletData.encrypted);
                console.log('WalletStore: Executing KDF...');
                const encryptionKey = await executeKdf(password, kdfConf);
                console.log('WalletStore: Deserializing wallet...');
                const wallet = await DirectSecp256k1HdWallet.deserializeWithEncryptionKey(walletData.encrypted, encryptionKey);
                const address = (await wallet.getAccounts())[0].address;

                this.activeWalletMeta = { name, address, type: COSMJS_WALLET_TYPE };
                this.activeWalletInstance = wallet;
                this.addressNames = {};
                this.selectedAuthorIdentity = address;

                console.log('WalletStore: CosmJS wallet connected successfully:', { name, address });
            } catch (error) {
                console.error('WalletStore: Failed to connect CosmJS wallet:', error);
                throw error;
            }
        },

        async connectExtension(type) {
            console.log('WalletStore: Connecting to extension wallet:', type);
            const provider = type === "keplr" ? window.keplr : null;
            if (!provider) {
                console.error('WalletStore: Extension not found:', type);
                throw new Error(`Extension not found: ${type}`);
            }

            try {
                await this.loadChainIdFromApi();
                console.log('WalletStore: Suggesting chain if needed...');
                await this.suggestChainIfNeeded(provider);
                console.log('WalletStore: Getting offline signer...');
                const offlineSigner = provider.getOfflineSigner(this.chainId);
                console.log('WalletStore: Getting key from provider...');
                let { name, bech32Address: address } = await provider.getKey(this.chainId);

                this.activeWalletMeta = { name: String(name), address: String(address), type: String(type) };
                this.activeWalletInstance = offlineSigner;
                this.addressNames = {};
                this.selectedAuthorIdentity = address;

                console.log('WalletStore: Extension wallet connected successfully:', { name, address, type });
            } catch (error) {
                console.error('WalletStore: Failed to connect extension wallet:', error);
                throw error;
            }
        },

        disconnectWallet() {
            console.log('WalletStore: Disconnecting wallet...');
            const previousWallet = this.activeWalletMeta;
            this.activeWalletMeta = null;
            this.activeWalletInstance = null;
            this.selectedAuthorIdentity = null;
            this.addressNames = {};
            console.log('WalletStore: Wallet disconnected:', previousWallet);
        },

        // Deprecated methods omitted for brevity

        async loadChainIdFromApi() {
            console.log('WalletStore: Loading chain ID from API...');
            const url = `${this.restUrl}/cosmos/base/tendermint/v1beta1/node_info`;
            console.log('WalletStore: Fetching node info from:', url);

            try {
                const resp = await fetch(url);
                if (!resp.ok) {
                    const errorText = await resp.text();
                    console.error('WalletStore: Node info failed:', resp.status, errorText);
                    throw new Error(`Node info failed: ${errorText}`);
                }
                const json = await resp.json();
                const discovered = json?.default_node_info?.network;
                if (!discovered) {
                    console.error('WalletStore: No chainId in response:', json);
                    throw new Error("No chainId");
                }
                this.chainId = discovered;
                console.log('WalletStore: Chain ID loaded successfully:', this.chainId);
            } catch (error) {
                console.error('WalletStore: Failed to load chain ID:', error);
                throw error;
            }
        },

        async suggestChainIfNeeded(provider) {
            console.log('WalletStore: Suggesting chain to provider...');
            const chainInfo = {
                chainId: this.chainId,
                chainName: "Dyson Chain",
                rpc: "http://localhost:26657",
                rest: this.restUrl,
                bip44: { coinType: 118 },
                bech32Config: {
                    bech32PrefixAccAddr: "dys2",
                    bech32PrefixAccPub: "dys2pub",
                    bech32PrefixValAddr: "dys2valoper",
                    bech32PrefixValPub: "dys2valoperpub",
                    bech32PrefixConsAddr: "dys2valcons",
                    bech32PrefixConsPub: "dys2valconspub",
                },
                currencies: [{ coinDenom: "DYS", coinMinimalDenom: "udys", coinDecimals: 6 }],
                feeCurrencies: [{ coinDenom: "DYS", coinMinimalDenom: "udys", coinDecimals: 6 }],
                stakeCurrency: { coinDenom: "DYS", coinMinimalDenom: "udys", coinDecimals: 6 },
                gasPriceStep: { low: 0.0, average: 0.00001, high: 0.00002 },
            };

            try {
                console.log('WalletStore: Attempting to enable chain:', this.chainId);
                await provider.enable(this.chainId);
                console.log('WalletStore: Chain enabled successfully');
            } catch (error) {
                console.log('WalletStore: Chain not known, suggesting chain config...');
                await provider.experimentalSuggestChain(chainInfo);
                console.log('WalletStore: Chain suggested, enabling...');
                await provider.enable(this.chainId);
                console.log('WalletStore: Chain enabled after suggestion');
            }
        },

        buildFee(gasLimit) {
            const limit = Number(gasLimit) || 200000;
            const price = Number(this.gasPrice) || 0;
            const totalAmount = Math.floor(limit * price);
            const fee = {
                amount: [{ denom: "udys", amount: String(totalAmount) }],
                gas_limit: String(limit),
            };
            console.log('WalletStore: Built fee:', fee);
            return fee;
        },

        listLocalCosmJsWallets() {
            console.log('WalletStore: Listing local CosmJS wallets:', this.localCosmJsWallets.length);
            return [...this.localCosmJsWallets];
        },

        async generateMnemonic(length = 24) {
            console.log('WalletStore: Generating mnemonic with length:', length);
            const wallet = await DirectSecp256k1HdWallet.generate(length);
            console.log('WalletStore: Mnemonic generated successfully');
            return wallet.mnemonic;
        },

        async importNamedCosmJsWallet(name, mnemonic, password) {
            console.log('WalletStore: Importing CosmJS wallet:', name);
            if (!name.trim()) {
                console.error('WalletStore: Name required for wallet import');
                throw new Error("Name required");
            }
            if (!mnemonic.trim()) {
                console.error('WalletStore: Mnemonic empty for wallet import');
                throw new Error("Mnemonic empty");
            }
            if (!password.trim()) {
                console.error('WalletStore: Password required for wallet import');
                throw new Error("Password required");
            }
            if (this.localCosmJsWallets.find((w) => w.name === name.trim())) {
                console.error('WalletStore: Wallet already exists:', name);
                throw new Error(`Wallet "${name}" exists`);
            }

            try {
                console.log('WalletStore: Creating wallet from mnemonic...');
                const wallet = await DirectSecp256k1HdWallet.fromMnemonic(mnemonic, { prefix: DEFAULT_CHAIN_INFO.bech32Prefix });
                const kdfConfig = { algorithm: "argon2id", params: { outputLength: 32, opsLimit: 24, memLimitKib: 12 * 1024 } };
                console.log('WalletStore: Executing KDF for encryption...');
                const encryptionKey = await executeKdf(password, kdfConfig);
                console.log('WalletStore: Serializing wallet with encryption...');
                const encrypted = await wallet.serializeWithEncryptionKey(encryptionKey, kdfConfig);
                const address = (await wallet.getAccounts())[0].address;

                this.localCosmJsWallets.push({ name: name.trim(), encrypted, _pass: password, address });
                console.log('WalletStore: Wallet imported successfully:', { name: name.trim(), address });
            } catch (error) {
                console.error('WalletStore: Failed to import wallet:', error);
                throw error;
            }
        },

        removeNamedCosmJsWallet(name) {
            console.log('WalletStore: Removing CosmJS wallet:', name);
            const idx = this.localCosmJsWallets.findIndex((w) => w.name === name);
            if (idx === -1) {
                console.error('WalletStore: Wallet not found for removal:', name);
                throw new Error(`Wallet "${name}" not found`);
            }
            if (this.activeWalletMeta?.name === name) {
                console.log('WalletStore: Disconnecting active wallet before removal');
                this.disconnectWallet();
            }
            this.localCosmJsWallets.splice(idx, 1);
            console.log('WalletStore: Wallet removed successfully:', name);
        },

        getWallet() {
            console.log('WalletStore: Getting wallet instance...');
            if (!this.activeWalletMeta) {
                console.error('WalletStore: No wallet available');
                throw new Error("No wallet");
            }
            if (this.activeWalletMeta.type === "keplr" && !this.activeWalletInstance) {
                console.log('WalletStore: Recreating Keplr wallet instance...');
                const provider = window.keplr;
                if (!provider) {
                    console.error('WalletStore: Keplr not found when recreating instance');
                    throw new Error("Keplr not found");
                }
                const offlineSigner = provider.getOfflineSigner(this.chainId);
                this.activeWalletInstance = offlineSigner;
                console.log('WalletStore: Keplr wallet instance recreated');
            }
            if (!this.activeWalletInstance) {
                console.error('WalletStore: Wallet instance expired');
                throw new Error("Wallet expired");
            }
            console.log('WalletStore: Wallet instance ready:', this.activeWalletMeta.type);
            return { ...this.activeWalletMeta, walletInstance: this.activeWalletInstance };
        },

        async getAccountInfo() {
            console.log('WalletStore: Getting account info...');
            const { address } = this.getWallet();
            try {
                const accountInfo = await getChainInfo({ apiUrl: this.restUrl, address });
                console.log('WalletStore: Account info retrieved:', accountInfo);
                return accountInfo;
            } catch (error) {
                console.error('WalletStore: Failed to get account info:', error);
                throw error;
            }
        },

        async sendMsg({ msg, gasLimit, memo = "" }) {
            console.log('WalletStore: Sending message...', { msgType: msg['@type'], gasLimit, memo });
            const { walletInstance, address, type } = this.getWallet();
            let finalGasLimit = gasLimit;

            if (gasLimit == null) {
                console.log('WalletStore: Gas limit not specified, determining automatically...');
                if (type === COSMJS_WALLET_TYPE) {
                    console.log('WalletStore: Running simulation for gas estimation...');
                    const simulationResult = await sendMsgs({
                        apiUrl: this.restUrl,
                        wallet: walletInstance,
                        walletType: type,
                        address,
                        msgs: [msg],
                        memo,
                        fee: this.buildFee(200000),
                        simulate: true,
                    });
                    if (!simulationResult.success) {
                        console.error('WalletStore: Simulation failed:', simulationResult.rawLog);
                        throw new Error(`Simulation failed: ${simulationResult.rawLog || 'Unknown'}`);
                    }
                    const gasUsed = parseInt(simulationResult.gasUsed || "0");
                    finalGasLimit = gasUsed > 0 ? Math.ceil(gasUsed * 1.5) : 200000;
                    console.log('WalletStore: Gas estimation complete:', { gasUsed, finalGasLimit });
                } else {
                    finalGasLimit = 200000;
                    console.log('WalletStore: Using default gas limit for extension wallet:', finalGasLimit);
                }
            }

            const fee = this.buildFee(finalGasLimit);

            // Create transaction history entry immediately when user clicks "Send Tx"
            const txId = this.getNextId();
            console.log('WalletStore: Created transaction entry immediately:', { txId, finalGasLimit });

            this.txHistory.push({
                txId,
                txHash: null,
                status: 'pending',
                progress: null, // Start with null progress to show activity
                timestamp: new Date(),
                msgs: [msg],
                memo,
                fee,
                result: null,
                error: null
            });
            const entry = this.txHistory[this.txHistory.length - 1]; // Get the entry we just added

            let result;
            try {
                console.log('WalletStore: Executing sendMsgs...');
                result = await sendMsgs({
                    apiUrl: this.restUrl,
                    wallet: walletInstance,
                    walletType: type,
                    address,
                    msgs: [msg],
                    memo,
                    fee,
                    simulate: false,
                });

                // Handle user cancellation
                if (result.code === -1) {
                    console.log('WalletStore: Transaction cancelled by user');
                    entry.status = 'failed';
                    entry.error = 'Transaction cancelled by user';
                    return result;
                }

                entry.txHash = result.raw?.tx_response?.txhash;
                console.log('WalletStore: Transaction hash received:', entry.txHash);

                if (result.success) {
                    console.log('WalletStore: Transaction successful');
                    entry.status = 'success';
                    entry.result = result;
                    await this.watchMempoolAndUpdateProgress(txId); // Poll for inclusion
                } else {
                    console.error('WalletStore: Transaction failed:', result.rawLog);
                    entry.status = 'failed';
                    entry.error = result.rawLog;
                    // Check for actual out-of-gas errors in the message text, not just error code
                    const errorMessage = result.rawLog?.toLowerCase() || '';
                    if (errorMessage.includes('out of gas') || errorMessage.includes('gas limit exceeded') || errorMessage.includes('insufficient gas')) {
                        console.log('WalletStore: Out of gas detected, offering retry...');
                        if (confirm("Out of gas. Retry with higher gas?")) {
                            console.log('WalletStore: User accepted gas retry');
                            return this.sendMsg({ msg, gasLimit: Math.ceil(finalGasLimit * 1.5), memo });
                        }
                    } else if (errorMessage.includes('insufficient funds') || errorMessage.includes('balance') || errorMessage.includes('spendable')) {
                        console.log('WalletStore: Insufficient funds detected');
                        // Don't offer gas retry for insufficient funds
                    }
                }
            } catch (error) {
                console.error('WalletStore: Exception during sendMsg:', error);

                // Update the transaction entry with error details
                entry.status = 'failed';

                // Provide user-friendly error messages
                if (error.message.includes('Request rejected') || error.message.includes('rejected')) {
                    entry.error = 'Transaction rejected by user';
                    console.log('WalletStore: User rejected transaction in wallet');
                } else if (error.message.includes('Insufficient funds')) {
                    entry.error = 'Insufficient funds';
                } else if (error.message.includes('gas')) {
                    entry.error = 'Gas estimation failed';
                } else {
                    entry.error = error.message || 'Transaction failed';
                }

                // Don't re-throw for user rejections, return gracefully
                if (error.message.includes('Request rejected') || error.message.includes('rejected')) {
                    return { success: false, code: -1, rawLog: entry.error };
                }

                throw error; // Re-throw for other errors
            }

            this.updateLastTxChoices({ gasPrice: this.gasPrice, memo });
            console.log('WalletStore: sendMsg complete:', { txId, success: result?.success });
            return result;
        },

        async runDysonScript({
            scriptAddress,
            functionName = "",
            args = "",
            kwargs = "",
            extraCode = "",
            attachedMsg = [],
            memo = "",
            gasLimit = 100000000,
            simulate = false,
        }) {
            console.log('WalletStore: Running Dyson script...', {
                scriptAddress,
                functionName,
                args: args.length,
                kwargs: kwargs.length,
                extraCode: extraCode.length,
                attachedMsg: attachedMsg.length,
                memo,
                gasLimit,
                simulate
            });

            const { walletInstance, address, type } = this.getWallet();
            if (!scriptAddress) {
                console.error('WalletStore: Script address required');
                throw new Error("scriptAddress required");
            }

            let finalGasLimit = gasLimit;
            if (gasLimit === "auto" && !simulate) {
                console.log('WalletStore: Auto gas limit requested, running simulation...');
                if (type === COSMJS_WALLET_TYPE) {
                    const simulationResult = await runScript({
                        apiUrl: this.restUrl,
                        wallet: walletInstance,
                        walletType: type,
                        executorAddress: address,
                        scriptAddress,
                        functionName,
                        args,
                        kwargs,
                        extraCode,
                        attachedMsg,
                        memo,
                        fee: this.buildFee(100000000),
                        simulate: true,
                    });
                    if (!simulationResult.success) {
                        console.error('WalletStore: Script simulation failed');
                        return simulationResult;
                    }
                    const gasUsed = parseInt(simulationResult.rawSendMsgsResponse?.gasUsed || "0");
                    finalGasLimit = gasUsed > 0 ? Math.round(gasUsed * 1.5) : 100000000;
                    console.log('WalletStore: Script gas estimation:', { gasUsed, finalGasLimit });
                } else {
                    finalGasLimit = 100000000;
                    console.log('WalletStore: Using default gas for extension wallet script');
                }
            }

            const fee = this.buildFee(finalGasLimit);

            // Create transaction history entry immediately when script execution starts
            const txId = this.getNextId();
            console.log('WalletStore: Created script transaction entry immediately:', { txId, finalGasLimit });

            this.txHistory.push({
                txId,
                txHash: null,
                status: 'pending',
                progress: null, // Start with null progress to show activity
                timestamp: new Date(),
                msgs: [{ scriptAddress, functionName, args, kwargs, extraCode, attachedMsg }],
                memo,
                fee,
                result: null,
                error: null
            });
            const entry = this.txHistory[this.txHistory.length - 1]; // Get the entry we just added

            let result;
            try {
                console.log('WalletStore: Executing runScript...');
                result = await runScript({
                    apiUrl: this.restUrl,
                    wallet: walletInstance,
                    walletType: type,
                    executorAddress: address,
                    scriptAddress,
                    functionName,
                    args,
                    kwargs,
                    extraCode,
                    attachedMsg,
                    memo,
                    fee,
                    simulate,
                });

                // Handle user cancellation
                if (result.rawSendMsgsResponse?.code === -1) {
                    console.log('WalletStore: Script transaction cancelled by user');
                    entry.status = 'failed';
                    entry.error = 'Script transaction cancelled by user';
                    return result;
                }

                entry.txHash = result.rawSendMsgsResponse?.raw?.tx_response?.txhash;
                console.log('WalletStore: Script transaction hash:', entry.txHash);

                if (result.success) {
                    console.log('WalletStore: Script execution successful');
                    entry.status = 'success';
                    entry.result = result;
                    if (!simulate) await this.watchMempoolAndUpdateProgress(txId);
                } else {
                    console.error('WalletStore: Script execution failed:', result.rawSendMsgsResponse?.rawLog);
                    entry.status = 'failed';
                    entry.error = result.rawSendMsgsResponse?.rawLog;
                    // Check for actual out-of-gas errors in the message text, not just error code
                    const errorMessage = result.rawSendMsgsResponse?.rawLog?.toLowerCase() || '';
                    if (errorMessage.includes('out of gas') || errorMessage.includes('gas limit exceeded') || errorMessage.includes('insufficient gas')) {
                        console.log('WalletStore: Script out of gas, offering retry...');
                        if (confirm("Out of gas. Retry?")) {
                            console.log('WalletStore: User accepted script gas retry');
                            return this.runDysonScript({ scriptAddress, functionName, args, kwargs, extraCode, attachedMsg, memo, gasLimit: Math.ceil(finalGasLimit * 1.5), simulate });
                        }
                    } else if (errorMessage.includes('insufficient funds') || errorMessage.includes('balance') || errorMessage.includes('spendable')) {
                        console.log('WalletStore: Script insufficient funds detected');
                        // Don't offer gas retry for insufficient funds
                    }
                }
            } catch (error) {
                console.error('WalletStore: Exception during runDysonScript:', error);

                // Update the transaction entry with error details
                entry.status = 'failed';

                // Provide user-friendly error messages
                if (error.message.includes('Request rejected') || error.message.includes('rejected')) {
                    entry.error = 'Script transaction rejected by user';
                    console.log('WalletStore: User rejected script transaction in wallet');
                } else if (error.message.includes('Insufficient funds')) {
                    entry.error = 'Insufficient funds for script execution';
                } else if (error.message.includes('gas')) {
                    entry.error = 'Gas estimation failed for script';
                } else if (error.message.includes('script')) {
                    entry.error = `Script error: ${error.message}`;
                } else {
                    entry.error = error.message || 'Script execution failed';
                }

                // Don't re-throw for user rejections, return gracefully
                if (error.message.includes('Request rejected') || error.message.includes('rejected')) {
                    return { success: false, rawSendMsgsResponse: { code: -1, rawLog: entry.error } };
                }

                throw error; // Re-throw for other errors
            }

            this.updateLastTxChoices({ gasPrice: this.gasPrice, memo });
            console.log('WalletStore: runDysonScript complete:', { txId, success: result?.success });
            return result;
        },

        async watchMempoolAndUpdateProgress(txId) {
            console.log('WalletStore: Starting transaction watch for txId:', txId);
            const entry = this.txHistory.find(t => t.txId === txId);
            if (!entry) {
                console.warn('WalletStore: Transaction entry not found:', txId);
                return;
            }

            const maxAttempts = 60; // 2 minutes if poll every 2s
            const intervalMs = 2000;
            let attempt = 0;

            const checkTxStatus = async () => {
                attempt++;
                console.log(`WalletStore: Transaction check ${attempt}/${maxAttempts} for tx:`, entry.txHash || 'no-hash');

                try {
                    if (!entry.txHash) {
                        // Still waiting for transaction hash from broadcast
                        console.log('WalletStore: Still waiting for transaction hash...');
                        // Keep progress as null for animated progress bar

                        if (attempt > 15) { // 30 seconds without hash
                            console.warn('WalletStore: Timeout waiting for transaction hash');
                            entry.status = 'failed';
                            entry.error = 'Broadcast timeout - no transaction hash received';
                            return;
                        }
                    } else {
                        // Check if transaction has been included in a block
                        const txRes = await fetch(`${this.restUrl}/cosmos/tx/v1beta1/txs/${entry.txHash}`);
                        if (txRes.ok) {
                            const txData = await txRes.json();
                            const height = txData.tx_response?.height;
                            const code = txData.tx_response?.code || 0;

                            if (height && height !== "0") {
                                console.log('WalletStore: Transaction included in block, height:', height);
                                entry.status = code === 0 ? 'included' : 'failed';
                                entry.progress = 100;
                                entry.result = txData;
                                entry.timestamp = new Date(); // Update timestamp to reflect completion time
                                if (code !== 0) {
                                    entry.error = txData.tx_response?.raw_log || 'Transaction failed on chain';
                                }
                                return; // Stop watching
                            } else {
                                // Still in mempool, keep progress null for animated bar
                                console.log('WalletStore: Transaction still pending in mempool');
                            }
                        } else if (txRes.status === 404) {
                            // Transaction not found - might have been dropped or not yet propagated
                            console.log('WalletStore: Transaction not found (404), might be dropped or not yet propagated');
                            // Keep progress null for animated bar
                        } else {
                            console.warn('WalletStore: Error checking transaction status:', txRes.status);
                        }
                    }

                    // Continue checking if still pending and under max attempts
                    if (entry.status === 'pending' && attempt < maxAttempts) {
                        setTimeout(checkTxStatus, intervalMs);
                    } else if (entry.status === 'pending') {
                        console.warn('WalletStore: Timeout waiting for transaction inclusion:', entry.txHash);
                        entry.status = 'failed';
                        entry.error = 'Timeout - transaction may have been dropped from mempool';
                        entry.timestamp = new Date(); // Update timestamp to reflect failure time
                    }

                } catch (error) {
                    console.warn('WalletStore: Transaction check error:', error);
                    // Keep progress null for animated bar during network errors

                    // Continue checking unless we've exceeded max attempts
                    if (attempt < maxAttempts) {
                        setTimeout(checkTxStatus, intervalMs);
                    } else {
                        entry.status = 'failed';
                        entry.error = `Network error after ${maxAttempts} attempts: ${error.message}`;
                        entry.timestamp = new Date(); // Update timestamp to reflect failure time
                    }
                }
            };

            // Start the checking process
            setTimeout(checkTxStatus, 1000); // Start after 1 second
        },

        updateLastTxChoices({ gasPrice, memo }) {
            console.log('WalletStore: Updating last tx choices:', { gasPrice, memo });
            this.lastTxChoices.gasPrice = gasPrice;
            this.lastTxChoices.memo = memo;
        },

        getTxHistory() {
            return this.txHistory.sort((a, b) => b.txId - a.txId); // Highest ID first
        },

        getPendingTxHistory() {
            return this.txHistory.filter(tx => tx.status === 'pending').sort((a, b) => b.timestamp - a.timestamp);
        },

        getSuccessfulTxHistory() {
            return this.txHistory.filter(tx => tx.status === 'success' || tx.status === 'included');
        },

        getFailedTxHistory() {
            return this.txHistory.filter(tx => tx.status === 'failed');
        },

        getRelativeTime(timestamp) {
            if (!timestamp) return 'Unknown';

            // Ensure timestamp is a Date object
            const date = timestamp instanceof Date ? timestamp : new Date(timestamp);

            // Check if the date is valid
            if (isNaN(date.getTime())) {
                console.warn('WalletStore: Invalid timestamp:', timestamp);
                return 'Invalid date';
            }

            const now = new Date();
            const diff = now - date;
            const seconds = Math.floor(diff / 1000);
            const minutes = Math.floor(diff / (1000 * 60));
            const hours = Math.floor(diff / (1000 * 60 * 60));
            const days = Math.floor(diff / (1000 * 60 * 60 * 24));

            if (seconds < 60) return `${seconds}s ago`;
            if (minutes < 60) return `${minutes}m ago`;
            if (hours < 24) return `${hours}h ago`;
            return `${days}d ago`;
        },

        getTxTypeDisplay(tx) {
            if (!tx.msgs || !tx.msgs.length) return 'Unknown';

            const msg = tx.msgs[0];
            if (typeof msg === 'object' && msg['@type']) {
                const type = msg['@type'];
                if (type.includes('MsgExec')) return 'Script Execution';
                if (type.includes('MsgSend')) return 'Token Transfer';
                if (type.includes('MsgDelegate')) return 'Delegate';
                if (type.includes('MsgUndelegate')) return 'Undelegate';
                if (type.includes('storage')) return 'Storage';
                if (type.includes('nameservice')) return 'Name Service';
                return type.split('.').pop().replace('Msg', '');
            }

            // Handle script transactions
            if (msg.scriptAddress) return 'Script';
            if (msg.functionName) return `Script: ${msg.functionName}`;

            return 'Transaction';
        },

        async refreshPendingTxs() {
            console.log('WalletStore: Manually refreshing pending transactions...');
            const pendingTxs = this.getPendingTxHistory();
            console.log('WalletStore: Found pending transactions:', pendingTxs.length);

            for (const tx of pendingTxs) {
                if (tx.txHash) {
                    console.log('WalletStore: Checking status for tx:', tx.txHash);
                    try {
                        const txRes = await fetch(`${this.restUrl}/cosmos/tx/v1beta1/txs/${tx.txHash}`);
                        if (txRes.ok) {
                            const txData = await txRes.json();
                            const height = txData.tx_response?.height;
                            const code = txData.tx_response?.code || 0;

                            if (height && height !== "0") {
                                console.log('WalletStore: Transaction included in block:', tx.txHash, 'height:', height);
                                tx.status = 'included';
                                tx.progress = 100;
                                tx.result = txData;
                                tx.timestamp = new Date(); // Update timestamp to reflect completion time
                            } else if (code !== 0) {
                                console.log('WalletStore: Transaction failed:', tx.txHash, 'code:', code);
                                tx.status = 'failed';
                                tx.error = txData.tx_response?.raw_log || 'Transaction failed';
                                tx.timestamp = new Date(); // Update timestamp to reflect failure time
                            } else {
                                console.log('WalletStore: Transaction still pending:', tx.txHash);
                                // Keep progress null for animated bar
                            }
                        }
                    } catch (error) {
                        console.warn('WalletStore: Error checking transaction status:', error);
                    }
                } else {
                    // No hash yet, probably still submitting
                    const elapsed = Date.now() - tx.timestamp.getTime();
                    if (elapsed > 30000) { // 30 seconds without hash = likely failed
                        console.warn('WalletStore: Transaction timeout without hash:', tx.txId);
                        tx.status = 'failed';
                        tx.error = 'Submission timeout';
                        tx.timestamp = new Date(); // Update timestamp to reflect failure time
                    }
                }
            }

            console.log('WalletStore: Pending transactions refresh complete');
        },

        clearTxHistory() {
            console.log('WalletStore: Clearing transaction history, count:', this.txHistory.length);
            this.txHistory = [];
        },

        // Toast demo with DaisyUI: Add to HTML: <div x-data="{ toasts: $store.walletStore.toasts }" class="toast toast-top toast-end" x-show="toasts.length > 0">
        // <template x-for="toast in toasts">
        // <div :class="`alert alert-${toast.type}`"><span x-text="toast.message"></span></div>
        // </template></div>
        showToast(message, type = 'info', duration = 5000) { // Call on modal close: this.showToast(`Tx ${txId} pending`, 'info')
            const id = this.getNextId();
            console.log('WalletStore: Showing toast:', { id, message, type, duration });
            this.toasts.push({ id, message, type });
            const timeoutId = setTimeout(() => {
                this.toasts = this.toasts.filter(t => t.id !== id);
                console.log('WalletStore: Toast expired:', id);
            }, duration);
        },

        // Other methods (signArbitraryData, loadDenomMetadata, normalizeCoin) remain unchanged
    });
});