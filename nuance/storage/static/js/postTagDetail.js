function createPostTagDetailData(postId, tagName, earliestClaimTime, up, down, earned, bestRating, postAuthor) {
  return {
    tagName: tagName,
    postId: postId,
    availableRewards: '',
    earnedRewards: '',
    timeLeft: 0,
    earliestClaimTime: earliestClaimTime,
    author: postAuthor || null,
    amount: Alpine.$persist(1), // Default to 1 DYS
    error: '',
    isSubmitting: false,
    isClaiming: false,
    
    // Get the current author identity from wallet store
    get currentAuthor() {
      try {
        return this.$store.walletStore.getAuthorIdentity();
      } catch (error) {
        return '';
      }
    },
    
    // Validate amount field
    get isAmountValid() {
      if (this.amount === '' || this.amount === null || this.amount === undefined) {
        return false;
      }
      const numAmount = parseFloat(this.amount);
      return !isNaN(numAmount) && numAmount > 0;
    },
    
    init() {
      this.calculateAvailableRewards();
      this.normalizeEarnedRewards(earned);
      this.startCountdown();
      this.updateButtonStates();
      
      // Listen for wallet changes
      this.$watch('$store.walletStore.activeWalletMeta', () => {
        this.updateButtonStates();
      });
      
      // Clear errors when form fields change
      this.$watch('tagName', () => {
        this.clearError();
      });
      
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
      return this.hasClaimableAmount && this.isAuthor && !this.timeLeft;
    },
    
    get isAuthor() {
      if (!this.author || !this.$store.walletStore.activeWalletMeta) return false;
      
      // Compare both the current author identity and wallet address
      const currentAuthorIdentity = this.currentAuthor;
      const walletAddress = this.$store.walletStore.activeWalletMeta.address;
      
      // The post author matches if it equals either the selected author identity or wallet address
      return this.author === currentAuthorIdentity || this.author === walletAddress;
    },
    
    async calculateAvailableRewards() {
      try {
        console.log('calculateAvailableRewards', this.postId, this.tagName);
        const [rawTagRewards, postPosition, post] = await Promise.all([
          getData(getTagRewardsIndex(this.tagName)),
          getPostPositionInHotPosts(this.postId, this.tagName),
          getData('posts/' + formatId(this.postId)),
        ]);
        
        // Parse the JSON data field from storage response (same fix as reply rewards)
        const tagRewards = rawTagRewards?.entry ? JSON.parse(rawTagRewards.entry.data) : rawTagRewards;
        
        // Handle null data gracefully
        if (!post) {
          console.warn('Post data not found for ID:', this.postId);
          this.availableRewards = 0;
          return;
        }
        
        if (!tagRewards) {
          console.warn('Tag rewards not found for tag:', this.tagName);
          this.availableRewards = 0;
          return;
        }
        
        // Only set author if not already provided (for backwards compatibility)
        if (!this.author && post.author) {
          this.author = post.author;
        }
        console.log('tagName', this.tagName);
        console.log('postId', this.postId);

        if (postPosition === -1) {
          this.availableRewards = 0;
        } else {
          // Handle case where tagRewards.available might not exist
          // Use udys (micro) denomination since rewards are stored in base units
          const availableUdys = tagRewards.available?.udys || 0;
          const rawRewards = Math.floor(
            availableUdys * (1 / 2) ** (1 + postPosition),
          );
          
          // Normalize the rewards amount using wallet store
          Alpine.store('walletStore').loadDenomMetadata().then(() => {
            const normalizedRewards = Alpine.store('walletStore').normalizeCoin({
              amount: String(rawRewards),
              denom: 'udys'
            });
            this.availableRewards = parseFloat(normalizedRewards.display.amount);
          });
        }
        console.log('postPosition', postPosition);
        console.log('tagRewards', tagRewards);
        console.log('availableRewards', this.availableRewards);
      } catch (error) {
        console.error('Error calculating rewards:', error);
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
    
    async claim(event) {
      event.preventDefault();
      
      try {
        this.isClaiming = true;
        this.error = '';
        
        const scriptAddress = window.scriptAddress;
        const postPosition = await getPostPositionInHotPosts(this.postId, this.tagName);
        if (postPosition === -1) return;
        
        const result = await Alpine.store('walletStore').runDysonScript({
          scriptAddress,
          functionName: 'claim_tag_rewards',
          args: JSON.stringify([this.tagName, postPosition]),
          gasLimit: "auto"
        });
        
        if (result.success) {
          // Navigate to refresh the tag detail page
          location.href = `/${this.postId}/topics/${this.tagName}`;
        } else {
          let errorMsg = 'Transaction failed';
          if (result.scriptResponse?.exception?.msg) {
            errorMsg = `Transaction failed: [${result.scriptResponse?.exception?.class}] ${result.scriptResponse?.exception?.msg}`;
          } else if (result.rawSendMsgsResponse?.rawLog) {
            errorMsg = `Transaction failed: ${result.rawSendMsgsResponse?.rawLog}`;
          }
          this.error = errorMsg;
          console.error('claim failed:', errorMsg);
        }
      } catch (e) {
        this.error = `Claim Error: ${e.message}`;
        console.error('claim error:', e);
      } finally {
        this.isClaiming = false;
      }
    },
    
    async rateTag(rate, event) {
      event.preventDefault();
      
      try {
        this.isSubmitting = true;
        this.error = '';
        
        const scriptAddress = window.scriptAddress;
        
        const attachedMsg = [];
        // Convert DYS to udys (1 DYS = 1,000,000 udys)
        const amountInUdys = Math.round(parseFloat(this.amount) * 1000000);
        if (amountInUdys > 0) {
          attachedMsg.push({
            '@type': '/cosmos.bank.v1beta1.MsgSend',
            from_address: Alpine.store('walletStore').getWallet().address,
            to_address: scriptAddress,
            amount: [{ denom: 'udys', amount: String(amountInUdys) }]
          });
        }
        
        const result = await Alpine.store('walletStore').runDysonScript({
          scriptAddress,
          functionName: 'rate_tag',
          kwargs: JSON.stringify({ 
            tag_name: this.tagName, 
            post_id: this.postId, 
            rate, 
            contributor: this.currentAuthor 
          }),
          attachedMsg,
          gasLimit: "auto"
        });
        
        if (result.success) {
          // Navigate to refresh the tag detail page
          location.href = `/${this.postId}/topics/${this.tagName}`;
        } else {
          let errorMsg = 'Transaction failed';
          if (result.scriptResponse?.exception?.msg) {
            errorMsg = `Transaction failed: [${result.scriptResponse?.exception?.class}] ${result.scriptResponse?.exception?.msg}`;
          } else if (result.rawSendMsgsResponse?.rawLog) {
            errorMsg = `Transaction failed: ${result.rawSendMsgsResponse?.rawLog}`;
          }
          this.error = errorMsg;
          console.error('rateTag failed:', errorMsg);
        }
      } catch (e) {
        this.error = `Rate Error: ${e.message}`;
        console.error('rateTag error:', e);
      } finally {
        this.isSubmitting = false;
      }
    }
  };
}

// Make it available globally
window.createPostTagDetailData = createPostTagDetailData; 