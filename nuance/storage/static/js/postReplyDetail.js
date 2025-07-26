function createPostReplyDetailData(postId, replyPostId, earliestClaimTime, up, down, earned, bestRating) {
  return {
    postId: postId,
    replyPostId: replyPostId,
    availableRewards: 0,
    earnedRewards: '',
    timeLeft: 0,
    earliestClaimTime: earliestClaimTime,
    amount: Alpine.$persist(0),
    error: '',
    isSubmitting: false,
    isClaiming: false,
    showDetails: false,
    
    init() {
      console.log("PostReplyDetail init() called for post", this.postId, "reply", this.replyPostId);
      this.normalizeEarnedRewards(earned);
      this.startCountdown();
      this.updateButtonStates();
      
      // Calculate rewards after a short delay to ensure everything is loaded
      setTimeout(() => {
        console.log("Calling calculateReplyAvailableRewards after timeout");
        this.calculateReplyAvailableRewards();
      }, 100);
      
      // Listen for wallet changes
      this.$watch('$store.walletStore.activeWalletMeta', () => {
        this.updateButtonStates();
      });
      
      // Clear errors when form fields change
      this.$watch('amount', () => {
        this.clearError();
      });
    },
    
    clearError() {
      if (this.error) {
        this.error = '';
      }
    },

    async normalizeEarnedRewards(earnedUdys) {
      try {
        // Normalize the earned amount using wallet store
        Alpine.store('walletStore').loadDenomMetadata().then(() => {
          const normalizedEarned = Alpine.store('walletStore').normalizeCoin({
            amount: String(earnedUdys),
            denom: 'udys'
          });
          this.earnedRewards = parseFloat(normalizedEarned.display.amount);
        }).catch(() => {
          // Fallback to manual conversion if denom metadata fails
          this.earnedRewards = earnedUdys / 1000000;
        });
      } catch (error) {
        console.error('Error normalizing earned rewards:', error);
        // Fallback to manual conversion
        this.earnedRewards = earnedUdys / 1000000;
      }
    },
    
    get hasClaimableAmount() {
      return this.availableRewards >= 1;
    },
    
    get hasAccount() {
      return !!this.$store.walletStore.activeWalletMeta;
    },
    
    get canClaim() {
      return this.hasClaimableAmount && this.hasAccount && !this.timeLeft;
    },
    
    async calculateReplyAvailableRewards() {
      console.log("=== calculateReplyAvailableRewards() CALLED ===");
      try {
        const replyRewardsIndex = getReplyRewardsIndex(this.postId);
        console.log("Looking for reply rewards at index:", replyRewardsIndex);
        
        const [rawReplyRewards, replyPosition] = await Promise.all([
          getData(replyRewardsIndex),
          getPostPositionInHotReplies(this.postId, this.replyPostId),
        ]);
        
        // Parse the JSON data field from storage response
        const replyRewards = rawReplyRewards.entry ? JSON.parse(rawReplyRewards.entry.data) : rawReplyRewards;
        
        console.log("replyPostId", this.replyPostId);
        console.log("postId", this.postId);
        console.log("replyPosition", replyPosition);
        console.log("replyRewards", replyRewards);
        
        if (replyPosition === -1) {
          console.log("Reply not found in hot list, setting rewards to 0");
          this.availableRewards = 0;
        } else {
          const availableUdys = replyRewards?.available?.udys || 0;
          console.log("Available DYS in rewards pool:", availableUdys / 1000000);
          console.log("Raw udys amount:", availableUdys);
          
          const rewardMultiplier = (1 / 2) ** (1 + replyPosition);
          console.log("Reward multiplier for position", replyPosition, ":", rewardMultiplier);
          
          const rawRewards = Math.floor(availableUdys * rewardMultiplier);
          console.log("Raw rewards calculation:", availableUdys, "*", rewardMultiplier, "=", rawRewards);
          
          // Normalize the rewards amount using wallet store
          Alpine.store('walletStore').loadDenomMetadata().then(() => {
            const normalizedRewards = Alpine.store('walletStore').normalizeCoin({
              amount: String(rawRewards),
              denom: 'udys'
            });
            this.availableRewards = parseFloat(normalizedRewards.display.amount);
            console.log("Final available rewards:", this.availableRewards, "DYS");
          });
        }
        
      } catch (error) {
        console.error('Error calculating reply rewards:', error);
        console.log("Error details:", error);
        this.availableRewards = 0;
      }
    },
    
    updateCountdown() {
      const now = Math.floor(Date.now() / 1000);
      this.timeLeft = Math.max(0, this.earliestClaimTime - now);
    },
    
    startCountdown() {
      this.updateCountdown();
      setInterval(() => {
        this.updateCountdown();
      }, 1000);
    },
    
    get claimButtonText() {
      if (this.timeLeft <= 0) {
        return 'Claim now';
      } else {
        const hours = Math.floor((this.timeLeft % (60 * 60 * 24)) / (60 * 60));
        const minutes = Math.floor((this.timeLeft % (60 * 60)) / 60);
        const seconds = Math.floor(this.timeLeft % 60);
        const timeDisplay = hours > 0 ? hours + 'h' : minutes > 0 ? minutes + 'm' : seconds + 's';
        return 'Claim in ' + timeDisplay;
      }
    },
    
    updateButtonStates() {
      // This will be handled reactively by Alpine
    },
    
    async claimReply(event) {
      event.preventDefault();
      
      try {
        this.isClaiming = true;
        this.error = '';
        
        console.log("claimReply", this.postId, this.replyPostId, event);
        
        const scriptAddress = window.scriptAddress;
        const postPosition = await getPostPositionInHotReplies(this.postId, this.replyPostId);
        if (postPosition === -1) return;
        
        const result = await Alpine.store('walletStore').runDysonScript({
          scriptAddress,
          functionName: 'claim_reply_rewards',
          args: JSON.stringify([this.postId, postPosition]),
          gasLimit: "auto"
        });

        if (result.success) {
          htmx.ajax("GET", "/" + this.postId + "/replies/" + this.replyPostId , {
            target: htmx.closest(event.target, "form"),
            swap: "outerHTML",
            select: "form",
          });
        } else {
          let errorMsg = 'Transaction failed';
          if (result.scriptResponse?.exception?.msg) {
            errorMsg = `Transaction failed: [${result.scriptResponse?.exception?.class}] ${result.scriptResponse?.exception?.msg}`;
          } else if (result.rawSendMsgsResponse?.rawLog) {
            errorMsg = `Transaction failed: ${result.rawSendMsgsResponse?.rawLog}`;
          }
          this.error = errorMsg;
          console.error('claimReply failed:', errorMsg);
        }
      } catch (e) {
        this.error = `Claim Error: ${e.message}`;
        console.error('claimReply error:', e);
      } finally {
        this.isClaiming = false;
      }
    },
    
    async rateReply(rate, event) {
      event.preventDefault();
      
      try {
        this.isSubmitting = true;
        this.error = '';
        
        const scriptAddress = window.scriptAddress;
        
        const attachedMsg = [];
        if (this.amount) {
          const amountInUdys = Math.round(parseFloat(this.amount) * 1000000);
          if (amountInUdys > 0) {
            attachedMsg.push({
              '@type': '/cosmos.bank.v1beta1.MsgSend',
              from_address: Alpine.store('walletStore').getWallet().address,
              to_address: scriptAddress,
              amount: [{ denom: 'udys', amount: String(amountInUdys) }]
            });
          }
        }
        
        const result = await Alpine.store('walletStore').runDysonScript({
          scriptAddress,
          functionName: 'rate_reply',
          kwargs: JSON.stringify({ 
            reply_post_id: this.replyPostId, 
            post_id: this.postId, 
            rate 
          }),
          attachedMsg,
          gasLimit: "auto"
        });
        console.log("rate_reply result", result);
        if (result.success) {
          console.log("rate_reply", rate, this.postId, this.replyPostId);
          
          htmx.ajax("GET", "/" + this.postId + "/replies/" + this.replyPostId + "?cacheBuset=" + result.rawSendMsgsResponse.raw.tx_response.txhash, {
            target: htmx.closest(event.target, ".reply-detail-container"),
            swap: "outerHTML",
            select: ".reply-detail-container",
          });
        } else {
          let errorMsg = 'Transaction failed';
          if (result.scriptResponse?.exception?.msg) {
            errorMsg = `Transaction failed: [${result.scriptResponse?.exception?.class}] ${result.scriptResponse?.exception?.msg}`;
          } else if (result.rawSendMsgsResponse?.rawLog) {
            errorMsg = `Transaction failed: ${result.rawSendMsgsResponse?.rawLog}`;
          }
          this.error = errorMsg;
          console.error('rateReply failed:', errorMsg);
        }
      } catch (e) {
        this.error = `Rate Error: ${e.message}`;
        console.error("rateReply error:", e);
      } finally {
        this.isSubmitting = false;
      }
    }
  };
}

// Make it available globally
window.createPostReplyDetailData = createPostReplyDetailData; 