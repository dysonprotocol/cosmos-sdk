import { DirectSecp256k1HdWallet, makeSignDoc, makeSignBytes, executeKdf, extractKdfConfiguration } from "@cosmjs/proto-signing";
import { getChainInfo, sendMsgs, runScript, signData, encodeAndDecodeTx } from "./dysonTxUtils.js";
import { Tx, TxBody, AuthInfo, TxRaw } from "cosmjs-types/cosmos/tx/v1beta1/tx.js";
import { toBase64, fromBase64 } from "@cosmjs/encoding";

const DEFAULT_CHAIN_INFO = {
  restUrl: window.location.origin, // Use current domain instead of hardcoded localhost
  bech32Prefix: "dys", // same as chain prefix
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

    // Call this somewhere (e.g. <body x-init="$store.walletStore.init()">
    async init() {      
      ///====
      console.log("walletStore init");
      ///====

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
          }
        } else if (this.activeWalletMeta.type === COSMJS_WALLET_TYPE) {
          const walletData = this.localCosmJsWallets.find((w) => w.name === this.activeWalletMeta.name);
          if (walletData && walletData._pass && walletData._pass.trim() !== "") {
            try {
              await this.connectNamedCosmJsWallet(walletData.name, walletData._pass);
            } catch (error) {
              console.error("Auto reconnection failed for wallet", walletData.name, error);
            }
          }
        }
      }
      // TODO: remove this
      if (this.localCosmJsWallets.length === 0) {
        // TODO: remove this
        await this.importNamedCosmJsWallet("alice",  "public feature teach face federal matrix throw legend bridge brass diary beach typical doll evoke weapon among crane regret trust enact swarm brother outside", "password");
        await this.importNamedCosmJsWallet("bob",  "aerobic creek copper rice disagree become brass elegant century elegant apology position infant saddle metal brain gain loud alpha add boy balance truth cherry", "password");
        await this.importNamedCosmJsWallet("charlie",  "blind people aim sheriff awkward once wish above agree journey unknown uncover swap damage bamboo volume clay error weekend fiber acquire diamond vintage lake", "password");
      
        await this.connectNamedCosmJsWallet("alice", "password");
      }

      // Mark as loaded
      this.isLoading = false;
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
          bech32PrefixAccAddr: "dys",
          bech32PrefixAccPub: "dyspub",
          bech32PrefixValAddr: "dysvaloper",
          bech32PrefixValPub: "dysvaloperpub",
          bech32PrefixConsAddr: "dysvalcons",
          bech32PrefixConsPub: "dysvalconspub",
        },
        currencies: [
          {
            coinDenom: "DYS",
            coinMinimalDenom: "dys",
            coinDecimals: 0,
          },
        ],
        feeCurrencies: [
          {
            coinDenom: "DYS",
            coinMinimalDenom: "dys",
            coinDecimals: 0,
          },
        ],
        stakeCurrency: {
          coinDenom: "DYS",
          coinMinimalDenom: "dys",
          coinDecimals: 0,
        },
        gasPriceStep: {
          low: 0.0,
          average: 0.00001,
          high: 0.00002,
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
            denom: "dys",
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

    // Extension methods
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
    },

    disconnectWallet() {
      this.activeWalletMeta = null;
      this.activeWalletInstance = null;
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
      gasLimit = 200000,
      simulate = false,
    }) {
      const { walletInstance, address, type } = this.getWallet();
      if (!scriptAddress) {
        throw new Error("scriptAddress is required.");
      }
      const fee = this.buildFee(gasLimit);

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
  });
}); 