function createPostTopicsData(postId) {
  return {
    tagName: '',
    amount: Alpine.$persist(0),
    contributor: Alpine.$persist(''),
    isSubmitting: false,
    error: '',
    
    get isFormValid() {
      // Tag name is required and must be non-empty after trimming
      if (!this.tagName.trim()) {
        return false;
      }
      
      // Amount validation: if provided, must be a valid positive number
      if (this.amount !== '' && this.amount !== null && this.amount !== undefined) {
        const numAmount = parseFloat(this.amount);
        if (isNaN(numAmount) || numAmount < 0) {
          return false;
        }
      }
      
      return true;
    },
    
    async addTag() {
      if (!this.tagName.trim()) return;
      
      try {
        this.isSubmitting = true;
        this.error = '';
        const scriptAddress = window.scriptAddress; // Set in base.html
        
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
          functionName: 'rate_tag',
          kwargs: JSON.stringify({ 
            tag_name: this.tagName, 
            post_id: postId, 
            rate: 'up', 
            contributor: this.contributor 
          }),
          attachedMsg,
          gasLimit: "auto"
        });
        
        console.log('rated tag result:', result);
        if (result.success) {
          location = `/${postId}/topics/${this.tagName}`;
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