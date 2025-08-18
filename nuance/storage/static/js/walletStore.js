import { DirectSecp256k1HdWallet, makeSignDoc, makeSignBytes, executeKdf, extractKdfConfiguration } from "@cosmjs/proto-signing";
import { getChainInfo, sendMsgs, runScript, signData, encodeAndDecodeTx } from "./dysonTxUtils.js";
import { Tx, TxBody, AuthInfo, TxRaw } from "cosmjs-types/cosmos/tx/v1beta1/tx.js";
import { toBase64, fromBase64 } from "@cosmjs/encoding";

const DEFAULT_CHAIN_INFO = {
  restUrl: window.location.origin, // Use current domain instead of hardcoded localhost
  bech32Prefix: "dys2", // same as chain prefix
};

const COSMJS_WALLET_TYPE = "cosmjs";

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
    denomMetadatas: [], // Cache for denom metadata
    
    // Author identity management (separate from wallet/signer)
    selectedAuthorIdentity: Alpine.$persist(null), // Can be address or name
    addressNames: {}, // Cache for fetched names by address

    // Call this somewhere (e.g. <body x-init="$store.walletStore.init()">
    async init() {      
      console.log("walletStore init");
      await this.loadChainIdFromApi();
      
      // Attempt to reconnect if activeWalletMeta is set
      if (this.activeWalletMeta) {
        if (this.activeWalletMeta.type === "keplr") {
          const provider = window.keplr;
          if (!provider) {
            console.error("Keplr extension not found, please install it.");
            this.disconnectWallet();
          } else {
            const offlineSigner = provider.getOfflineSigner(this.chainId);
            this.activeWalletInstance = offlineSigner;
            // Restore author identity after reconnection
            await this.restoreAuthorIdentity();
          }
        } else if (this.activeWalletMeta.type === COSMJS_WALLET_TYPE) {
          const walletData = this.localCosmJsWallets.find((w) => w.name === this.activeWalletMeta.name);
          if (walletData && walletData._pass && walletData._pass.trim() !== "") {
            try {
              await this.connectNamedCosmJsWallet(walletData.name, walletData._pass);
              // Restore author identity after reconnection
              await this.restoreAuthorIdentity();
            } catch (error) {
              console.error("Auto reconnection failed for wallet", walletData.name, error);
            }
          }
        }
      }
      // TODO: remove this
      if (this.localCosmJsWallets.length === 0 && this.chainId === 'cahin-a') {
        // TODO: remove this
        const seed = "public feature teach face federal matrix throw legend bridge brass diary beach typical doll evoke weapon among crane regret trust enact swarm brother outside"; 
        console.log("creating default wallet");
        await this.importNamedCosmJsWallet("alice", seed, "password");
        await this.connectNamedCosmJsWallet("alice", "password");
      }

      // Mark as loaded
      this.isLoading = false;
      
    },

    // ========================================
    // SIGNER METHODS (Wallet Address)
    // ========================================
    
    /**
     * Get the wallet address that signs transactions
     * @returns {string} The wallet address
     */
    getSignerAddress() {
      if (!this.activeWalletMeta?.address) {
        throw new Error("No wallet connected.");
      }
      return this.activeWalletMeta.address;
    },

    /**
     * Check if a wallet is connected
     * @returns {boolean}
     */
    isWalletConnected() {
      return !!this.activeWalletMeta?.address;
    },

    // ========================================
    // AUTHOR IDENTITY METHODS
    // ========================================
    
         /**
      * Get the current author identity (can be address or name)
      * @returns {string} The author identity to use for posts/profiles
      */
     getAuthorIdentity() {
      
       if (!this.isWalletConnected()) {

         throw new Error("No wallet connected.");
       }
       
       // If no author identity is set, default to wallet address
       const result = this.selectedAuthorIdentity || this.getSignerAddress();
      
       return result;
     },

    /**
     * Set the author identity
     * @param {string} identity - Can be wallet address or a name
     */
    async setAuthorIdentity(identity) {
      if (!this.isWalletConnected()) {
        throw new Error("No wallet connected.");
      }
      
      // Validate that this identity is valid for the current wallet
      if (identity !== this.getSignerAddress()) {
        // If it's not the wallet address, verify it's a name that resolves to this address
        const isValid = await this.validateNameForCurrentWallet(identity);
        if (!isValid) {
          throw new Error(`Identity "${identity}" does not resolve to current wallet address.`);
        }
      }
      
      this.selectedAuthorIdentity = identity;
    },

         /**
      * Get available author identities for the current wallet
      * @returns {Promise<Array<string>>} Array of available identities (address + names)
      */
     async getAvailableAuthorIdentities() {
       
       if (!this.isWalletConnected()) {
         return [];
       }
       
       const address = this.getSignerAddress();
       
       const [destNames, ownedNames] = await Promise.all([
         this.fetchNamesByDestination(address),
         this.fetchNamesOwnedByAddress(address),
       ]);
       
       const identities = [address, ...destNames, ...ownedNames];
       const seen = new Set();
       const unique = [];
       for (const id of identities) {
         if (!seen.has(id)) {
           seen.add(id);
           unique.push(id);
         }
       }
       
       return unique;
     },

    /**
     * Get display text for an identity option
     * @param {string} identity 
     * @returns {string}
     */
    getDisplayTextForIdentity(identity) {
      
      const address = this.getSignerAddress();
      
      // If the identity is the address itself, truncate it
      if (identity === address) {
        if (identity.length <= 13) return identity;
        return identity.slice(0, 10) + '...' + identity.slice(-5);
      }
      
      // If it's a name, show it in full
      return identity;
    },

         /**
      * Restore author identity after wallet reconnection
      */
     async restoreAuthorIdentity() {
       if (this.selectedAuthorIdentity) {
         try {
           // Validate the stored identity is still valid for current wallet
           if (this.selectedAuthorIdentity !== this.getSignerAddress()) {
             const isValid = await this.validateNameForCurrentWallet(this.selectedAuthorIdentity);
             if (!isValid) {
               console.warn("Stored author identity is no longer valid for current wallet, resetting to wallet address");
               this.selectedAuthorIdentity = this.getSignerAddress();
               return;
             }
           }
           // Identity is valid (either it's the wallet address or a valid name)
         } catch (error) {
           console.warn("Error validating stored author identity, resetting to wallet address:", error);
           this.selectedAuthorIdentity = this.getSignerAddress();
         }
       } else {
         // No stored identity, default to wallet address
         this.selectedAuthorIdentity = this.getSignerAddress();
       }
     },

    /**
     * Validate that a name resolves to the current wallet address
     * @param {string} name 
     * @returns {Promise<boolean>}
     */
    async validateNameForCurrentWallet(name) {
      if (!this.isWalletConnected()) {
        return false;
      }
      
      try {
        const address = this.getSignerAddress();
        // Check destination resolution
        {
          const url = `${this.restUrl}/dysonprotocol/nameservice/v1/resolve_name/${encodeURIComponent(name)}`;
          const resp = await fetch(url);
          if (resp.ok) {
            const json = await resp.json();
            if (json?.address === address) return true;
          }
        }
        // Check NFT owner of the name
        {
          const url = `${this.restUrl}/dysonprotocol/nft/v1beta1/owner?class_id=nameservice.dys&id=${encodeURIComponent(name)}`;
          const resp = await fetch(url);
          if (resp.ok) {
            const json = await resp.json();
            if (json?.owner === address) return true;
          }
        }
        return false;
      } catch (error) {
        console.error("Error validating name:", error);
        return false;
      }
    },

    // ========================================
    // NAME RESOLUTION METHODS (Updated)
    // ========================================

    // Fetch names associated with an address
    async fetchNamesByDestination(address) {
      
      if (this.addressNames[address]) {
        return this.addressNames[address];
      }
      
      try {
        const url = `${this.restUrl}/dysonprotocol/nameservice/v1/names_by_destination/${address}`;
        
        const resp = await fetch(url);
        if (!resp.ok) {
          console.warn(`[WalletStore] Failed to fetch names for address ${address}: ${resp.status} ${resp.statusText}`);
          this.addressNames[address] = [];
          return [];
        }
        
        const json = await resp.json();
        
        const names = json.names || [];
        
        this.addressNames[address] = names;
        
        return names;
      } catch (error) {
        console.error(`[WalletStore] Error fetching names for address ${address}:`, error);
        this.addressNames[address] = [];
        return [];
      }
    },

    // Fetch names owned by an address (owner of nameservice.dys NFTs)
    async fetchNamesOwnedByAddress(address) {
      try {
        const params = new URLSearchParams({
          class_id: 'nameservice.dys',
          owner: address,
          'pagination.limit': '1000',
        });
        const url = `${this.restUrl}/dysonprotocol/nft/v1beta1/nfts?${params.toString()}`;
        const resp = await fetch(url);
        if (!resp.ok) {
          console.warn(`[WalletStore] Failed to fetch owned names for ${address}: ${resp.status} ${resp.statusText}`);
          return [];
        }
        const json = await resp.json();
        const nfts = json?.nfts || [];
        return nfts.map(n => n.id).filter(Boolean);
      } catch (error) {
        console.error(`[WalletStore] Error fetching owned names for ${address}:`, error);
        return [];
      }
    },

    // ========================================
    // WALLET CONNECTION METHODS (Updated)
    // ========================================

    async connectNamedCosmJsWallet(name, password) {
      const walletData = this.localCosmJsWallets.find((w) => w.name === name);
      if (!walletData) throw new Error(`No local wallet named "${name}".`);
      if (!password.trim()) throw new Error("Password required to unlock wallet.");

      const kdfConf = extractKdfConfiguration(walletData.encrypted);
      const encryptionKey = await executeKdf(password, kdfConf);
      const wallet = await DirectSecp256k1HdWallet.deserializeWithEncryptionKey(walletData.encrypted, encryptionKey);
      const address = (await wallet.getAccounts())[0].address;

      this.activeWalletMeta = {
        name,
        address,
        type: COSMJS_WALLET_TYPE,
      };
      this.activeWalletInstance = wallet;
      
      // Clear cached names and restore author identity for new wallet
      this.addressNames = {};
      await this.restoreAuthorIdentity();
    },

    async connectExtension(type) {
      const provider = type === "keplr" ? window.keplr : null;
      if (!provider) {
        throw new Error(`Extension not found: ${type}`);
      }
      await this.loadChainIdFromApi();
      await this.suggestChainIfNeeded(provider);

      const offlineSigner = provider.getOfflineSigner(this.chainId);
      let { name, bech32Address: address } = await provider.getKey(this.chainId);
      this.activeWalletMeta = { name: String(name), address: String(address), type: String(type) };
      this.activeWalletInstance = offlineSigner;
      
      // Clear cached names and restore author identity for new wallet
      this.addressNames = {};
      await this.restoreAuthorIdentity();
    },

    disconnectWallet() {
      this.activeWalletMeta = null;
      this.activeWalletInstance = null;
      this.selectedAuthorIdentity = null;
      // Clear cached address names when disconnecting
      this.addressNames = {};
    },

    // ========================================
    // DEPRECATED METHODS (For backwards compatibility)
    // ========================================
    
    // @deprecated Use getAvailableAuthorIdentities() instead
    async getDisplayOptionsForAddress(address) {
      console.warn("getDisplayOptionsForAddress is deprecated, use getAvailableAuthorIdentities()");
      const names = await this.fetchNamesByDestination(address);
      const options = [address];
      names.forEach(name => {
        if (name !== address) {
          options.push(name);
        }
      });
      return options;
    },

    // @deprecated Use getAuthorIdentity() instead
    getSelectedNameForAddress(address) {
      console.warn("getSelectedNameForAddress is deprecated, use getAuthorIdentity()");
      return this.selectedAuthorIdentity || address;
    },

    // @deprecated Use setAuthorIdentity() instead
    setSelectedNameForAddress(address, selectedName) {
      console.warn("setSelectedNameForAddress is deprecated, use setAuthorIdentity()");
      this.selectedAuthorIdentity = selectedName;
    },

    // @deprecated Use getDisplayTextForIdentity() instead
    getDisplayTextForOption(option, address) {
      console.warn("getDisplayTextForOption is deprecated, use getDisplayTextForIdentity()");
      return this.getDisplayTextForIdentity(option);
    },

    // Utilities
    async loadChainIdFromApi() {
      const url = `${this.restUrl}/cosmos/base/tendermint/v1beta1/node_info`;
      const resp = await fetch(url);
      if (!resp.ok) {
        throw new Error(`Failed to fetch node_info: ${await resp.text()}`);
      }
      const json = await resp.json();
      const discovered = json?.default_node_info?.network;
      if (!discovered) {
        throw new Error("No chainId found in node_info response.");
      }
      this.chainId = discovered;
    },

    async suggestChainIfNeeded(provider) {
      const chainInfo = {
        chainId: this.chainId,
        chainName: "Example Dyson Chain",
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
        currencies: [
          { coinDenom: "DYS2", coinMinimalDenom: "udys", coinDecimals: 6 },
        ],
        feeCurrencies: [
          {
            coinDenom: "DYS2",
            coinMinimalDenom: "udys",
            coinDecimals: 6,
            gasPriceStep: { low: 0.0, average: 0.0, high: 0.00002 },
          },
        ],
        stakeCurrency: {
          coinDenom: "DYS2",
          coinMinimalDenom: "udys",
          coinDecimals: 6,
        },
      };

      try {
        await provider.enable(this.chainId);
      } catch {
        await provider.experimentalSuggestChain(chainInfo);
        await provider.enable(this.chainId);
      }
    },

    buildFee(gasLimit) {
      const limit = Number(gasLimit) || 200000;
      const price = Number(this.gasPrice) || 0;
      const totalAmount = Math.floor(limit * price);

      return {
        amount: [
          {
            denom: "udys",
            amount: String(totalAmount),
          },
        ],
        gas_limit: String(limit),
      };
    },

    // Local wallet methods
    listLocalCosmJsWallets() {
      return [...this.localCosmJsWallets];
    },

    async generateMnemonic(length = 24) {
      const wallet = await DirectSecp256k1HdWallet.generate(length);
      return wallet.mnemonic;
    },

    async importNamedCosmJsWallet(name, mnemonic, password) {
      if (!name.trim()) throw new Error("Wallet name is required.");
      if (!mnemonic.trim()) throw new Error("Mnemonic is empty.");
      if (!password.trim()) throw new Error("Password is required.");

      if (this.localCosmJsWallets.find((w) => w.name === name.trim())) {
        throw new Error(`Wallet "${name}" already exists.`);
      }

      const wallet = await DirectSecp256k1HdWallet.fromMnemonic(mnemonic, {
        prefix: DEFAULT_CHAIN_INFO.bech32Prefix,
      });
      const kdfConfig = {
        algorithm: "argon2id",
        params: {
          outputLength: 32,
          opsLimit: 24,
          memLimitKib: 12 * 1024,
        },
      };
      const encryptionKey = await executeKdf(password, kdfConfig);
      const encrypted = await wallet.serializeWithEncryptionKey(encryptionKey, kdfConfig);
      const address = (await wallet.getAccounts())[0].address;

      this.localCosmJsWallets.push({
        name: name.trim(),
        encrypted,
        _pass: password,
        address,
      });
    },

    removeNamedCosmJsWallet(name) {
      const idx = this.localCosmJsWallets.findIndex((w) => w.name === name);
      if (idx === -1) throw new Error(`Wallet "${name}" not found.`);

      // If removing the currently active wallet, disconnect first
      if (this.activeWalletMeta?.name === name) {
        this.disconnectWallet();
      }

      this.localCosmJsWallets.splice(idx, 1);
    },

    getWallet() {
      if (!this.activeWalletMeta) {
        throw new Error("No wallet connected.");
      }
      if (this.activeWalletMeta.type === "keplr" && !this.activeWalletInstance) {
        const provider = window.keplr;
        if (!provider) throw new Error("Keplr extension not found.");
        const offlineSigner = provider.getOfflineSigner(this.chainId);
        this.activeWalletInstance = offlineSigner;
      }
      if (!this.activeWalletInstance) {
        throw new Error("Wallet session expired. Please reconnect your wallet.");
      }
      return { ...this.activeWalletMeta, walletInstance: this.activeWalletInstance };
    },

    async getAccountInfo() {
      const { address } = this.getWallet();
      return getChainInfo({
        apiUrl: this.restUrl,
        address,
      });
    },

    async sendMsg({ msg, gasLimit, memo = "" }) {
      const { walletInstance, address, type } = this.getWallet();
      
              // If gasLimit is null/undefined, estimate gas via simulation
        let finalGasLimit = gasLimit;
        if (gasLimit == null || gasLimit == undefined) {

            // First, simulate to get gas usage
            const simulationResult = await sendMsgs({
              apiUrl: this.restUrl,
              wallet: walletInstance,
              walletType: type,
              address,
              msgs: [msg],
              memo,
              fee: this.buildFee(200000), // Use default gas for simulation
              simulate: true,
            });
            
            // Check if simulation failed
            if (!simulationResult.success) {
              const errorMsg = simulationResult.rawLog || simulationResult.raw?.message || 'Simulation failed';
              
              throw new Error(`Gas estimation failed, code: [${simulationResult.code}] ${errorMsg}`);
            }
            
            // Extract gas used from simulation result
            let gasUsed = 0;
            if (simulationResult?.raw?.gas_info?.gas_used) {
              gasUsed = parseInt(simulationResult.raw.gas_info.gas_used);
            } else if (simulationResult?.gasUsed) {
              gasUsed = parseInt(simulationResult.gasUsed);
            }
            
            // Add 50% buffer to the estimated gas
            finalGasLimit = gasUsed > 0 ? Math.ceil(gasUsed * 1.5) : 200000;
      }
      
      const fee = this.buildFee(finalGasLimit);
      return sendMsgs({
        apiUrl: this.restUrl,
        wallet: walletInstance,
        walletType: type,
        address,
        msgs: [msg],
        memo,
        fee,
        simulate: false,
      });
    },

    // Key method for Dyson scripts:
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
      const { walletInstance, address, type } = this.getWallet();
      if (!scriptAddress) {
        throw new Error("scriptAddress is required.");
      }

      // Handle "auto" gas estimation for CosmJS wallets only
      let finalGasLimit = gasLimit;
      if (gasLimit === "auto" && !simulate) {
        if (type === COSMJS_WALLET_TYPE) {
          // For CosmJS wallets, simulate to get gas estimation
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
            fee: this.buildFee(100000000), // Use high gas limit for simulation
            simulate: true,
          });

          if (!simulationResult.success) {
            // Return the simulation error
            return simulationResult;
          }

          // Extract gas used and add buffer
          const gasUsed = parseInt(simulationResult.rawSendMsgsResponse?.gasUsed || "0");
          finalGasLimit = gasUsed > 0 ? Math.round(gasUsed * 1.5) : 100000000;
        } else {
          // For Keplr and other extension wallets, use a reasonable default
          // They will handle gas estimation themselves
          finalGasLimit = 100000000;
        }
      }

      const fee = this.buildFee(finalGasLimit);

      return runScript({
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
    },

    // New wrapper for signing arbitrary data (calls signData in dysonTxUtils)
    async signArbitraryData({ data }) {
      const { walletInstance, address, type } = this.getWallet();
      const apiUrl = this.restUrl;
      // Create a Tx in normal JSON shape:
      let transaction = {
        body: {
          messages: [
            {
              "@type": "/offchain.MsgSignArbitraryData",
              app_domain: "dysond",
              signer: address,
              data: data, // e.g., "hi world\n"
            },
          ],
          memo: "",
          timeout_height: "0",
          unordered: false,
          timeout_timestamp: "0001-01-01T00:00:00Z",
          extension_options: [],
          non_critical_extension_options: [],
        },
        auth_info: {
          signer_infos: [],
          fee: {
            amount: [],
            gas_limit: "0",
            payer: "",
            granter: "",
          },
          tip: null,
        },
        signatures: [],
      };
      const [{ pubkey }] = await this.activeWalletInstance.getAccounts();
      transaction.auth_info.signer_infos = [
        {
          public_key: {
            "@type": "/cosmos.crypto.secp256k1.PubKey",
            key: toBase64(pubkey), // base64
          },
          mode_info: {
            single: { mode: "SIGN_MODE_DIRECT" },
          },
          sequence: "0",
        },
      ];
      console.log("transaction", transaction);
      const encodeRes = await fetch(`${apiUrl}/cosmos/tx/v1beta1/encode`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tx: transaction }),
      });
      if (!encodeRes.ok) {
        throw new Error(`Failed to encode: ${await encodeRes.text()}`);
      }
      const encodedTx = await encodeRes.json();
      console.log("encodedTx", encodedTx);


      const tx = TxRaw.decode(fromBase64(encodedTx.tx_bytes));
      console.log("tx", tx);
      const chainId = ""; // or "" if the Go code uses empty
      const accountNumber = "0";

      const signDoc = makeSignDoc(tx.bodyBytes, tx.authInfoBytes, chainId, accountNumber);
      const debugSignBytes = makeSignBytes(signDoc);
      console.log("debugSignBytes", toBase64(debugSignBytes));
      const sig = await walletInstance.signDirect(address, signDoc);
      console.log("sig", sig);
      transaction.signatures = [sig.signature.signature];
      return transaction;

      // signData returns the final signed Tx as base64
      /*
      return signData({
        apiUrl: this.restUrl,
        wallet: walletInstance,
        walletType: type,
        address,
        data,
      });
      */
    },

    // Load denom metadata from the chain
    async loadDenomMetadata() {
      if (this.denomMetadatas.length > 0) {
        return;
      }
      const url = `${this.restUrl}/cosmos/bank/v1beta1/denoms_metadata?pagination.limit=1000`;
      const resp = await fetch(url);
      if (!resp.ok) {
        console.warn(`Failed to load denom metadata: ${resp.status} ${resp.statusText}`);
        return;
      }
      const json = await resp.json();
      if (json.metadatas.length < 1) {
        throw new Error('No denom metadata found');
      }
      this.denomMetadatas = json.metadatas;
    },

    // Normalize a coin with denom metadata
    normalizeCoin({ amount, denom }) {
      // Assume amount is a string to handle large numbers precisely
      const inputAmount = BigInt(amount);

      // Find the metadata and input unit
      let metadata = null;
      let inputUnit = null;
      for (const md of this.denomMetadatas) {
        for (const unit of md.denom_units) {
          console.log('unit', unit);
          if (unit.denom === denom || unit.aliases.includes(denom)) {
            metadata = md;
            inputUnit = unit;
            break;
          }
        }
        if (metadata) break;
      }

      if (!metadata) {
        throw new Error(`Denom metadata not found for ${denom}`);
      }

      const inputExponent = inputUnit.exponent;
      const baseDenom = metadata.base;
      const baseAmount = inputAmount * (10n ** BigInt(inputExponent));

      // Find display unit
      const displayDenom = metadata.display;
      const displayUnit = metadata.denom_units.find(u => u.denom === displayDenom || u.aliases.includes(displayDenom));
      if (!displayUnit) {
        throw new Error(`Display unit not found for ${displayDenom}`);
      }

      const displayExponent = displayUnit.exponent;
      const displayAmountBig = baseAmount / (10n ** BigInt(displayExponent));
      // For simplicity, assume integer division; in production, handle fractional with Decimal.js or similar
      const displayAmount = displayAmountBig.toString(); // Return as string to preserve precision

      return {
        base: {
          amount: baseAmount.toString(),
          denom: baseDenom
        },
        display: {
          amount: displayAmount,
          denom: displayDenom
        },
        metadata: metadata
      };
    },
  });
}); 