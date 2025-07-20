document.addEventListener("alpine:init", () => {
  Alpine.data("scriptStore", () => ({
    // Script info
    scriptAddress: "",
    scriptInfo: {},
    currentCode: "",
    
    // Function parsing
    functions: [],
    functionsLoading: false,
    
    // Test functions
    tests: [],
    
    // Execution state
    executingFunctions: {},
    results: {},
    
    // Test execution state
    executingTests: {},
    testResults: {},
    
    // Update script state
    isUpdatingScript: false,
    updateStatus: "",
    updateResult: null,
    
    // Coverage visualization
    currentCoverageData: null,
    coverageSource: null, // 'demo' or 'test'
    visualizationMode: 'coverage', // 'coverage' or 'performance'
    currentTestCoverageId: null, // Track which test's coverage is currently displayed
    
    init() {
      this.loadScriptInfo();
    },
    
        async loadScriptInfo() {
      try {
        // Read script address from embedded JSON
        const scriptDataElement = document.getElementById('script-data');
        if (!scriptDataElement) {
          throw new Error('Script data not found in page');
        }
        
        const scriptData = JSON.parse(scriptDataElement.textContent);
        this.scriptAddress = scriptData.script_address;
        
        // Query for script info using API
        const apiUrl = window.location.origin;
        const queryUrl = `${apiUrl}/dysonprotocol/script/v1/script_info/${this.scriptAddress}`;
        
        const resp = await fetch(queryUrl);
        if (!resp.ok) {
          throw new Error(`Failed to fetch script info: ${resp.status}`);
        }
        
        const data = await resp.json();
        
        if (data?.script) {
          this.scriptInfo = data.script;
          this.currentCode = data.script.code || "";
          
          // Update the editor content if it exists
          const editor = document.getElementById('editor');
          if (editor && this.currentCode) {
            editor.textContent = this.currentCode;
          }
          
          // Load functions after loading code
          await this.loadFunctions();
        } else {
          console.log("No script data found");
        }
        
      } catch (error) {
        console.error("Error loading script info:", error);
        this.scriptInfo = { error: error.message };
      }
    },
    
    // Load functions from the /script/functions API endpoint
    async loadFunctions() {
      try {
        this.functionsLoading = true;
        const response = await fetch('/script/functions');
        if (response.ok) {
          const functionsData = await response.json();
          this.functions = this.transformFunctionsData(functionsData);
        } else {
          console.error('Failed to load functions:', response.statusText);
          this.functions = [];
        }
      } catch (error) {
        console.error('Error loading functions:', error);
        this.functions = [];
      } finally {
        this.functionsLoading = false;
      }
    },

    // Transform API response to internal format
    transformFunctionsData(functionsData) {
      const allFunctions = Object.entries(functionsData).map(([name, metadata]) => {
        // Generate default kwargs based on function signature
        const defaultKwargs = {};
        metadata.args.forEach(arg => {
          if (arg.default !== null) {
            
              defaultKwargs[arg.name] = arg.default;
            
          } else {
            // Include parameters without defaults as null
            defaultKwargs[arg.name] = null;
          }
        });

        return {
          id: name,
          name: name,
          params: metadata.args.map(arg => arg.name),
          kwargs: JSON.stringify(defaultKwargs, null, 2),
          gasLimit: 200000,
          attachedMsg: "[]",
          doc: metadata.doc,
          pretty: metadata.pretty,
          metadata: metadata  // Preserve original metadata for placeholders
        };
      });
      
      // Separate tests from regular functions
      this.tests = allFunctions.filter(f => f.name.startsWith('test_'));
      this.functions = allFunctions.filter(f => !f.name.startsWith('test_'));
      
      return this.functions;
    },
    
    // Update function arguments
    updateFunctionArgs(funcId, field, value) {
      const func = this.functions.find(f => f.id === funcId);
      if (func) {
        func[field] = value;
      }
    },
    
    // Simulate function execution
    async simulateFunction(func) {
      const funcId = func.id;
      
      try {
        this.executingFunctions[funcId] = 'simulating';
        
        const walletStore = Alpine.store('walletStore');
        if (!walletStore) {
          throw new Error('Wallet store not available');
        }
        
        // Parse attached messages JSON
        let attachedMessages = [];
        try {
          attachedMessages = JSON.parse(func.attachedMsg || "[]");
        } catch (error) {
          console.error("Failed to parse attached messages JSON:", error);
          this.handleResult(funcId, { error: `Invalid attached messages JSON: ${error.message}` }, 'SIMULATION ERROR');
          return;
        }

        const result = await walletStore.runDysonScript({
          scriptAddress: this.scriptAddress,
          functionName: func.name,
          args: '[]',
          kwargs: func.kwargs,
          gasLimit: func.gasLimit,
          attachedMsg: attachedMessages,
          simulate: true
        });
        
        this.handleResult(funcId, result, 'SIMULATION');
        
      } catch (error) {
        console.error("Simulation error:", error);
        this.handleResult(funcId, { error: error.message }, 'SIMULATION ERROR');
      } finally {
        delete this.executingFunctions[funcId];
      }
    },
    
    // Execute function transaction
    async executeFunction(func) {
      const funcId = func.id;
      
      try {
        this.executingFunctions[funcId] = 'executing';
        
        const walletStore = Alpine.store('walletStore');
        if (!walletStore) {
          throw new Error('Wallet store not available');
        }
        
        // Parse attached messages JSON
        let attachedMessages = [];
        try {
          attachedMessages = JSON.parse(func.attachedMsg || "[]");
        } catch (error) {
          console.error("Failed to parse attached messages JSON:", error);
          this.handleResult(funcId, { error: `Invalid attached messages JSON: ${error.message}` }, 'TRANSACTION ERROR');
          return;
        }

        const result = await walletStore.runDysonScript({
          scriptAddress: this.scriptAddress,
          functionName: func.name,
          args: '[]',
          kwargs: func.kwargs,
          gasLimit: func.gasLimit,
          attachedMsg: attachedMessages,
          simulate: false
        });
        
        this.handleResult(funcId, result, 'TRANSACTION');
        
      } catch (error) {
        console.error("Execution error:", error);
        this.handleResult(funcId, { error: error.message }, 'TRANSACTION ERROR');
      } finally {
        delete this.executingFunctions[funcId];
      }
    },
    
    // Handle execution results
    handleResult(funcId, result, type) {
      let output = `[${type}]\n`;
      let hasError = false;
      
      if (result.error) {
        output += 'Error: ' + result.error;
        hasError = true;
      } else if (!result.success) {
        // Handle runDysonScript failure
        const errorMsg = result.rawSendMsgsResponse?.rawLog || 'Transaction failed';
        
        // Even on failure, we might have extracted script response data (gas info, etc.)
        if (result.scriptResponse) {
          // Extract gas information from error simulation results
          if (type === 'SIMULATION' && result.scriptResponse.script_gas_consumed) {
            const gasConsumed = result.scriptResponse.script_gas_consumed;
            // Add 50% buffer to the gas consumed for safety
            const recommendedGas = Math.ceil(gasConsumed * 1.5);
            
            // Update the function's gas limit
            const func = this.functions.find(f => f.id === funcId);
            if (func) {
              func.gasLimit = recommendedGas;
            }
            
            output += `Gas Consumed: ${gasConsumed}\n`;
            output += `Recommended Gas Limit: ${recommendedGas}\n\n`;
          }
          
          output += 'Script Error Response: ' + JSON.stringify(result.scriptResponse, null, 2) + '\n\n';
        }
        
        output += 'Error: ' + errorMsg;
        hasError = true;
      } else {
        // Handle successful runDysonScript response
        if (result.scriptResponse) {
          // Extract gas information from simulation results
          if (type === 'SIMULATION' && result.scriptResponse.script_gas_consumed) {
            const gasConsumed = result.scriptResponse.script_gas_consumed;
            // Add 50% buffer to the gas consumed for safety
            const recommendedGas = Math.ceil(gasConsumed * 1.5);
            
            // Update the function's gas limit
            const func = this.functions.find(f => f.id === funcId);
            if (func) {
              func.gasLimit = recommendedGas;
            }
            
            output += `Gas Consumed: ${gasConsumed}\n`;
            output += `Recommended Gas Limit: ${recommendedGas}\n\n`;
          }
          
          output += 'Script Response: ' + JSON.stringify(result.scriptResponse, null, 2);
        } else {
          output += 'Success: ' + JSON.stringify(result.rawSendMsgsResponse, null, 2);
        }
      }
      
      this.results[funcId] = {
        output: output,
        hasError: hasError,
        timestamp: new Date().toLocaleTimeString()
      };
    },
    
        // Get placeholder text for kwargs
    getKwargsPlaceholder(func) {
      if (!func.metadata || !func.metadata.args || func.metadata.args.length === 0) {
        return '{}';
      }
      
      // Generate placeholder based on actual function metadata defaults only
      const placeholderKwargs = {};
      func.metadata.args.forEach(arg => {
        if (arg.default !== null) {
          // Use the actual default value from the function metadata
          placeholderKwargs[arg.name] = arg.default;
        } else {
          // No fallbacks - use null for parameters without defaults
          placeholderKwargs[arg.name] = null;
        }
      });
      
      return JSON.stringify(placeholderKwargs, null, 2);
    },
    
    // Check if function is currently executing
    isExecuting(funcId, type = null) {
      if (type) {
        return this.executingFunctions[funcId] === type;
      }
      return !!this.executingFunctions[funcId];
    },
    
    // Get execution status text
    getExecutionStatus(funcId) {
      const status = this.executingFunctions[funcId];
      if (status === 'simulating') return 'Simulating...';
      if (status === 'executing') return 'Executing...';
      return '';
    },
    
    // Update script code
    async updateScript() {
      try {
        this.isUpdatingScript = true;
        this.updateStatus = 'Preparing update transaction...';
        this.updateResult = null;
        
        const walletStore = Alpine.store('walletStore');
        if (!walletStore) {
          throw new Error('Wallet store not available');
        }
        
        // Use getWallet() to properly get the wallet info
        const wallet = walletStore.getWallet();
        
        if (!wallet || !wallet.address) {
          throw new Error('No wallet connected or address not available');
        }
        
        // Create the update script message
        const updateMessage = {
          "@type": "/dysonprotocol.script.v1.MsgUpdateScript",
          "address": this.scriptAddress,  // Field 1: script address (not creator_address or script_address!)
          "code": this.currentCode        // Field 2: script code
        };
        
        this.updateStatus = 'Signing and broadcasting transaction...';

        // Send the transaction
        const result = await walletStore.sendMsg({
          msg: updateMessage,
          memo: 'Script update via dashboard'
        });
        
        this.handleUpdateResult(result);
        
        // Reload script info if successful
        if (result.success) {
          this.updateStatus = 'Update successful! Reloading script info...';
          await this.loadScriptInfo();
          // The editor content will be updated by loadScriptInfo
        }
        
      } catch (error) {
        console.error("Update script error:", error);
        this.handleUpdateResult({ error: error.message });
      } finally {
        this.isUpdatingScript = false;
        this.updateStatus = '';
      }
    },
    
    // Handle update script results
    handleUpdateResult(result) {
      let output = '[SCRIPT UPDATE]\n';
      let hasError = false;
      
      if (result.error) {
        output += 'Error: ' + result.error;
        hasError = true;
      } else if (!result.success) {
        const errorMsg = result.rawLog || 'Transaction failed';
        output += 'Error: ' + errorMsg;
        hasError = true;
      } else {
        output += 'Success: Script updated successfully\n\n';
        
        if (result.raw?.tx_response) {
          const txResp = result.raw.tx_response;
          output += `Transaction Hash: ${txResp.txhash}\n`;
          output += `Gas Used: ${txResp.gas_used}\n`;
          output += `Height: ${txResp.height}\n`;
        }
      }
      
      this.updateResult = {
        output: output,
        hasError: hasError,
        timestamp: new Date().toLocaleTimeString()
      };
    },
    
    // Run test function (similar to simulate but for tests)
    async runTest(test) {
      const testId = test.id;
      
      try {
        this.executingTests[testId] = true;
        
        const walletStore = Alpine.store('walletStore');
        if (!walletStore) {
          throw new Error('Wallet store not available');
        }
        
        // Parse attached messages JSON
        let attachedMessages = [];
        try {
          attachedMessages = JSON.parse(test.attachedMsg || "[]");
        } catch (error) {
          console.error("Failed to parse attached messages JSON:", error);
          this.handleTestResult(testId, { error: `Invalid attached messages JSON: ${error.message}` });
          return;
        }

        const result = await walletStore.runDysonScript({
          scriptAddress: this.scriptAddress,
          functionName: test.name,
          args: '[]',
          kwargs: test.kwargs,
          gasLimit: test.gasLimit,
          attachedMsg: attachedMessages,
          simulate: true
        });
        
        this.handleTestResult(testId, result);
        
      } catch (error) {
        console.error("Test error:", error);
        this.handleTestResult(testId, { error: error.message });
      } finally {
        delete this.executingTests[testId];
      }
    },
    
    // Handle test execution results
    handleTestResult(testId, result) {
      console.log("Test result:", result);
      let output = `[TEST EXECUTION]\n`;
      let hasError = false;
      
      if (result.error) {
        output += 'Error: ' + result.error;
        hasError = true;
      } else if (!result.success) {
        const errorMsg = result.rawSendMsgsResponse?.rawLog || 'Test failed';
        
        if (result.scriptResponse) {
          if (result.scriptResponse.script_gas_consumed) {
            const gasConsumed = result.scriptResponse.script_gas_consumed;
            const recommendedGas = Math.ceil(gasConsumed * 1.5);
            
            // Update the test's gas limit
            const test = this.tests.find(t => t.id === testId);
            if (test) {
              test.gasLimit = recommendedGas;
            }
            
            output += `Gas Consumed: ${gasConsumed}\n`;
            output += `Recommended Gas Limit: ${recommendedGas}\n\n`;
          }
          
          output += 'Script Error Response: ' + JSON.stringify(result.scriptResponse, null, 2) + '\n\n';
        }
        
        output += 'Error: ' + errorMsg;
        hasError = true;
      } else {
        if (result.scriptResponse) {
          const gasConsumed = result.scriptResponse.script_gas_consumed || 0;
          let coveragePercentage = 0;
          let totalNodes = 0;
          let coveredNodes = 0;
          
          if (gasConsumed > 0) {
            const recommendedGas = Math.ceil(gasConsumed * 1.5);
            
            // Update the test's gas limit
            const test = this.tests.find(t => t.id === testId);
            if (test) {
              test.gasLimit = recommendedGas;
            }
          }
          
          // Extract and calculate coverage from test results
          if (result.scriptResponse.result) {
            try {
              // Parse the result if it's a string
              let coverageData = result.scriptResponse.result;
              if (typeof coverageData === 'string') {
                coverageData = JSON.parse(coverageData);
              }
              
              // Check if it looks like coverage data (array of arrays with specific structure)
              if (Array.isArray(coverageData) && coverageData.length > 0 && 
                  Array.isArray(coverageData[0]) && coverageData[0].length === 2) {
                
                // Calculate coverage percentage based on AST nodes
                totalNodes = coverageData.length;
                coveredNodes = coverageData.filter(([meta, [calls, gas]]) => calls > 0).length;
                coveragePercentage = totalNodes > 0 ? Math.round((coveredNodes / totalNodes) * 100) : 0;
                
                // Apply coverage visualization (maintains current visualization mode)
                this.coverageSource = 'test';
                this.currentTestCoverageId = testId;
                this.applyCoverage(this.currentCode, coverageData);
              }
            } catch (e) {
              console.log('Test result is not coverage data:', e);
            }
          }
          
          // Show summary instead of full response
          output += `✓ Test completed successfully\n\n`;
                     output += `📊 Coverage: ${coveragePercentage}% (${coveredNodes}/${totalNodes} nodes)\n`;
          output += `⛽ Gas Consumed: ${gasConsumed.toLocaleString()}\n`;
          
          if (gasConsumed > 0) {
            const recommendedGas = Math.ceil(gasConsumed * 1.5);
            output += `💡 Recommended Gas Limit: ${recommendedGas.toLocaleString()}\n`;
          }
          
          if (coveragePercentage > 0) {
            output += `\n🎨 Coverage visualization applied to code editor`;
          }
        } else {
          output += 'Success: ' + JSON.stringify(result.rawSendMsgsResponse, null, 2);
        }
      }
      
      // Store coverage data with the test result
      let storedCoverageData = null;
      if (!hasError && result.scriptResponse?.result) {
        try {
          let coverageData = result.scriptResponse.result;
          if (typeof coverageData === 'string') {
            coverageData = JSON.parse(coverageData);
          }
          if (Array.isArray(coverageData) && coverageData.length > 0 && 
              Array.isArray(coverageData[0]) && coverageData[0].length === 2) {
            storedCoverageData = coverageData;
          }
        } catch (e) {
          // Ignore parsing errors
        }
      }
      
      this.testResults[testId] = {
        output: output,
        hasError: hasError,
        timestamp: new Date().toLocaleTimeString(),
        coverageData: storedCoverageData
      };
    },
    
    // Update test arguments
    updateTestArgs(testId, field, value) {
      const test = this.tests.find(t => t.id === testId);
      if (test) {
        test[field] = value;
      }
    },
    
    // Check if test is currently executing
    isTestExecuting(testId) {
      return !!this.executingTests[testId];
    },
    
    // Check if current wallet is the script owner
    isScriptOwner() {
      const walletStore = Alpine.store('walletStore');
      if (!walletStore || !walletStore.activeWalletMeta || !walletStore.activeWalletMeta.address) {
        return false;
      }
      return walletStore.activeWalletMeta.address === this.scriptAddress;
    },
    
    // Demo coverage data and code (from demo.html)
    getDemoCoverageData() {
      return {
        code: `def fib(n: int=3) -> int:
    if n <= 1:
        return n
    return fib(n - 1) + fib(n - 2) + 1

def test_fib(n: int=1):
    fib(n)
`,
        coverage: [[[1,
          0,
          4,
          38,
          'FunctionDef',
          'def fib(n: int=3) -> int:\n    if n <= 1:\n        return n\n    return fib(n - 1) + fib(n - 2) + 1'],
         [1, 17]],
        [[1, 8, 1, 14, 'arg', 'n: int'], [1, 5]],
        [[1, 11, 1, 14, 'Name', 'int'], [1, 30]],
        [[1, 15, 1, 16, 'Constant', '3'], [1, 0]],
        [[1, 21, 1, 24, 'Name', 'int'], [1, 17]],
        [[2, 4, 3, 16, 'If', 'if n <= 1:\n    return n'], [1, 81]],
        [[2, 7, 2, 13, 'Compare', 'n <= 1'], [1, 81]],
        [[2, 7, 2, 8, 'Name', 'n'], [1, 0]],
        [[2, 12, 2, 13, 'Constant', '1'], [1, 81]],
        [[3, 8, 3, 16, 'Return', 'return n'], [1, 81]],
        [[3, 15, 3, 16, 'Name', 'n'], [1, 84]],
        [[4, 4, 4, 38, 'Return', 'return fib(n - 1) + fib(n - 2) + 1'], [0, 0]],
        [[4, 11, 4, 38, 'BinOp', 'fib(n - 1) + fib(n - 2) + 1'], [0, 0]],
        [[4, 11, 4, 34, 'BinOp', 'fib(n - 1) + fib(n - 2)'], [0, 0]],
        [[4, 11, 4, 21, 'Call', 'fib(n - 1)'], [0, 0]],
        [[4, 11, 4, 14, 'Name', 'fib'], [0, 0]],
        [[4, 15, 4, 20, 'BinOp', 'n - 1'], [0, 0]],
        [[4, 15, 4, 16, 'Name', 'n'], [0, 0]],
        [[4, 19, 4, 20, 'Constant', '1'], [0, 0]],
        [[4, 24, 4, 34, 'Call', 'fib(n - 2)'], [0, 0]],
        [[4, 24, 4, 27, 'Name', 'fib'], [0, 0]],
        [[4, 28, 4, 33, 'BinOp', 'n - 2'], [0, 0]],
        [[4, 28, 4, 29, 'Name', 'n'], [0, 0]],
        [[4, 32, 4, 33, 'Constant', '2'], [0, 0]],
        [[4, 37, 4, 38, 'Constant', '1'], [0, 0]],
        [[6, 0, 7, 10, 'FunctionDef', 'def test_fib(n: int=1):\n    fib(n)'],
         [1, 38]],
        [[6, 13, 6, 19, 'arg', 'n: int'], [1, 26]],
        [[6, 16, 6, 19, 'Name', 'int'], [1, 51]],
        [[6, 20, 6, 21, 'Constant', '1'], [1, 29]],
        [[7, 4, 7, 10, 'Expr', 'fib(n)'], [1, 81]],
        [[7, 4, 7, 10, 'Call', 'fib(n)'], [1, 81]],
        [[7, 4, 7, 7, 'Name', 'fib'], [1, 0]],
        [[7, 8, 7, 9, 'Name', 'n'], [1, 94]]]
      };
    },
    
    // Helper: convert + assert (from demo.html)
    convertCoverage(coverage, code) {
      const lines = code.split('\n');
      const offs = [];
      for (let i = 0; i < lines.length; i++) {
        offs[i] = i === 0
          ? 0
          : offs[i-1] + lines[i-1].length + 1;
      }
      return coverage.map(([meta, [calls, gas]]) => {
        const [sL, sC, eL, eC, , snippet] = meta;
        const start = offs[sL-1] + sC;
        const end   = offs[eL-1] + eC;
        const actual = code.slice(start, end);
        //console.assert(
        //  actual === snippet,
        //  `Mismatch at ${sL}:${sC}-${eL}:${eC}\n› got    "${actual}"\n› want   "${snippet}"`
        //);
        return { start:[sL,sC], end:[eL,eC], calls, gas };
      });
    },
    
    // Show coverage visualization with demo data
    showDemoCoverage() {
      const demoData = this.getDemoCoverageData();
      
      // Set the editor content to demo code
      const editor = document.getElementById('editor');
      if (editor) {
        editor.textContent = demoData.code;
        this.currentCode = demoData.code;
      }
      
      // Reset to coverage mode and apply visualization
      this.visualizationMode = 'coverage';
      this.coverageSource = 'demo';
      this.currentTestCoverageId = null;
      this.applyCoverage(demoData.code, demoData.coverage);
    },
    
    // Apply coverage highlighting (from demo.html approach)
    applyCoverage(code, coverageData) {
      const editor = document.getElementById('editor');
      if (!editor) return;
      
      // Convert coverage data with validation
      const report = this.convertCoverage(coverageData, code);
      
      // Build lineOffsets for viz
      const lines = code.split('\n');
      const lineOffsets = [];
      for (let i = 0; i < lines.length; i++) {
        lineOffsets[i] = i === 0
          ? 0
          : lineOffsets[i-1] + lines[i-1].length + 1;
      }
      
      // Build & sort events
      const events = [];
      report.forEach(r => {
        const startPos = lineOffsets[r.start[0]-1] + r.start[1];
        const endPos   = lineOffsets[r.end[0]-1]   + r.end[1];
        events.push({pos:startPos, type:'start', calls:r.calls, gas:r.gas, spanEnd:endPos, spanStart:startPos});
        events.push({pos:endPos,   type:'end',                           spanEnd:endPos, spanStart:startPos});
      });
      events.sort((a,b)=>{
        if(a.pos!==b.pos) return a.pos-b.pos;
        if(a.type!==b.type) return a.type==='start' ? -1:1;
        return a.type==='start'
          ? b.spanEnd - a.spanEnd
          : b.spanStart - a.spanStart;
      });
      
      // Compute maxes
      const maxCalls  = Math.max(...report.map(r=>r.calls));
      const maxGas = Math.max(...report.map(r=>r.gas));
      
      // One-pass string builder
      let last = 0, parts = [];
      events.forEach(ev => {
        if (ev.pos > last) {
          parts.push( this.escapeHTML(code.slice(last, ev.pos)) );
          last = ev.pos;
        }
        if (ev.type === 'start') {
          const color = this.visualizationMode === 'coverage' 
            ? this.getCoverageColor(ev.calls, maxCalls)
            : this.getPerformanceColor(ev.gas, maxGas);
          parts.push(
            `<mark data-calls="${ev.calls}" data-gas="${ev.gas}"`+
            ` data-calls="${ev.calls}" data-gas="${ev.gas}"`+
            ` title="Calls: ${ev.calls}, Gas: ${ev.gas}"`+
            ` style="background:${color}">`
          );
        } else {
          parts.push(`</mark>`);
        }
      });
      if (last < code.length) {
        parts.push( this.escapeHTML(code.slice(last)) );
      }
      editor.innerHTML = parts.join('');
      
      this.currentCoverageData = coverageData;
    },
    
    // Escape HTML (from demo.html)
    escapeHTML(s) {
      return s.replace(/&/g,'&amp;')
              .replace(/</g,'&lt;')
              .replace(/>/g,'&gt;');
    },
    
    // Clear coverage highlighting
    clearCoverage() {
      const editor = document.getElementById('editor');
      if (editor) {
        // Restore plain text content
        editor.textContent = this.currentCode;
      }
      
      this.currentCoverageData = null;
      this.coverageSource = null;
      this.visualizationMode = 'coverage';
      this.currentTestCoverageId = null;
    },
    
    // Set visualization mode (from demo.html toggle functionality)
    setVisualizationMode(mode) {
      this.visualizationMode = mode;
      // Re-apply coverage with new mode
      if (this.currentCoverageData) {
        this.applyCoverage(this.currentCode, this.currentCoverageData);
      }
    },
    
    // Re-apply coverage from a specific test result
    reapplyTestCoverage(testId, mode = null) {
      const testResult = this.testResults[testId];
      if (!testResult || !testResult.coverageData) {
        return;
      }
      
      // Set visualization mode if provided
      if (mode) {
        this.visualizationMode = mode;
      }
      
      // Apply the test's coverage data
      this.coverageSource = 'test';
      this.currentTestCoverageId = testId;
      this.applyCoverage(this.currentCode, testResult.coverageData);
    },
    
    // Generate color for coverage mode (from demo.html)
    getCoverageColor(calls, maxCalls) {
      if (!calls) return '#ffcccc';
      const ratio = Math.min(calls/maxCalls,1);
      const start={r:204,g:255,b:204}, end={r:0,g:255,b:0};
      const r=Math.round(start.r+(end.r-start.r)*ratio);
      const g=Math.round(start.g+(end.g-start.g)*ratio);
      const b=Math.round(start.b+(end.b-start.b)*ratio);
      return `rgb(${r},${g},${b})`;
    },
    
    // Generate color for performance mode (from demo.html)
    getPerformanceColor(gas, maxGas) {
      const ratio = Math.min(gas/maxGas,1);
      const hue       = Math.round(60*(1-ratio));
      const lightness = Math.round(100-50*ratio);
      return `hsl(${hue},100%,${lightness}%)`;
    },
  }));
});