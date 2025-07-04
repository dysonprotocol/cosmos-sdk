document.addEventListener("alpine:init", () => {
  Alpine.data("tasksStore", () => ({
    // Module parameters
    moduleParams: {},
    moduleParamsLoading: false,
    
    // Tasks data
    tasks: [],
    filteredTasks: [],
    loading: false,
    
    // Pagination
    currentPage: 1,
    pageSize: 20,
    hasMore: false,
    totalTasks: 0,
    
    // Filters
    statusFilters: Alpine.$persist(["PENDING", "DONE", "FAILED", "EXPIRED"]),
    selectedStatuses: Alpine.$persist(["PENDING", "DONE"]),
    
    // Task creation
    createTaskLoading: false,
    newTask: {
      scheduledTimestamp: "+1s",
      expiryTimestamp: "",
      gasLimit: 200000,
      gasFee: "1",
      messages: [
        {
          "@type": "/dysonprotocol.script.v1.MsgExec",
          "executor_address": "",
          "script_address": "",
          "extra_code": "",
          "function_name": "",
          "args": "[]",
          "kwargs": "{}",
          "attached_messages": []
        }
      ]
    },
    

    
    // Task details
    selectedTask: null,
    showTaskDetails: false,
    
    // Statistics
    stats: {
      total: 0,
      pending: 0,
      done: 0,
      failed: 0,
      expired: 0
    },

    init() {
      this.loadModuleParams();
      this.loadTasks();
      
      // Watch for filter changes
      this.$watch('selectedStatuses', () => {
        this.filterTasks();
      });
    },
    
    // Get the current script address from the domain
    getScriptAddress() {
      const hostname = window.location.hostname;
      const parts = hostname.split('.');
      return parts[0];
    },

    // Load module parameters
    async loadModuleParams() {
      try {
        this.moduleParamsLoading = true;
        const apiUrl = window.location.origin;
        const response = await fetch(`${apiUrl}/dysonprotocol/crontask/v1/params`);
        
        if (response.ok) {
          const data = await response.json();
          this.moduleParams = data.params || {};
        } else {
          console.error("Failed to load module parameters:", response.statusText);
        }
      } catch (error) {
        console.error("Error loading module parameters:", error);
      } finally {
        this.moduleParamsLoading = false;
      }
    },

    // Load tasks
    async loadTasks(append = false) {
      try {
        if (!append) {
          this.loading = true;
          this.currentPage = 1;
        }
        
        const scriptAddress = this.getScriptAddress();
        const apiUrl = window.location.origin;
        
        // Build query parameters
        const params = new URLSearchParams({
          'pagination.limit': this.pageSize.toString(),
          'pagination.offset': ((this.currentPage - 1) * this.pageSize).toString()
        });
        
        const fetchUrl = `${apiUrl}/dysonprotocol/crontask/v1/tasks/creator/${scriptAddress}?${params}`;
        console.log("Fetching tasks from:", fetchUrl);
        
        const response = await fetch(fetchUrl);
        const data = await response.json();
        
        if (data?.tasks) {
          const newTasks = data.tasks.map(task => ({
            ...task,
            // Parse timestamps
            scheduledTime: new Date(parseInt(task.scheduled_timestamp) * 1000),
            expiryTime: task.expiry_timestamp ? new Date(parseInt(task.expiry_timestamp) * 1000) : null,
            // Parse messages (try both field names)
            parsedMessages: this.parseMessages(task.msgs || task.messages),
            // Parse message results
            parsedMsgResults: this.parseMsgResults(task.msg_results),
            // Calculate time remaining for pending tasks
            timeRemaining: this.calculateTimeRemaining(task),
            // Extract failure information if task failed
            failure_reason: this.extractFailureReason(task),
            error_log: this.extractErrorLog(task),
            failed_at: task.status === 'FAILED' && task.execution_time ? task.execution_time : null
          }));
          
          if (append) {
            this.tasks = [...this.tasks, ...newTasks];
          } else {
            this.tasks = newTasks;
          }
          
          this.hasMore = newTasks.length === this.pageSize;
          this.updateStats();
          this.filterTasks();
        } else {
          if (!append) {
            this.tasks = [];
            this.filteredTasks = [];
          }
        }
      } catch (error) {
        console.error("Error loading tasks:", error);
        this.tasks = [];
        this.filteredTasks = [];
      } finally {
        this.loading = false;
      }
    },

    // Parse messages for display
    parseMessages(messages) {
      if (!messages || !Array.isArray(messages)) {
        return [];
      }
      
      return messages.map(msg => {
        try {
          return typeof msg === 'string' ? JSON.parse(msg) : msg;
        } catch (error) {
          return { raw: msg };
        }
      });
    },

    // Parse message results for display
    parseMsgResults(msgResults) {
      if (!msgResults || !Array.isArray(msgResults)) {
        return [];
      }
      
      return msgResults.map(result => this.recursiveJsonParse(result));
    },

    // Recursively parse JSON strings in an object
    recursiveJsonParse(obj) {
      if (typeof obj === 'string') {
        try {
          // Try to parse the string as JSON
          const parsed = JSON.parse(obj);
          // Recursively parse the result
          return this.recursiveJsonParse(parsed);
        } catch (e) {
          // If it's not valid JSON, return the original string
          return obj;
        }
      } else if (Array.isArray(obj)) {
        // Recursively parse arrays
        return obj.map(item => this.recursiveJsonParse(item));
      } else if (obj !== null && typeof obj === 'object') {
        // Recursively parse objects
        const result = {};
        for (const [key, value] of Object.entries(obj)) {
          result[key] = this.recursiveJsonParse(value);
        }
        return result;
      }
      // Return primitive values as-is
      return obj;
    },

    // Calculate time remaining for pending tasks
    calculateTimeRemaining(task) {
      if (task.status !== "PENDING") return null;
      
      const now = new Date();
      const scheduled = new Date(parseInt(task.scheduled_timestamp) * 1000);
      const diff = scheduled.getTime() - now.getTime();
      
      if (diff <= 0) return "Overdue";
      
      const days = Math.floor(diff / (24 * 60 * 60 * 1000));
      const hours = Math.floor((diff % (24 * 60 * 60 * 1000)) / (60 * 60 * 1000));
      const minutes = Math.floor((diff % (60 * 60 * 1000)) / (60 * 1000));
      
      if (days > 0) return `${days}d ${hours}h`;
      if (hours > 0) return `${hours}h ${minutes}m`;
      return `${minutes}m`;
    },

    // Extract failure reason from task execution result
    extractFailureReason(task) {
      if (task.status !== 'FAILED') return null;
      
      // Check for generic error fields
      if (task.error) return task.error;
      if (task.failure_reason) return task.failure_reason;
      if (task.error_message) return task.error_message;
      
      return "Task execution failed";
    },

    // Extract message types from parsed messages
    getMessageTypes(messages) {
      if (!messages || !Array.isArray(messages)) {
        return [];
      }
      
      return messages.map((msg, index) => {
        if (msg['@type']) {
          // Extract just the message type name from the full type path
          const typeParts = msg['@type'].split('.');
          return typeParts[typeParts.length - 1] || msg['@type'];
        }
        if (msg.raw) {
          return 'Raw Message';
        }
        return `Message ${index + 1}`;
      });
    },

    // Extract detailed error log from task
    extractErrorLog(task) {
      if (task.status !== 'FAILED') return null;
      
      // Check for generic error log fields
      if (task.raw_log) return task.raw_log;
      if (task.error_log) return task.error_log;
      if (task.log) return task.log;
      
      return null;
    },

    // Update statistics
    updateStats() {
      this.stats = {
        total: this.tasks.length,
        pending: this.tasks.filter(t => t.status === "PENDING").length,
        done: this.tasks.filter(t => t.status === "DONE").length,
        failed: this.tasks.filter(t => t.status === "FAILED").length,
        expired: this.tasks.filter(t => t.status === "EXPIRED").length
      };
    },

    // Filter tasks
    filterTasks() {
      let filtered = [...this.tasks];
      
      // Filter by status
      if (this.selectedStatuses.length > 0) {
        filtered = filtered.filter(task => this.selectedStatuses.includes(task.status));
      }
      
      this.filteredTasks = filtered;
    },

    // Toggle status filter
    toggleStatusFilter(status) {
      const index = this.selectedStatuses.indexOf(status);
      if (index > -1) {
        this.selectedStatuses.splice(index, 1);
      } else {
        this.selectedStatuses.push(status);
      }
    },

    // Reset new task form
    resetNewTask() {
      this.newTask = {
        scheduledTimestamp: "+1s",
        expiryTimestamp: "",
        gasLimit: 200000,
        gasFee: "1",
        messages: [
          {
            "@type": "/dysonprotocol.script.v1.MsgExec",
            "executor_address": "",
            "script_address": "",
            "extra_code": "",
            "function_name": "",
            "args": "[]",
            "kwargs": "{}",
            "attached_messages": []
          }
        ]
      };
      
      // Update the editor content
      this.updateMessagesEditor();
    },

    // Update messages from JSON editor
    updateMessagesFromJson(jsonText) {
      try {
        const parsed = JSON.parse(jsonText);
        if (Array.isArray(parsed)) {
          this.newTask.messages = parsed;
        } else {
          console.error("Messages must be an array");
        }
      } catch (error) {
        console.error("Invalid JSON:", error);
        // Don't update the messages if JSON is invalid
      }
    },

    // Update the messages editor content (without affecting cursor)
    updateMessagesEditor() {
      // Use setTimeout to ensure this runs after Alpine has processed
      setTimeout(() => {
        const editor = this.$refs?.messagesEditor;
        if (editor) {
          editor.textContent = JSON.stringify(this.newTask.messages, null, 2);
        }
      }, 0);
    },



    // Create task
    async createTask() {
      try {
        this.createTaskLoading = true;
        
        const walletStore = Alpine.store('walletStore');
        if (!walletStore?.activeWalletMeta) {
          throw new Error('Wallet not connected');
        }
        
        // Use timestamps directly - server will parse them
        const scheduledTimestamp = this.newTask.scheduledTimestamp.trim();
        if (!scheduledTimestamp) {
          throw new Error('Scheduled timestamp is required');
        }
        
        const expiryTimestamp = this.newTask.expiryTimestamp.trim()
        
        // Validate messages
        if (this.newTask.messages.length === 0) {
          throw new Error('At least one message is required');
        }
        
        // Create the task message
        const taskMsg = {
          "@type": "/dysonprotocol.crontask.v1.MsgCreateTask",
          "creator": walletStore.activeWalletMeta.address,
          "scheduled_timestamp": scheduledTimestamp,
          "expiry_timestamp": expiryTimestamp,
          "task_gas_limit": this.newTask.gasLimit.toString(),
          "task_gas_fee": {
            "denom": "udys",
            "amount": this.newTask.gasFee || "1"
          },
          "msgs": this.newTask.messages
        };
        
        const result = await walletStore.sendMsg({
          msg: taskMsg,
          gasLimit: Math.max(300000, this.newTask.gasLimit + 100000),
          memo: 'Create scheduled task'
        });
        
        if (result.success) {
          this.resetNewTask();
          await this.loadTasks();
        } else {
          console.error("Task creation failed:", result);
          throw new Error(result.rawLog || 'Task creation failed');
        }
        
      } catch (error) {
        console.error("Error creating task:", error);
        alert(`Error creating task: ${error.message}`);
      } finally {
        this.createTaskLoading = false;
      }
    },

    // Delete task
    async deleteTask(taskId) {
      if (!confirm(`Are you sure you want to delete task ${taskId}? This action cannot be undone.`)) {
        return;
      }
      
      try {
        const walletStore = Alpine.store('walletStore');
        if (!walletStore?.activeWalletMeta) {
          throw new Error('Wallet not connected');
        }
        
        const deleteMsg = {
          "@type": "/dysonprotocol.crontask.v1.MsgDeleteTask",
          "creator": walletStore.activeWalletMeta.address,
          "task_id": taskId
        };
        
        const result = await walletStore.sendMsg({
          msg: deleteMsg,
          gasLimit: 200000,
          memo: `Delete task ${taskId}`
        });
        
        if (result.success) {
          await this.loadTasks();
        } else {
          console.error("Task deletion failed:", result);
          throw new Error(result.rawLog || 'Task deletion failed');
        }
        
      } catch (error) {
        console.error("Error deleting task:", error);
        alert(`Error deleting task: ${error.message}`);
      }
    },

    // Clone task
    cloneTask(task) {
      this.newTask = {
        scheduledTimestamp: "+1s",
        expiryTimestamp: "",
        gasLimit: parseInt(task.gas_limit),
        gasFee: task.gas_fee,
        messages: JSON.parse(JSON.stringify(task.parsedMessages))
      };
    },

    // Show task details
    showDetails(task) {
      this.selectedTask = task;
      this.showTaskDetails = true;
    },

    // Hide task details
    hideDetails() {
      this.selectedTask = null;
      this.showTaskDetails = false;
    },

    // Get status badge class
    getStatusBadgeClass(status) {
      const classes = {
        "PENDING": "badge-info",
        "DONE": "badge-success",
        "FAILED": "badge-error",
        "EXPIRED": "badge-neutral"
      };
      return classes[status] || "badge-neutral";
    },

    // Utility functions
    truncateAddress(address, length = 8) {
      if (!address) return "";
      if (address.length <= length * 2) return address;
      return `${address.slice(0, length)}...${address.slice(-length)}`;
    },

    truncateString(str, length = 30) {
      if (!str) return "";
      if (str.length <= length) return str;
      return `${str.slice(0, length)}...`;
    },

    formatTimestamp(timestamp) {
      if (!timestamp) return "";
      const date = new Date(parseInt(timestamp) * 1000);
      return date.toLocaleString();
    },

    formatGas(gasLimit) {
      return parseInt(gasLimit).toLocaleString();
    },

    // Load more tasks
    loadMore() {
      this.currentPage++;
      this.loadTasks(true);
    },


  }));
}); 