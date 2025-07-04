document.addEventListener("alpine:init", () => {
  Alpine.data("messagesStore", () => ({
    messages: [],
    message: "",
    sponsorAmount: 0,
    deletingMessageId: null,
    submitting: false,
    submitError: null,

    init() {
      this.fetchMessages();
    },

    // Get the current script address from an embedded JSON <script> tag
    getScriptAddress() {
      // Expect a tag like:
      // <script type="application/json" class="messages-config">{ "scriptAddress": "dys1..." }</script>
      const cfgTag = document.querySelector('script.messages-config[type="application/json"]');
      if (cfgTag) {
        try {
          const cfg = JSON.parse(cfgTag.textContent.trim());
          if (cfg && typeof cfg.scriptAddress === 'string' && cfg.scriptAddress.trim() !== '') {
            return cfg.scriptAddress.trim();
          }
        } catch (e) {
          console.error('Invalid messages-config JSON', e);
        }
      }
      // Fallback: empty string if not provided
      return '';
    },

    async fetchMessages() {
      try {
        const scriptAddress = this.getScriptAddress();
        const apiUrl = window.location.origin; // Use current domain
        const fetchUrl = `${apiUrl}/dysonprotocol/storage/v1/storage_list?owner=${scriptAddress}&index_prefix=messages&pagination.limit=100&pagination.reverse=true`;
        console.log("Fetching messages from:", fetchUrl);
        
        const resp = await fetch(fetchUrl);
        console.log("Fetch response status:", resp.status);
        
        const data = await resp.json();
        console.log("Raw fetch data:", data);
        
        if (data?.entries) {
          this.messages = data.entries.map((s) => ({
            ...s,
            data: JSON.parse(s.data),
          }));
          console.log("Parsed messages:", this.messages);
        } else {
          this.messages = [];
          console.log("No entries found in response");
        }
      } catch (error) {
        console.log("Error fetching messages:", error?.message || error);
        this.messages = [];
      }
    },

    async submitMessage() {
      this.submitting = true;
      this.submitError = null;

      try {
        console.log("submitMessage called");

        const scriptAddress = this.getScriptAddress();
        const walletStore = Alpine.store("walletStore");

        if (!walletStore || !walletStore.runDysonScript) {
          this.submitError = "Wallet connection not found. Please connect your wallet first.";
          return;
        }

        let attachedMsg = [];
        if (this.sponsorAmount && this.sponsorAmount > 0) {
          const bankSendMsg = {
            "@type": "/cosmos.bank.v1beta1.MsgSend",
            "from_address": walletStore.activeWalletMeta.address,
            "to_address": scriptAddress,
            "amount": [{ "denom": "udys", "amount": this.sponsorAmount.toString() }]
          };
          attachedMsg.push(bankSendMsg);
        }

        let finalGasLimit = 200000;

        if (walletStore.activeWalletMeta?.type === "cosmjs") {
          console.log("Simulating transaction for gas estimation...");
          const simulationResult = await walletStore.runDysonScript({
            scriptAddress: scriptAddress,
            functionName: "save_message",
            kwargs: JSON.stringify({ message: this.message }),
            attachedMsg: attachedMsg,
            gasLimit: finalGasLimit,
            simulate: true
          });

          if (simulationResult.success && simulationResult.rawSendMsgsResponse?.gasUsed) {
            const simulatedGas = parseInt(simulationResult.rawSendMsgsResponse.gasUsed, 10);
            finalGasLimit = Math.ceil(simulatedGas * 1.5);
            console.log(`Gas limit set to ${finalGasLimit} after simulation.`);
          } else if (!simulationResult.success) {
            const error = simulationResult.rawSendMsgsResponse?.rawLog || "Simulation failed.";
            this.submitError = `Transaction would fail: ${error}`;
            console.error("Simulation Error:", error);
            return;
          }
        }

        console.log("Executing transaction...");
        const result = await walletStore.runDysonScript({
          scriptAddress: scriptAddress,
          functionName: "save_message",
          kwargs: JSON.stringify({ message: this.message }),
          attachedMsg: attachedMsg,
          gasLimit: finalGasLimit,
          simulate: false
        });

        if (result.success) {
          console.log("Transaction successful:", result);
          this.message = "";
          this.sponsorAmount = 0;
          await this.fetchMessages();
          const newMessageIndex = result?.scriptResponse?.result;
          if (newMessageIndex) {
            location.hash = newMessageIndex;
          }
        } else {
          const error = result.scriptResponse?.error || result.rawSendMsgsResponse?.rawLog || "Transaction failed.";
          this.submitError = `Transaction failed: ${error}`;
          console.error("Execution Error:", error);
        }

      } catch (error) {
        this.submitError = error?.message || "An unexpected error occurred.";
        console.error("submitMessage error:", error);
      } finally {
        this.submitting = false;
      }
    },

    async deleteMessage(messageId) {
      try {
        console.log("Deleting message:", messageId);
        
        // Show confirmation dialog
        if (!confirm("Are you sure you want to delete this message? This action cannot be undone.")) {
          console.log("Delete cancelled by user");
          return;
        }
        
        // Set loading state
        this.deletingMessageId = messageId;
        
        const scriptAddress = this.getScriptAddress();
        const walletStore = Alpine.store("walletStore");
        
        if (!walletStore || !walletStore.runDysonScript) {
          console.log("Error: Wallet store or runDysonScript not found");
          return;
        }

        let finalGasLimit = 200000; // Default gas limit

        // If using CosmJS wallet, simulate first to get gas estimate
        if (walletStore.activeWalletMeta?.type === "cosmjs") {
          console.log("CosmJS wallet detected, simulating delete transaction first...");
          
          const simulationResult = await walletStore.runDysonScript({
            scriptAddress: scriptAddress,
            functionName: "delete_message",
            kwargs: JSON.stringify({ message_id: messageId }),
            gasLimit: finalGasLimit,
            simulate: true
          });
          
          console.log("Delete simulation result:", simulationResult);
          
          if (simulationResult.success && simulationResult.rawSendMsgsResponse?.gasUsed) {
            const simulatedGas = parseInt(simulationResult.rawSendMsgsResponse.gasUsed, 10);
            finalGasLimit = Math.ceil(simulatedGas * 1.5);
            console.log(`Delete gas simulation: used ${simulatedGas}, setting limit to ${finalGasLimit}`);
          } else {
            console.log("Delete simulation failed or no gas info, using default gas limit");
            if (!simulationResult.success) {
              console.log("Delete simulation error:", simulationResult.rawSendMsgsResponse?.rawLog);
              this.deletingMessageId = null;
              return;
            }
          }
        }
        
        console.log("Calling delete_message with:", JSON.stringify({
          scriptAddress: scriptAddress,
          functionName: "delete_message", 
          kwargs: JSON.stringify({ message_id: messageId }),
          gasLimit: finalGasLimit,
        }));
        
        const result = await walletStore.runDysonScript({
          scriptAddress: scriptAddress,
          functionName: "delete_message",
          kwargs: JSON.stringify({ message_id: messageId }),
          gasLimit: finalGasLimit,
          simulate: false
        });
        
        console.log("deleteMessage result:", JSON.stringify(result, null, 2));

        if (result.success) {
          console.log("Message deleted successfully");
          // Refresh the messages list
          await this.fetchMessages();
        } else {
          console.log("Delete failed:", result);
          // You could add user-friendly error handling here
        }

      } catch (error) {
        console.log("deleteMessage error:", error?.message || error);
      } finally {
        // Clear loading state
        this.deletingMessageId = null;
      }
    },
  }));
}); 