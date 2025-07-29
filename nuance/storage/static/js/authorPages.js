/**
 * Author Pages JavaScript Module
 * Handles functionality for author profile pages, custom pages, and related features
 */

/**
 * Shared utility to get author identity with fallback logic
 */
function getAuthorIdentity() {
  try {
    return Alpine.store('walletStore').getAuthorIdentity();
  } catch (error) {
    console.error('Failed to get author identity from wallet store:', error);
    
    // Fallback: try to get from page context or URL
    const authorElement = document.querySelector('[data-author-name]');
    if (authorElement) {
      return authorElement.getAttribute('data-author-name');
    }
    
    const pathMatch = window.location.pathname.match(/\/edit-author\/([^/]+)/);
    return pathMatch ? pathMatch[1] : '';
  }
}

/**
 * Alpine.js component for managing custom pages
 */
export function customPagesManager() {
  return {
    pages: [],
    newPage: {
      path: '',
      postId: null,
      title: ''
    },
    message: '',
    messageType: 'success',
    profileAuthor: '', // The author whose profile is being edited (from URL)
    
    // Computed property to check if we can add a page
    get canAddPage() {
      return this.newPage.path.trim() && 
             this.newPage.postId && 
             this.newPage.postId > 0;
    },
    
    init() {
      // Extract profile author from URL
      const pathMatch = window.location.pathname.match(/\/edit-author\/([^/]+)/);
      this.profileAuthor = pathMatch ? pathMatch[1] : '';
      
      this.loadInitialData();
    },
    
    loadInitialData() {
      try {
        const initialDataElement = document.getElementById('custom-pages-data');
        if (initialDataElement) {
          const initialData = JSON.parse(initialDataElement.textContent);
          this.pages = Array.isArray(initialData) ? initialData : [];
        }
      } catch (e) {
        console.error('Failed to load initial custom pages data:', e);
        this.pages = [];
      }
    },
    
    showMessage(text, type = 'success') {
      this.message = text;
      this.messageType = type;
      // Clear message after 5 seconds
      setTimeout(() => {
        this.message = '';
      }, 5000);
    },
    
    validatePath(path) {
      if (!path || path.length > 50) {
        throw new Error('Path must be 1-50 characters');
      }
      
      if (!/^[a-zA-Z0-9_-]+$/.test(path)) {
        throw new Error('Path must contain only letters, numbers, hyphens, and underscores');
      }
      
      // Remove the check - we'll handle updates in addPage
      // Allow paths to be replaced/updated
    },
    
    async addPage() {
      try {
        const { path, postId, title } = {
          path: this.newPage.path.trim(),
          postId: this.newPage.postId,
          title: this.newPage.title.trim()
        };
        
        if (!this.canAddPage) {
          throw new Error('Please fill in all fields');
        }
        
        this.validatePath(path);
        
        const result = await Alpine.store('walletStore').runDysonScript({
          scriptAddress: window.scriptAddress,
          functionName: "link_page",
          kwargs: JSON.stringify({ 
            path, 
            post_id: postId, 
            title: title || '',
            author: getAuthorIdentity()
          }),
          gasLimit: "auto",
        });
        
        if (result.success) {
          // Check if this was an update or a new page
          const existingPageIndex = this.pages.findIndex(page => page.path === path);
          
          if (existingPageIndex >= 0) {
            // Update existing page
            this.pages[existingPageIndex] = { path, post_id: postId, title: title || '' };
            this.showMessage("Custom page updated successfully!");
          } else {
            // Add new page
            this.pages.push({ path, post_id: postId, title: title || '' });
            this.showMessage("Custom page added successfully!");
          }
          
          this.resetForm();
        } else {
          throw new Error(result.rawLog || 'Transaction failed');
        }
      } catch (error) {
        console.error("Error adding custom page:", error);
        this.showMessage(`Failed to add custom page: ${error.message}`, 'error');
      }
    },
    
    async removePage(path) {
      if (!confirm(`Remove custom page "${path}"?`)) return;
      
      try {
        const result = await Alpine.store('walletStore').runDysonScript({
          scriptAddress: window.scriptAddress,
          functionName: "unlink_page",
          kwargs: JSON.stringify({ 
            path, 
            author: getAuthorIdentity()
          }),
          gasLimit: "auto",
        });
        
        if (result.success) {
          const index = this.pages.findIndex(page => page.path === path);
          if (index > -1) {
            this.pages.splice(index, 1);
          }
          this.showMessage("Custom page removed successfully!");
        } else {
          throw new Error(result.rawLog || 'Transaction failed');
        }
      } catch (error) {
        console.error("Error removing custom page:", error);
        this.showMessage(`Failed to remove custom page: ${error.message}`, 'error');
      }
    },
    
    resetForm() {
      this.newPage = {
        path: '',
        postId: null,
        title: ''
      };
    }
  };
}

