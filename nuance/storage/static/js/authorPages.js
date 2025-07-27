/**
 * Author Pages JavaScript Module
 * Handles functionality for author profile pages, custom pages, and related features
 */

// Alpine.js component for managing custom pages
export function customPagesManager() {
  return {
    pages: [],
    newPage: {
      path: '',
      title: '',
      postId: null
    },
    message: '',
    messageType: 'success',
    
    // Computed property to check if we can add a page
    get canAddPage() {
      return this.newPage.path.trim() && 
             this.newPage.title.trim() && 
             this.newPage.postId && 
             this.newPage.postId > 0;
    },
    
    init() {
      // Load initial data from template
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
      setTimeout(() => {
        this.message = '';
      }, 5000);
    },
    
    validatePath(path) {
      if (!path || path.length > 50) {
        throw new Error('Path must be 1-50 characters');
      }
      
      // Check if path contains only allowed characters
      if (!/^[a-zA-Z0-9_-]+$/.test(path)) {
        throw new Error('Path must contain only letters, numbers, hyphens, and underscores');
      }
      
      // Check for duplicate paths
      if (this.pages.some(page => page.path === path)) {
        throw new Error('A page with this path already exists');
      }
    },
    
    async addPage() {
      try {
        const path = this.newPage.path.trim();
        const title = this.newPage.title.trim();
        const postId = this.newPage.postId;
        const authorName = this.getAuthorIdentity();
        
        if (!this.canAddPage) {
          throw new Error('Please fill in all fields');
        }
        
        this.validatePath(path);
        
        // Use the wallet store to run the dyson script
        const result = await Alpine.store('walletStore').runDysonScript({
          scriptAddress: window.scriptAddress,
          functionName: "link_page",
          kwargs: JSON.stringify({ 
            path: path, 
            title: title, 
            post_id: postId, 
            author: authorName
          }),
          gasLimit: "auto",
        });
        
        if (result.success) {
          // Add to local state
          this.pages.push({ 
            path: path, 
            title: title, 
            post_id: postId 
          });
          
          // Clear form
          this.newPage = {
            path: '',
            title: '',
            postId: null
          };
          
          this.showMessage("Custom page added successfully!");
        } else {
          throw new Error(result.rawLog || 'Transaction failed');
        }
      } catch (error) {
        console.error("Error adding custom page:", error);
        this.showMessage("Failed to add custom page: " + error.message, 'error');
      }
    },
    
    async removePage(path) {
      if (!confirm(`Remove custom page "${path}"?`)) return;
      
      try {
        const authorName = this.getAuthorIdentity();
        
        const result = await Alpine.store('walletStore').runDysonScript({
          scriptAddress: window.scriptAddress,
          functionName: "unlink_page",
          kwargs: JSON.stringify({ 
            path: path, 
            author: authorName
          }),
          gasLimit: "auto",
        });
        
        if (result.success) {
          // Remove from local state
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
        this.showMessage("Failed to remove custom page: " + error.message, 'error');
      }
    },
    
    getAuthorIdentity() {
      // Use wallet store to get current author identity
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
  }
}

// Profile editing functionality
export function initProfileEditor() {
  const saveButton = document.getElementById("saveButton");
  const profileContent = document.getElementById("profile-content");
  
  if (!saveButton || !profileContent) {
    return; // Not on profile edit page
  }
  
  // Check if already initialized to prevent duplicate listeners
  if (saveButton.hasAttribute('data-initialized')) {
    return;
  }
  saveButton.setAttribute('data-initialized', 'true');
  
  saveButton.addEventListener("click", async () => {
    try {
      const content = profileContent.value;
      
      // Get author identity from Alpine store
      let authorName;
      try {
        authorName = Alpine.store('walletStore').getAuthorIdentity();
      } catch (error) {
        console.error('Failed to get author identity from wallet store:', error);
        
        // Fallback: try to get from page context or URL
        const authorElement = document.querySelector('[data-author-name]');
        if (authorElement) {
          authorName = authorElement.getAttribute('data-author-name');
        } else {
          const pathMatch = window.location.pathname.match(/\/edit-author\/([^/]+)/);
          authorName = pathMatch ? pathMatch[1] : '';
        }
      }
      
      if (!authorName) {
        throw new Error('Could not determine author identity. Please connect your wallet and select an identity.');
      }

      // Use the wallet store to run the dyson script
      const result = await Alpine.store('walletStore').runDysonScript({
        scriptAddress: window.scriptAddress,
        functionName: "edit_author_profile",
        kwargs: JSON.stringify({ content: content, author: authorName }),
        gasLimit: "auto",
      });
      
      if (result.success) {
        alert("Profile updated successfully!");
        window.location.href = "/authors/" + authorName;
      } else {
        throw new Error(result.rawLog || 'Profile update failed');
      }
    } catch (error) {
      console.error("Error updating profile:", error);
      alert("Failed to update profile: " + error.message);
    }
  });
}

// Utility function to get author identity from wallet store
function getAuthorIdentityFromWalletStore() {
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

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
  initProfileEditor();
});

// Make functions available globally for Alpine.js
window.customPagesManager = customPagesManager; 