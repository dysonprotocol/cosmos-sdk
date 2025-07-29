function createNewPostData() {
  return {
    content: Alpine.$persist(''),
    previewHtml: '',
    error: '',
    isSubmitting: false,
    
    init() {
      this.updatePreview();
      
      // Clear errors when form fields change
      this.$watch('content', () => {
        this.clearError();
      });
    },
    
    // Get the current author identity from wallet store
    get currentAuthor() {
      try {
        return this.$store.walletStore.getAuthorIdentity();
      } catch (error) {
        return '';
      }
    },
    
    clearError() {
      if (this.error) {
        this.error = '';
      }
    },
    
    debounce(func, wait) {
      let timeout;
      return function(...args) {
        clearTimeout(timeout);
        timeout = setTimeout(() => func.apply(this, args), wait);
      };
    },
    
    embedPosts(contentText, depth) {
      //"(?:^\n*?|\n+?)/(\d+)(#[^\s]+)?(?:\n*?$|\n+?)"
      return contentText.replace(/(?:^\n*?|\n+?)\/(\d+)(#[^\s]+)?(?:\n*?$|\n+?)/gm, (match, p1, p2) => {
        return `
          <div
            hx-trigger="load"
            hx-get="/${p1}?depth=${depth}"
            hx-select="article"
            hx-disinherit="hx-select"
            hx-swap="innerHTML ignoreTitle:true"
            hx-target="this"
            data-fragment="${p2 || ''}"
          >
            Loading: ${p1} ...
          </div>
        `;
      });
    },
    
    updatePreview() {
      console.log('updatePreview', this.content);
      const escaped = this.content.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
      this.previewHtml = this.embedPosts(escaped, 1);
      this.$nextTick(() => {
        const preview = this.$refs.preview;
        console.log('preview', preview);
        if (preview) {
          preview.classList.add('markdown'); // the markdown class is used to render the markdown and is removed after rendering
          renderMarkdownAndHighlight(preview).then(() => {
            console.log('htmx.process(preview)', preview);
            if (typeof htmx !== 'undefined') {
              htmx.process(preview);
            }
          }).catch(error => {
            console.error('Error rendering markdown:', error);
          });
        }
      });
    },
    
    get hasAccount() {
      return !!this.$store.walletStore.activeWalletMeta;
    },
    
    async postContent() {
      try {
        this.isSubmitting = true;
        this.error = '';
        
        // Validate we have an author identity
        if (!this.currentAuthor) {
          throw new Error('No author identity selected. Please connect your wallet and select an identity.');
        }
        
        const scriptAddress = window.scriptAddress; // Set in base.html
        const result = await this.$store.walletStore.runDysonScript({
          scriptAddress,
          functionName: 'publish_post',
          kwargs: JSON.stringify({ content: this.content, author: this.currentAuthor }),
          gasLimit: 'auto'
        });
        
        console.log('result', result);
        
        if (result.success) {
          const postId = result.scriptResponse.result;
          this.content = '';
          
          // Use direct navigation for maximum reliability in tests
          console.log('Navigating to post:', postId);
          window.location.href = `/${postId}`;
        } else {
          let errorMsg = 'Transaction failed';
          if (result.scriptResponse?.exception?.msg) {
            errorMsg = `Transaction failed: [${result.scriptResponse?.exception?.class}] ${result.scriptResponse?.exception?.msg}`;
          } else if (result.rawSendMsgsResponse?.rawLog) {
            errorMsg = `Transaction failed: ${result.rawSendMsgsResponse?.rawLog}`;
          }
          this.error = errorMsg;
          console.error('postContent failed:', errorMsg);
        }
      } catch (e) {
        this.error = `Post Error: ${e.message}`;
        console.error('postContent error:', e);
      } finally {
        this.isSubmitting = false;
      }
    }
  };
}

// Make it available globally
window.createNewPostData = createNewPostData; 