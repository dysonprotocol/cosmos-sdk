function createPostTopicsData(postId) {
  return {
    tagName: '',
    isSubmitting: false,
    error: '',
    
    // Get the current author identity from wallet store
    get currentAuthor() {
      try {
        return this.$store.walletStore.getAuthorIdentity();
      } catch (error) {
        return '';
      }
    },
    
    get isFormValid() {
      // Tag name is required and must be non-empty after trimming
      return this.tagName.trim() !== '';
    },
    
    async addTag() {
      if (!this.tagName.trim()) return;
      
      try {
        this.isSubmitting = true;
        this.error = '';
        const scriptAddress = window.scriptAddress; // Set in base.html
        
        const attachedMsg = [];
        // Hardcoded amount: 1 udys
        attachedMsg.push({
            '@type': '/cosmos.bank.v1beta1.MsgSend',
            from_address: Alpine.store('walletStore').getWallet().address,
            to_address: scriptAddress,
            amount: [{ denom: 'udys', amount: '1' }]
        });
        
        const result = await Alpine.store('walletStore').runDysonScript({
          scriptAddress,
          functionName: 'rate_tag',
          kwargs: JSON.stringify({ 
            tag_name: this.tagName, 
            post_id: postId, 
            rate: 'up', 
            contributor: this.currentAuthor 
          }),
          attachedMsg,
          gasLimit: "auto"
        });
        
        console.log('rated tag result:', result);
        if (result.success) {
          htmx.ajax('GET', `/${postId}/topics/${this.tagName}`);
        } else {
          let errorMsg = 'Transaction failed';
          if (result.scriptResponse?.exception?.msg) {
            errorMsg = `Transaction failed: [${result.scriptResponse?.exception?.class}] ${result.scriptResponse?.exception?.msg}`;
          } else if (result.rawSendMsgsResponse?.rawLog) {
            errorMsg = `Transaction failed: ${result.rawSendMsgsResponse?.rawLog}`;
          }
          this.error = errorMsg;
          console.error('rated tag failed:', errorMsg);
        }
      } catch (e) {
        this.error = `JavaScript Error: ${e.message}`;
        console.error('addTag error:', e);
      } finally {
        this.isSubmitting = false;
      }
    }
  };
}

// Make it available globally
window.createPostTopicsData = createPostTopicsData; 