/**
 * Alpine.js component for profile editing
 */
export function profileEditor() {
  return {
    content: '',
    isLoading: false,
    message: '',
    messageType: 'success',
    profileAuthor: '', // The author whose profile is being edited (from URL)
    previewHtml: '',
    previewDebounceTimeout: null,
    
    init() {
      // Load initial content from textarea
      const textarea = this.$refs.profileContent;
      if (textarea) {
        this.content = textarea.value;
      }
      
      // Extract profile author from URL
      const pathMatch = window.location.pathname.match(/\/edit-author\/([^/]+)/);
      this.profileAuthor = pathMatch ? pathMatch[1] : '';
      
      // Initialize preview
      this.updatePreview();
      
      // Watch for content changes to update preview with debounce
      this.$watch('content', () => {
        this.debouncedUpdatePreview();
      });
    },
    
    get currentAuthor() {
      try {
        return this.$store.walletStore.getAuthorIdentity();
      } catch {
        return '';
      }
    },
    
    get isOwner() {
      return this.currentAuthor && this.currentAuthor === this.profileAuthor;
    },
    
    get canSave() {
      return !this.isLoading && 
             this.$store.walletStore.isWalletConnected() && 
             this.content.trim().length > 0 &&
             this.isOwner;
    },
    
    showMessage(text, type = 'success') {
      this.message = text;
      this.messageType = type;
      setTimeout(() => {
        this.message = '';
      }, 5000);
    },
    
    embedPosts(contentText, depth) {
      return contentText.replace(/(?:^\n*?|\n+?)\/(\d+)(#[^\s]+)?(?:\s*\n*?$|\n+?)/gm, (match, p1, p2) => {
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
    
    debouncedUpdatePreview() {
      if (this.previewDebounceTimeout) {
        clearTimeout(this.previewDebounceTimeout);
      }
      this.previewDebounceTimeout = setTimeout(() => {
        this.updatePreview();
      }, 300);
    },

    updatePreview() {
      const escaped = this.content.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
      this.previewHtml = this.embedPosts(escaped, 1);
      this.$nextTick(() => {
        const preview = this.$refs.preview;
        if (preview) {
          preview.classList.add('markdown');
          renderMarkdownAndHighlight(preview).then(() => {
            if (typeof htmx !== 'undefined') {
              htmx.process(preview);
            }
          }).catch(error => {
            console.error('Error rendering markdown:', error);
          });
        }
      });
    },
    
    async saveProfile() {
      if (!this.canSave) return;
      
      this.isLoading = true;
      
      try {
        const authorName = getAuthorIdentity();
        
        if (!authorName) {
          throw new Error('Could not determine author identity. Please connect your wallet and select an identity.');
        }

        const result = await this.$store.walletStore.runDysonScript({
          scriptAddress: window.scriptAddress,
          functionName: "edit_author_profile",
          kwargs: JSON.stringify({ 
            content: this.content, 
            author: authorName 
          }),
          gasLimit: "auto",
        });
        
        if (result.success) {
          this.showMessage("Profile updated successfully!");
          // Navigate using HTMX form trigger (URL already set via Alpine binding)
          setTimeout(() => {
            const navForm = document.getElementById('profile-nav-form');
            if (navForm && typeof htmx !== 'undefined') {
              // Process the form with HTMX to ensure bindings are active
              htmx.process(navForm);
              // Trigger the form submission
              navForm.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
            } else {
              console.error('Navigation form element not found or HTMX not available');
              // Fallback to direct navigation
              window.location.href = `/authors/${authorName}`;
            }
          }, 1500);
        } else {
          throw new Error(result.rawLog || 'Profile update failed');
        }
      } catch (error) {
        console.error("Error updating profile:", error);
        this.showMessage(`Failed to update profile: ${error.message}`, 'error');
      } finally {
        this.isLoading = false;
      }
    }
  };
}

// Make functions available globally for Alpine.js
window.customPagesManager = customPagesManager;
window.profileEditor = profileEditor;
