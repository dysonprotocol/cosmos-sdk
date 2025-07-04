// namesStore.js - Alpine components for Nameservice management UI
// This file is automatically served and included by base.html via render_script_tags()

// Ensure code runs after Alpine framework is initialised

document.addEventListener('alpine:init', () => {
  // --- Register Name Store ---
  // A global store to manage the state of the name registration form.
  // This ensures state persists even if the component is re-initialized.
  Alpine.store('registerNameStore', {
    step: 1, // 1: commit, 2: reveal, 3: done
    name: '',
    valuation: '',
    salt: '',
    commitHash: '',
    committing: false,
    revealing: false,
    txHash: '',
    error: '',

    reset() {
        this.step = 1;
        this.name = '';
        this.valuation = '';
        this.salt = '';
        this.commitHash = '';
        this.committing = false;
        this.revealing = false;
        this.txHash = '';
        this.error = '';
    },
    
    get walletConnected() {
      return !!Alpine.store('walletStore')?.activeWalletMeta;
    },

    get isReady() {
        const walletStore = Alpine.store('walletStore');
        return walletStore?.activeWalletMeta && walletStore.activeWalletMeta.address;
    },

    async commit() {
      this.error = '';
      this.txHash = '';
      if (!this.walletConnected) {
        this.error = 'Connect a wallet first.';
        return;
      }
      if (!this.name || !this.valuation) {
        this.error = 'Name and valuation are required.';
        return;
      }
      
      const walletStore = Alpine.store('walletStore');
      const fromAddr = walletStore.activeWalletMeta.address;

      if (!fromAddr) {
        this.error = 'Wallet address not found. Please ensure your wallet is connected properly.';
        return;
      }

      this.committing = true;
      try {
        // 1. Generate salt
        this.salt = Math.random().toString(36).substring(2, 15);

        // 2. Create commit hash (client-side)
        const commitMsg = `${this.name}:${fromAddr}:${this.salt}`;
        const encoder = new TextEncoder();
        const data = encoder.encode(commitMsg);
        const hashBuffer = await crypto.subtle.digest('SHA-256', data);
        const hashArray = Array.from(new Uint8Array(hashBuffer));
        this.commitHash = hashArray.map(b => b.toString(16).padStart(2, '0')).join('');

        // 3. Send commit transaction
        const msg = {
          '@type': '/dysonprotocol.nameservice.v1.MsgCommit',
          committer: fromAddr,
          hexhash: this.commitHash,
          valuation: {
            denom: 'udys,
            amount: String(this.valuation),
          }
        };
        
        const res = await walletStore.sendMsg({ msg, gasLimit: '200000', memo: 'Commit name registration' });
        if (!res.success) {
          throw new Error(res.rawLog || 'Commit transaction failed');
        }
        
        this.txHash = res.raw?.tx_response?.txhash || res.raw?.result?.txhash || '';
        this.step = 2; // Move to reveal step
      } catch (e) {
        console.error(e);
        this.error = e.message;
      } finally {
        this.committing = false;
      }
    },

    async reveal() {
      this.error = '';
      if (!this.walletConnected) {
        this.error = 'Connect a wallet first.';
        return;
      }
      
      const walletStore = Alpine.store('walletStore');
      const fromAddr = walletStore.activeWalletMeta.address;

      if (!fromAddr) {
        this.error = 'Wallet address not found. Please ensure your wallet is connected properly.';
        return;
      }

      this.revealing = true;
      try {
        const msg = {
          '@type': '/dysonprotocol.nameservice.v1.MsgReveal',
          committer: fromAddr,
          name: this.name,
          salt: this.salt,
        };

        const res = await walletStore.sendMsg({ msg, gasLimit: '300000', memo: 'Reveal name registration' });
        if (!res.success) {
            throw new Error(res.rawLog || 'Reveal transaction failed');
        }
        
        this.txHash = res.raw?.tx_response?.txhash || res.raw?.result?.txhash || '';
        this.step = 3; // Move to done step
        
        // Dispatch event to refresh the names list in the dashboard
        window.dispatchEvent(new CustomEvent('names-refresh', { detail: { newId: this.name } }));

      } catch (e) {
        console.error(e);
        this.error = e.message;
      } finally {
        this.revealing = false;
      }
    }
  });

  // --- Register Name Component (now just a placeholder) ---
  Alpine.data('registerNameComponent', () => ({
    // All state and logic moved to Alpine.store('registerNameStore')
  }));

  // --- Update Name Component ---
  Alpine.data('updateNameComponent', () => ({
    name: '',
    destination: '',
    valuation: '',
    updating: false,
    txHash: '',
    error: '',

    async submit() {
      this.error = '';
      const walletStore = Alpine.store('walletStore');
      if (!walletStore?.activeWalletMeta) {
        this.error = 'Connect a wallet first.';
        return;
      }
      const fromAddr = walletStore.activeWalletMeta.address;
      if (!this.name) {
        this.error = 'Name is required';
        return;
      }
      if (!this.destination && !this.valuation) {
        this.error = 'Provide destination and/or valuation.';
        return;
      }
      try {
        this.updating = true;
        const msgs = [];
        if (this.destination) {
          msgs.push({
            '@type': '/dysonprotocol.nameservice.v1.MsgSetDestination',
            owner: fromAddr,
            name: this.name,
            destination: this.destination.trim(),
          });
        }
        if (this.valuation) {
          msgs.push({
            '@type': '/dysonprotocol.nameservice.v1.MsgSetValuation',
            owner: fromAddr,
            nft_class_id: "nameservice.dys", // assuming name maps to class_id
            nft_id: this.name,       // placeholder mapping
            valuation: {
              denom: 'udys,
              amount: String(this.valuation).trim(),
            },
          });
        }
        if (msgs.length === 0) throw new Error('Nothing to update');
        // send each separately to simplify gas estimation
        let last = null;
        if (msgs.length === 1) {
          // Single message - send directly
          last = await walletStore.sendMsg({msg: msgs[0], gasLimit: null, memo: ''});
          if (last.success === false) throw new Error(last.rawLog || 'Tx failed');
        } else if (msgs.length > 1) {
          // Multiple messages - send as a batch in one transaction
          last = await walletStore.sendMsg({msg: msgs, gasLimit: null, memo: ''});
          if (last.success === false) throw new Error(last.rawLog || 'Tx failed');
        }
        this.txHash = last.raw?.tx_response?.txhash || last.raw?.result?.txhash || '';
        // reset
        this.destination = '';
        this.valuation = '';
      } catch (e) {
        console.error(e);
        this.error = e.message;
      } finally {
        this.updating = false;
      }
    },
  }));

  // --- Coins Component (within Names page) ---
  Alpine.data('namesCoinsComponent', () => ({
    balances: [],
    loading: false,
    error: '',
    denom: '',
    amount: '',
    minting: false,
    txHash: '',
    ownedNames: [],
    async loadOwnedNames() {
      if (!this.walletConnected) { this.ownedNames = []; return; }
      try {
        const walletStore = Alpine.store('walletStore');
        const address = walletStore.activeWalletMeta.address;
        const url = `/dysonprotocol/nft/v1beta1/nfts?class_id=nameservice.dys&owner=${address}`;
        const resp = await fetch(url);
        if (!resp.ok) throw new Error(await resp.text());
        const json = await resp.json();
        this.ownedNames = (json?.nfts || []).map((n)=>n.id);
      } catch(e){ console.error(e); this.ownedNames=[]; }
    },
    denomOwned(denom){
      // A denom is considered owned if it exactly matches an owned name (e.g., bob.dys)
      // OR starts with "<ownedName>/" (e.g., bob.dys/sub/foo)
      return this.ownedNames.some((n) => denom === n || denom.startsWith(`${n}/`));
    },
    get walletConnected() {
      return !!Alpine.store('walletStore')?.activeWalletMeta;
    },
    async load() {
      if (!this.walletConnected) { this.balances = []; return; }
      this.loading = true;
      try {
        await this.loadOwnedNames();
        const walletStore = Alpine.store('walletStore');
        const address = walletStore.activeWalletMeta.address;
        const resp = await fetch(`/cosmos/bank/v1beta1/balances/${address}`);
        if (!resp.ok) throw new Error(await resp.text());
        const { balances: raw = [] } = await resp.json();
        this.balances = raw.filter((c)=> c.denom.includes('.') && this.denomOwned(c.denom)).map(c=>({denom:c.denom, amount:c.amount}));
      } catch(e){ console.error(e); this.error=e.message; }
      finally{ this.loading=false; }
    },
    async mint() {
      this.error = '';
      this.txHash = '';
      if (!this.walletConnected) {
        this.error = 'Connect a wallet first.';
        return;
      }
      if (!this.denom || !this.amount) {
        this.error = 'Denom and amount required.';
        return;
      }
      if (!this.denomOwned(this.denom.trim())) { this.error = 'Denom root must match a name you own.'; return; }
      try {
        this.minting = true;
        const walletStore = Alpine.store('walletStore');
        const fromAddr = walletStore.activeWalletMeta.address;
        const msg = {
          '@type': '/dysonprotocol.nameservice.v1.MsgMintCoins',
          owner: fromAddr,
          amount: [
            {
              denom: this.denom.trim(),
              amount: String(this.amount).trim(),
            },
          ],
        };
        const res = await walletStore.sendMsg({ msg, gasLimit: null, memo: '' });
        if (res.success === false) throw new Error(res.rawLog || 'Mint failed');
        this.txHash = res.raw?.tx_response?.txhash || res.raw?.result?.txhash || '';
        this.denom = '';
        this.amount = '';
        this.load();
      } catch (e) {
        console.error(e);
        this.error = e.message;
      } finally {
        this.minting = false;
      }
    },
    init() {
      this.load();
      this.$watch(() => Alpine.store('walletStore').activeWalletMeta, () => this.load());
    },
  }));

  // --- NFTs Component ---
  Alpine.data('namesNftsComponent', () => ({
    nfts: [],
    loading: false,
    error: '',
    ownedNames: [],
    selectedName: '',
    nftId: '',
    uri: '',
    minting: false,
    txHash: '',
    className: '',
    classSuffix: '',
    classSymbol: '',
    classDesc: '',
    creatingClass: false,
    classError: '',
    classTxHash: '',
    ownedClasses: [],
    selectedClass: '',
    activeTab: 'register',
    async loadOwnedNames() {
      if (!this.walletConnected) { this.ownedNames=[]; return; }
      const walletStore = Alpine.store('walletStore');
      const address = walletStore.activeWalletMeta.address;
      try {
        const resp = await fetch(`/dysonprotocol/nft/v1beta1/nfts?class_id=nameservice.dys&owner=${address}`);
        if (!resp.ok) throw new Error(await resp.text());
        const json = await resp.json();
        this.ownedNames = (json?.nfts||[]).map((n)=>n.id);
      } catch(e){ console.error(e); this.ownedNames=[]; }
    },
    async loadOwnedClasses(){
      if(!this.walletConnected){this.ownedClasses=[];return;}
      const walletStore=Alpine.store('walletStore');
      const address=walletStore.activeWalletMeta.address;
      try{
        const resp=await fetch(`/dysonprotocol/nft/v1beta1/classes?owner=${address}`);
        if(!resp.ok) throw new Error(await resp.text());
        const json=await resp.json();
        // keep only classes starting with owned name
        this.ownedClasses=(json?.classes||[]).map(c=>c.class_id).filter(cid=>this.ownedNames.some(n=>cid===n||cid.startsWith(`${n}/`)));
      }catch(e){console.error(e);this.ownedClasses=[];}
    },
    async load() {
      if (!this.walletConnected) { this.nfts=[]; return; }
      this.loading=true;
      try {
        await this.loadOwnedNames();
        await this.loadOwnedClasses();
        const walletStore = Alpine.store('walletStore');
        const address = walletStore.activeWalletMeta.address;
        const resp = await fetch(`/dysonprotocol/nft/v1beta1/nfts?owner=${address}`);
        if (!resp.ok) throw new Error(await resp.text());
        const json = await resp.json();
        this.nfts = (json?.nfts||[]).filter((n)=> this.ownedClasses.includes(n.class_id)).map((n)=>({id:n.id,class_id:n.class_id,uri:n.uri}));
      } catch(e){ console.error(e); this.error=e.message; }
      finally{ this.loading=false; }
    },
    async mint() {
      this.error=''; this.txHash='';
      if (!this.walletConnected){ this.error='Connect a wallet.'; return; }
      if (!this.selectedClass || !this.nftId){ this.error='Select NFT class and NFT ID.'; return; }
      try {
        this.minting=true;
        const walletStore = Alpine.store('walletStore');
        const fromAddr = walletStore.activeWalletMeta.address;
        const msg={
          '@type':'/dysonprotocol.nameservice.v1.MsgMintNFT',
          owner: fromAddr,
          class_id: this.selectedClass,
          nft_id: this.nftId.trim(),
          uri: this.uri.trim(),
          uri_hash: '',
        };
        const res = await walletStore.sendMsg({msg,gasLimit:null,memo:''});
        if(res.success===false) throw new Error(res.rawLog||'Mint failed');
        this.txHash = res.raw?.tx_response?.txhash || res.raw?.result?.txhash || '';
        this.nftId=''; this.uri='';
        if(!this.ownedClasses.includes(this.selectedClass)) this.ownedClasses.push(this.selectedClass);
        this.load();
      } catch(e){ console.error(e); this.error=e.message; }
      finally{ this.minting=false; }
    },
    async createClass() {
      this.classError=''; this.classTxHash='';
      if (!this.walletConnected){ this.classError='Connect wallet.'; return; }
      if (!this.className){ this.classError='Select root name.'; return; }
      const suffix=this.classSuffix.trim();
      const classId = suffix?`${this.className}/${suffix}`:this.className;
      try {
        this.creatingClass=true;
        const walletStore = Alpine.store('walletStore');
        const fromAddr = walletStore.activeWalletMeta.address;
        const msg={
          '@type':'/dysonprotocol.nameservice.v1.MsgSaveClass',
          owner: fromAddr,
          class_id: classId,
          name: this.className,
          symbol: this.classSymbol.trim(),
          description: this.classDesc.trim(),
          uri: '',
          uri_hash: '',
        };
        const res = await walletStore.sendMsg({msg,gasLimit:null,memo:''});
        if(res.success===false) throw new Error(res.rawLog||'Create class failed');
        this.classTxHash = res.raw?.tx_response?.txhash || res.raw?.result?.txhash || '';
        this.classSuffix=''; this.classSymbol=''; this.classDesc='';
        this.ownedClasses.push(classId);
        this.load();
      } catch(e){ console.error(e); this.classError=e.message; }
      finally{ this.creatingClass=false; }
    },
    init(){ this.load(); this.$watch(()=>Alpine.store('walletStore').activeWalletMeta,()=>this.load()); },
    get walletConnected() { return !!Alpine.store('walletStore')?.activeWalletMeta; },
  }));

  // --- Trading Component ---
  Alpine.data('namesTradingComponent', () => ({
    bids: [],
    loading: false,
    error: '',

    async load() {
      this.loading = true;
      try {
        console.log('[namesTradingComponent] load trading data');
        await new Promise((r) => setTimeout(r, 300));
        this.bids = [];
      } catch (e) {
        this.error = e.message;
      } finally {
        this.loading = false;
      }
    },

    init() {
      this.load();
    },
  }));

  // --- Names List Component ---
  Alpine.data('namesListComponent', () => ({
    names: [],
    loading: false,
    error: '',
    expandedId: null,
    get walletConnected() {
      return !!Alpine.store('walletStore')?.activeWalletMeta;
    },
    toggle(id) {
      if (this.expandedId === id) {
        this.expandedId = null;
        return;
      }
      this.expandedId = id;
      const item = this.names.find((n) => n.id === id);
      if (item && !item._detailsLoaded) {
        this.loadDetails(item);
      }
    },
    async loadDetails(item) {
      try {
        const walletStore = Alpine.store('walletStore');
        const url = `/dysonprotocol/nft/v1beta1/nfts/nameservice.dys/${item.id}`;
        const resp = await fetch(url);
        if (!resp.ok) throw new Error(await resp.text());
        const json = await resp.json();
        const nft = json?.nft || {};
        const data = nft.data || {};
        item.destination = nft.uri || '';
        item.listed = data.listed || false;
        item._detailsLoaded = true;
      } catch (e) {
        console.error(e);
      }
    },
    async load() {
      if (!this.walletConnected) {
        this.names = [];
        return;
      }
      this.loading = true;
      try {
        const walletStore = Alpine.store('walletStore');
        const address = walletStore.activeWalletMeta.address;
        const url = `/dysonprotocol/nft/v1beta1/nfts?class_id=nameservice.dys&owner=${address}`;
        const resp = await fetch(url);
        if (!resp.ok) throw new Error(await resp.text());
        const json = await resp.json();
        const nfts = json?.nfts || [];
        this.names = nfts.map((n) => {
          let valuation = '0';
          try {
            valuation = n.data?.valuation?.amount || '0';
          } catch (_) {}
          return { id: n.id, valuation };
        });
      } catch (e) {
        console.error(e);
        this.error = e.message;
      } finally {
        this.loading = false;
      }
    },
    init() {
      this.load();
      // refresh when wallet changes or after reveal
      this.$watch(() => Alpine.store('walletStore').activeWalletMeta, () => this.load());
      window.addEventListener('names-refresh', () => this.load());
    },
  }));

  // --- Names Dashboard Component ---
  Alpine.data('namesDashboardComponent', () => ({
    names: [],
    loading: false,
    get walletConnected(){ return !!Alpine.store('walletStore')?.activeWalletMeta; },
    
    async loadNames(){
      if(!this.walletConnected){ this.names=[]; return; }
      this.loading=true;
      try{
        const addr=Alpine.store('walletStore').activeWalletMeta.address;
        const res=await fetch(`/dysonprotocol/nft/v1beta1/nfts?class_id=nameservice.dys&owner=${addr}`);
        if(!res.ok) throw new Error(await res.text());
        const json=await res.json();
        this.names=(json.nfts||[]).map(n=>({
          id: n.id,
          valuation: n.data?.valuation?.amount||'0',
          coins:[],
          classes:[],
          _details:false,
          newClass:{suffix:'',symbol:'',desc:'',creating:false,error:'',txHash:''},
          update:{
            destination: '', // Will be populated from current NFT data
            valuation: '', // Will be populated from current NFT data
            updatingDestination: false,
            updatingValuation: false, 
            destinationError: '', 
            valuationError: '',
            destinationTxHash: '',
            valuationTxHash: ''
          },
          mint:{amount:'', denomSubpath:'', error:'', txHash:'', creating:false, denom:n.id},
          burn:{denom:n.id, denomSubpath:'', amount:'', error:'', txHash:'', processing:false}
        }));
        
        // Load current data for each name to pre-populate forms
        await this.loadCurrentDataForNames();
        
        // Pre-populate mint denomination with name ID
        this.names.forEach(n => {
          if (!n.mint.denom) {
            n.mint.denom = n.id;
          }
        });
      }catch(e){ console.error(e);}finally{ this.loading=false; }
    },

    async loadCurrentDataForNames() {
      // Load current destination and valuation for each name to pre-populate update forms
      for (const nameObj of this.names) {
        try {
          const nftRes = await fetch(`/dysonprotocol/nft/v1beta1/nfts/nameservice.dys/${nameObj.id}`);
          if (nftRes.ok) {
            const nftJson = await nftRes.json();
            const nft = nftJson?.nft || {};
            // Pre-populate update form with current values
            nameObj.update.destination = nft.uri || '';
            nameObj.update.valuation = nameObj.valuation || '';
          }
        } catch (e) {
          console.error(`Failed to load current data for ${nameObj.id}:`, e);
        }
      }
    },
    
    denomOwned(name, denom){ return denom===name || denom.startsWith(`${name}/`); },
    
    async loadDetails(obj){
      if(obj._details) return;
      const addr=Alpine.store('walletStore').activeWalletMeta.address;
      
      // Load coins
      try{
        const balRes=await fetch(`/cosmos/bank/v1beta1/balances/${addr}`);
        if(balRes.ok){
          const balJson=await balRes.json();
          obj.coins=[];
          for(const bal of (balJson.balances||[])){
            if(this.denomOwned(obj.id, bal.denom)){
              const coin={
                denom:bal.denom,
                amount:bal.amount,
                supply:'',
                metadata:null,
                // Initialize 'from' address for coins move operation. Default to connected wallet address.
                move:{from:addr, to:'',amount:''},
                burn:{amount:''},
                error:'',
                txHash:'',
                processing: false
              };
              obj.coins.push(coin);
            }
          }
        }
      }catch(_){}
      
              // Load NFT classes
        try{
          // fetch all classes once (pagination limit reasonable)
          const clsRes=await fetch(`/dysonprotocol/nft/v1beta1/classes?pagination.limit=1000`);
          if(clsRes.ok){
            const clsJson=await clsRes.json();
            const classes=(clsJson.classes||[]).filter(cl=>cl.id===obj.id || cl.id.startsWith(`${obj.id}/`));
            obj.classes=classes.map(cl=>({
              class_id:cl.id, 
              symbol: cl.symbol||'', 
              description: cl.description||'', 
              extra_data: '', // Will be loaded from class data
              always_listed: false, // Will be loaded from class data
              annual_pct: '', // Will be loaded from class data
              nfts:[],
              // Pre-populate update form with current class data
              originalSymbol: cl.symbol||'',
              originalDescription: cl.description||'',
              originalExtraData: '',
              originalAlwaysListed: false,
              originalAnnualPct: '',
              newNftId: '',
              newNftUri: '',
              error: '',
              txHash: '',
              updating: false,
              minting: false,
              // Extra data update states
              updatingExtraData: false,
              extraDataError: '',
              extraDataTxHash: '',
              // Always listed update states
              updatingAlwaysListed: false,
              alwaysListedError: '',
              alwaysListedTxHash: '',
              // Annual percentage update states
              updatingAnnualPct: false,
              annualPctError: '',
              annualPctTxHash: ''
            }));
        }
        
        // fetch all NFTs of the classes regardless of owner
        for(const cls of obj.classes){
          try{
            const nftRes=await fetch(`/dysonprotocol/nft/v1beta1/nfts?class_id=${encodeURIComponent(cls.class_id)}`);
            if(nftRes.ok){
              const nftJson=await nftRes.json();
              for(const nft of nftJson.nfts||[]){
                // Create unique key to prevent Alpine duplicate key warnings
                const uniqueKey = `${nft.class_id}-${nft.id}`;
                // Check if NFT already exists to prevent duplicates
                if (!cls.nfts.find(existing => existing.uniqueKey === uniqueKey)) {
                  cls.nfts.push({
                    id:nft.id,
                    uniqueKey: uniqueKey, // Add unique key for Alpine x-for
                    owner:nft.owner||'',
                    uri:nft.uri||'',
                    metadata:'', // Will be loaded from NFT data
                    nftData: null, // Will be loaded from NFT data
                    listed: false, // Will be loaded from NFT data
                    // Initialize 'moveFrom' for NFT move operation. Default to current NFT owner or connected wallet.
                    moveFrom:nft.owner||addr||'',
                    moveTo:'',
                    tx:'',
                    error:'',
                    // Combined NFT data update states
                    updatingData: false,
                    dataError: '',
                    dataTxHash: '',
                    // Move NFT states
                    moving: false,
                    moveError: '',
                    moveTxHash: '',
                    // Burn NFT states
                    burning: false,
                    burnError: '',
                    burnTxHash: '',
                    // Set Listed states
                    updatingListed: false,
                    listedError: '',
                    listedTxHash: ''
                  });
                }
              }
            }
          }catch(e){
            console.error(`Failed to fetch NFTs for class ${cls.class_id}:`, e);
          }
        }
      }catch(e){ console.error(e); }
      
      // Fetch supply & metadata for each denom
      let allSupplies = {};
      try {
        const allSupplyRes = await fetch('/cosmos/bank/v1beta1/supply');
        if (allSupplyRes.ok) {
          const allSupplyJson = await allSupplyRes.json();
          // Create a lookup map for faster access
          for (const supply of allSupplyJson.supply || []) {
            allSupplies[supply.denom] = supply.amount;
          }
        }
      } catch (_) {}

      for(const coin of obj.coins){
        // Use the pre-fetched supply data
        coin.supply = allSupplies[coin.denom] || '';
        
        // Fetch metadata for each denom - wrap in try/catch to suppress 404s
        try{
          const mRes=await fetch(`/cosmos/bank/v1beta1/denoms_metadata/${encodeURIComponent(coin.denom)}`);
          if(mRes.ok){ const mJson=await mRes.json(); coin.metadata=mJson?.metadata||null; }
        }catch(e){
            // Suppress 404 errors for denoms without metadata
            if (!(e instanceof TypeError) && e.message.includes('404')) {
                 console.log(`No metadata found for denom: ${coin.denom}`);
            } else {
                 console.error(`Failed to fetch metadata for ${coin.denom}:`, e);
            }
        }
      }
      
              // Load metadata for each NFT
        for(const cls of obj.classes){
          for(const nft of cls.nfts){
            await this.loadNFTMetadata(cls.class_id, nft);
          }
        }
        
        // Load class data for extra_data
        for(const cls of obj.classes){
          await this.loadClassData(cls);
        }
        
        obj._details=true;
    },
    
    async ensureAllDetails(){
      const promises=this.names.map(n=>this.loadDetails(n));
      await Promise.all(promises);
    },

    async loadNFTMetadata(classId, nft){
      try{
        // Fetch the NFT owner from the owner endpoint
        try{
          const ownerRes = await fetch(`/dysonprotocol/nft/v1beta1/owner/${encodeURIComponent(classId)}/${encodeURIComponent(nft.id)}`);
          if(ownerRes.ok){
            const ownerJson = await ownerRes.json();
            nft.owner = ownerJson?.owner || '';
          }
        }catch(e){
          console.log(`Could not fetch owner for NFT ${classId}/${nft.id}:`, e);
          nft.owner = '';
        }
        
        // Fetch the full NFT data to get the complete NFTData structure
        const nftRes = await fetch(`/dysonprotocol/nft/v1beta1/nfts/${encodeURIComponent(classId)}/${encodeURIComponent(nft.id)}`);
        if(nftRes.ok){
          const nftJson = await nftRes.json();
          const nftData = nftJson?.nft?.data;
          if(nftData){
            // Store the complete NFT data structure
            nft.nftData = nftData;
            
            // Extract specific fields for form usage
            nft.metadata = nftData.metadata || '';
            nft.listed = nftData.listed || false;
          } else {
            // Initialize with defaults if no data
            nft.nftData = {
              listed: false,
              valuation: null,
              valuation_expiry: null,
              current_bidder: '',
              current_bid: null,
              bid_timestamp: null,
              metadata: ''
            };
            nft.metadata = '';
            nft.listed = false;
          }
        }
      }catch(e){
        console.error(`Failed to load metadata for NFT ${classId}/${nft.id}:`, e);
        nft.metadata = '';
        nft.listed = false;
        nft.nftData = null;
        nft.owner = '';
      }
    },

    async loadClassData(cls){
      try{
        // Fetch the NFT class data to get extra_data, always_listed, and annual_pct
        const classRes = await fetch(`/dysonprotocol/nft/v1beta1/classes/${encodeURIComponent(cls.class_id)}`);
        if(classRes.ok){
          const classJson = await classRes.json();
          const classData = classJson?.class?.data;
          if(classData && typeof classData === 'object'){
            // Extract data from the class data
            cls.extra_data = classData.extra_data || '';
            cls.originalExtraData = cls.extra_data;
            cls.always_listed = classData.always_listed || false;
            cls.originalAlwaysListed = cls.always_listed;
            cls.annual_pct = classData.annual_pct || '';
            cls.originalAnnualPct = cls.annual_pct;
          }
        }
      }catch(e){
        console.error(`Failed to load class data for ${cls.class_id}:`, e);
        cls.extra_data = '';
        cls.originalExtraData = '';
        cls.always_listed = false;
        cls.originalAlwaysListed = false;
        cls.annual_pct = '';
        cls.originalAnnualPct = '';
      }
    },
    
    async updateDestination(obj){
      obj.update.destinationError=''; obj.update.destinationTxHash='';
      if(!this.walletConnected){ obj.update.destinationError='Connect wallet.'; return; }
      if(!obj.update.destination){ obj.update.destinationError='Destination is required.'; return; }
      try{
        obj.update.updatingDestination=true;
        const addr=Alpine.store('walletStore').activeWalletMeta.address;
        const msg={
          '@type':'/dysonprotocol.nameservice.v1.MsgSetDestination',
          owner: addr,
          name: obj.id,
          destination: obj.update.destination.trim(),
        };
        const res = await Alpine.store('walletStore').sendMsg({msg, gasLimit:null, memo:''});
        if(res.success===false) throw new Error(res.rawLog||'Tx failed');
        obj.update.destinationTxHash= res.raw?.tx_response?.txhash || res.raw?.result?.txhash || '';
      }catch(e){ obj.update.destinationError=e.message||'Error'; console.error(e); }
      finally{ obj.update.updatingDestination=false; }
    },
    
    async updateValuation(obj){
      obj.update.valuationError=''; obj.update.valuationTxHash='';
      if(!this.walletConnected){ obj.update.valuationError='Connect wallet.'; return; }
      if(!obj.update.valuation){ obj.update.valuationError='Valuation is required.'; return; }
      try{
        obj.update.updatingValuation=true;
        const addr=Alpine.store('walletStore').activeWalletMeta.address;
        const msg={
          '@type':'/dysonprotocol.nameservice.v1.MsgSetValuation',
          owner: addr,
          nft_class_id: 'nameservice.dys',
          nft_id: obj.id,
          valuation:{denom:'udys, amount:String(obj.update.valuation).trim()},
        };
        const res = await Alpine.store('walletStore').sendMsg({msg, gasLimit:null, memo:''});
        if(res.success===false) throw new Error(res.rawLog||'Tx failed');
        obj.update.valuationTxHash= res.raw?.tx_response?.txhash || res.raw?.result?.txhash || '';
        // Update local valuation if it was changed
        obj.valuation = obj.update.valuation;
      }catch(e){ obj.update.valuationError=e.message||'Error'; console.error(e); }
      finally{ obj.update.updatingValuation=false; }
    },
    
    init(){
      this.loadNames().then(()=>this.ensureAllDetails());
      window.addEventListener('names-refresh', e=>{
        this.loadNames().then(()=>this.ensureAllDetails()).then(()=>{
          if(e.detail?.newId){
            this.$nextTick(()=>{ document.getElementById('name-'+e.detail.newId)?.scrollIntoView({behavior:'smooth', block:'center'}); });
          }
        });
      });
      this.$watch(()=>Alpine.store('walletStore').activeWalletMeta,()=>{ this.loadNames().then(()=>this.ensureAllDetails()); });
    },
    
    async createClass(obj){
      const nc=obj.newClass;
      nc.error=''; nc.txHash='';
      if(!this.walletConnected){ nc.error='Connect wallet.'; return; }
      const suffix=nc.suffix.trim();
      const classId=suffix?`${obj.id}/${suffix}`:obj.id;
      try{
        nc.creating=true;
        const addr=Alpine.store('walletStore').activeWalletMeta.address;
        const msg={
          '@type':'/dysonprotocol.nameservice.v1.MsgSaveClass',
          owner: addr,
          class_id: classId,
          name: obj.id,
          symbol: nc.symbol.trim(),
          description: nc.desc.trim(),
          uri:'',
          uri_hash:'',
        };
        const res=await Alpine.store('walletStore').sendMsg({msg,gasLimit:null,memo:''});
        if(res.success===false) throw new Error(res.rawLog||'Failed');
        nc.txHash=res.raw?.tx_response?.txhash || res.raw?.result?.txhash || '';
        nc.suffix=''; nc.symbol=''; nc.desc='';
        // Add new class to local state with pre-populated data
        obj.classes.push({
          class_id:classId,
          symbol: nc.symbol,
          description: nc.desc,
          nfts:[],
          originalSymbol: nc.symbol,
          originalDescription: nc.desc,
          newNftId: '',
          newNftUri: '',
          error: '',
          txHash: '',
          updating: false,
          minting: false
        });
      }catch(e){ nc.error=e.message||'Error'; }
      finally{ nc.creating=false; }
    },
    
    async mintNft(nameObj, cls){
      cls.mintError=''; cls.mintTxHash='';
      if(!this.walletConnected){ cls.mintError='Connect wallet.'; return; }
      if(!cls.newNftId){ cls.mintError='NFT ID required'; return; }
      try{
        cls.minting=true;
        const addr=Alpine.store('walletStore').activeWalletMeta.address;
        const msg={
          '@type':'/dysonprotocol.nameservice.v1.MsgMintNFT',
          owner: addr,
          class_id: cls.class_id,
          nft_id: cls.newNftId.trim(),
          uri: cls.newNftUri||'',
          uri_hash:'',
        };
        const res= await Alpine.store('walletStore').sendMsg({msg, gasLimit:null, memo:''});
        if(res.success===false) throw new Error(res.rawLog||'Mint failed');
        cls.mintTxHash = res.raw?.tx_response?.txhash || res.raw?.result?.txhash || '';
        const newNftId = cls.newNftId.trim();
        const uniqueKey = `${cls.class_id}-${newNftId}`;
        cls.nfts.push({
          id: newNftId, 
          uniqueKey: uniqueKey, // Add unique key for Alpine x-for
          owner:addr,
          uri:cls.newNftUri||'',
          metadata:'', // Empty for newly minted NFTs
          nftData: { // Initialize with default NFT data structure
            listed: false,
            valuation: null,
            valuation_expiry: null,
            current_bidder: '',
            current_bid: null,
            bid_timestamp: null,
            metadata: ''
          },
          listed: false, // Default to not listed
          // Initialize 'moveFrom' for NFT move operation
          moveFrom:addr,
          moveTo:'',
          tx:'',
          error:'',
          // Combined NFT data update states
          updatingData: false,
          dataError: '',
          dataTxHash: '',
          // Move NFT states
          moving: false,
          moveError: '',
          moveTxHash: '',
          // Burn NFT states
          burning: false,
          burnError: '',
          burnTxHash: '',
          // Set Listed states
          updatingListed: false,
          listedError: '',
          listedTxHash: ''
        });
        cls.newNftId=''; cls.newNftUri='';
      }catch(e){ cls.mintError=e.message||'Error'; }
      finally{ cls.minting=false; }
    },
    
    async updateClass(nameObj, cls){
      cls.updateError=''; cls.updateTxHash='';
      if(!this.walletConnected){ cls.updateError='Connect wallet.'; return; }
      if(!cls.symbol && !cls.description){ cls.updateError='Provide symbol and/or description'; return; }
      try{
        cls.updating=true;
        const addr=Alpine.store('walletStore').activeWalletMeta.address;
        const msg={
          '@type':'/dysonprotocol.nameservice.v1.MsgUpdateClass',
          owner: addr,
          class_id: cls.class_id,
          symbol: cls.symbol||'',
          description: cls.description||'',
          uri:'',
          uri_hash:'',
        };
        const res= await Alpine.store('walletStore').sendMsg({msg, gasLimit:null, memo:''});
        if(res.success===false) throw new Error(res.rawLog||'Update failed');
        cls.updateTxHash = res.raw?.tx_response?.txhash || res.raw?.result?.txhash || '';
        // Update original values for future pre-population
        cls.originalSymbol = cls.symbol;
        cls.originalDescription = cls.description;
      }catch(e){ cls.updateError=e.message||'Error'; }
      finally{ cls.updating=false; }
    },

    async updateClassExtraData(nameObj, cls){
      cls.extraDataError=''; cls.extraDataTxHash='';
      if(!this.walletConnected){ cls.extraDataError='Connect wallet.'; return; }
      if(!cls.extra_data){ cls.extraDataError='Extra data is required'; return; }
      try{
        cls.updatingExtraData=true;
        const addr=Alpine.store('walletStore').activeWalletMeta.address;
        const msg={
          '@type':'/dysonprotocol.nameservice.v1.MsgSetNFTClassExtraData',
          owner: addr,
          class_id: cls.class_id,
          extra_data: cls.extra_data
        };
        const res= await Alpine.store('walletStore').sendMsg({msg, gasLimit:null, memo:''});
        if(res.success===false) throw new Error(res.rawLog||'Update failed');
        cls.extraDataTxHash = res.raw?.tx_response?.txhash || res.raw?.result?.txhash || '';
        // Update original value for future pre-population
        cls.originalExtraData = cls.extra_data;
      }catch(e){ cls.extraDataError=e.message||'Error'; }
      finally{ cls.updatingExtraData=false; }
    },
    
    async setClassAlwaysListed(nameObj, cls){
      cls.alwaysListedError=''; cls.alwaysListedTxHash='';
      if(!this.walletConnected){ cls.alwaysListedError='Connect wallet.'; return; }
      try{
        cls.updatingAlwaysListed=true;
        const addr=Alpine.store('walletStore').activeWalletMeta.address;
        const msg={
          '@type':'/dysonprotocol.nameservice.v1.MsgSetNFTClassAlwaysListed',
          owner: addr,
          class_id: cls.class_id,
          always_listed: cls.always_listed
        };
        const res= await Alpine.store('walletStore').sendMsg({msg, gasLimit:null, memo:''});
        if(res.success===false) throw new Error(res.rawLog||'Set always listed failed');
        cls.alwaysListedTxHash = res.raw?.tx_response?.txhash || res.raw?.result?.txhash || '';
        // Update original value for future pre-population
        cls.originalAlwaysListed = cls.always_listed;
      }catch(e){ cls.alwaysListedError=e.message||'Error'; }
      finally{ cls.updatingAlwaysListed=false; }
    },
    
    async setClassAnnualPct(nameObj, cls){
      cls.annualPctError=''; cls.annualPctTxHash='';
      if(!this.walletConnected){ cls.annualPctError='Connect wallet.'; return; }
      if(!cls.annual_pct){ cls.annualPctError='Annual percentage is required'; return; }
      
      // Validate percentage range (0.0 to 100.0)
      const pctFloat = parseFloat(cls.annual_pct);
      if(isNaN(pctFloat) || pctFloat < 0.0 || pctFloat > 100.0){
        cls.annualPctError='Annual percentage must be between 0.0 and 100.0'; 
        return;
      }
      
      try{
        cls.updatingAnnualPct=true;
        const addr=Alpine.store('walletStore').activeWalletMeta.address;
        const msg={
          '@type':'/dysonprotocol.nameservice.v1.MsgSetNFTClassAnnualPct',
          owner: addr,
          class_id: cls.class_id,
          annual_pct: String(cls.annual_pct)
        };
        const res= await Alpine.store('walletStore').sendMsg({msg, gasLimit:null, memo:''});
        if(res.success===false) throw new Error(res.rawLog||'Set annual percentage failed');
        cls.annualPctTxHash = res.raw?.tx_response?.txhash || res.raw?.result?.txhash || '';
        // Update original value for future pre-population
        cls.originalAnnualPct = cls.annual_pct;
      }catch(e){ cls.annualPctError=e.message||'Error'; }
      finally{ cls.updatingAnnualPct=false; }
    },
    
    async mintCoins(nameObj){
      nameObj.mint = nameObj.mint || {amount:'', denomSubpath:'', error:'', txHash:'', creating:false};
      nameObj.mint.error=''; nameObj.mint.txHash='';
      if(!this.walletConnected){ nameObj.mint.error='Connect wallet.'; return; }
      if(!nameObj.mint.amount){ nameObj.mint.error='Amount required'; return; }
      try{
        nameObj.mint.creating=true;
        const addr=Alpine.store('walletStore').activeWalletMeta.address;
        const denomSubpath = nameObj.mint.denomSubpath.trim();
        const denom = denomSubpath ? `${nameObj.id}/${denomSubpath}` : nameObj.id;
        const msg={
          '@type':'/dysonprotocol.nameservice.v1.MsgMintCoins',
          owner: addr,
          amount:[{denom: denom, amount:String(nameObj.mint.amount)}]
        };
        const res=await Alpine.store('walletStore').sendMsg({msg, gasLimit:null, memo:''});
        if(res.success===false) throw new Error(res.rawLog||'Mint failed');
        nameObj.mint.txHash=res.raw?.tx_response?.txhash || res.raw?.result?.txhash || '';
        nameObj.mint.amount='';
        nameObj.mint.denomSubpath='';
        await this.loadDetails(nameObj);
      }catch(e){ nameObj.mint.error=e.message||'Error'; }
      finally{ nameObj.mint.creating=false; }
    },
    
    async moveCoins(nameObj, coin){
      coin.error=''; coin.txHash='';
      // Validate all required fields for MsgMoveCoins
      if(!this.walletConnected){ coin.error='Connect wallet.'; return; }
      if(!coin.move.from || !coin.move.to || !coin.move.amount){
        coin.error='From, To & amount required';
        return;
      }
      try{
        coin.processing=true;
        const addr=Alpine.store('walletStore').activeWalletMeta.address;
        const msg={
          '@type':'/dysonprotocol.nameservice.v1.MsgMoveCoins',
          owner: addr, // The connected wallet address (signer)
          inputs: [ // Must be an array of Input objects
            {
              address: coin.move.from.trim(), // The address from which to move coins
              coins: [
                {
                  denom: coin.denom,
                  amount: String(coin.move.amount).trim(),
                },
              ],
            },
          ],
          outputs: [ // Must be an array of Output objects
            {
              address: coin.move.to.trim(), // The address to which to move coins
              coins: [
                {
                  denom: coin.denom,
                  amount: String(coin.move.amount).trim(),
                },
              ],
            },
          ],
        };
        const res=await Alpine.store('walletStore').sendMsg({msg, gasLimit:null, memo:''});
        if(res.success===false) throw new Error(res.rawLog||'Move failed');
        coin.txHash=res.raw?.tx_response?.txhash || res.raw?.result?.txhash || '';
        // Clear input fields
        coin.move.from = addr; // Reset 'from' to current wallet for convenience
        coin.move.to='';
        coin.move.amount='';
        await this.loadDetails(nameObj);
      }catch(e){ coin.error=e.message||'Error'; }
      finally{ coin.processing=false; }
    },
    
    async burnCoins(nameObj, coin){
      coin.error=''; coin.txHash='';
      if(!this.walletConnected){ coin.error='Connect wallet.'; return; }
      if(!coin.burn.amount){ coin.error='Amount required'; return; }
      try{
        coin.processing=true;
        const addr=Alpine.store('walletStore').activeWalletMeta.address;
        const msg={
          '@type':'/dysonprotocol.nameservice.v1.MsgBurnCoins',
          owner: addr,
          amount: [{denom: coin.denom, amount: String(coin.burn.amount)}]
        };
        const res=await Alpine.store('walletStore').sendMsg({msg, gasLimit:null, memo:''});
        if(res.success===false) throw new Error(res.rawLog||'Burn failed');
        coin.txHash=res.raw?.tx_response?.txhash || res.raw?.result?.txhash || '';
        coin.burn.amount='';
        await this.loadDetails(nameObj);
      }catch(e){ coin.error=e.message||'Error'; }
      finally{ coin.processing=false; }
    },
    
    async burnCoin(nameObj){
      nameObj.burn.error=''; nameObj.burn.txHash='';
      if(!this.walletConnected){ nameObj.burn.error='Connect wallet.'; return; }
      if(!nameObj.burn.amount){ nameObj.burn.error='Amount required'; return; }
      try{
        nameObj.burn.processing=true;
        const addr=Alpine.store('walletStore').activeWalletMeta.address;
        const denomSubpath = nameObj.burn.denomSubpath.trim();
        const denom = denomSubpath ? `${nameObj.id}/${denomSubpath}` : nameObj.id;
        const msg={
          '@type':'/dysonprotocol.nameservice.v1.MsgBurnCoins',
          owner: addr,
          amount: [{denom: denom, amount: String(nameObj.burn.amount).trim()}]
        };
        const res=await Alpine.store('walletStore').sendMsg({msg, gasLimit:null, memo:''});
        if(res.success===false) throw new Error(res.rawLog||'Burn failed');
        nameObj.burn.txHash=res.raw?.tx_response?.txhash || res.raw?.result?.txhash || '';
        nameObj.burn.amount='';
        nameObj.burn.denomSubpath='';
        await this.loadDetails(nameObj);
      }catch(e){ nameObj.burn.error=e.message||'Error'; }
      finally{ nameObj.burn.processing=false; }
    },
    
    async updateNFTData(cls, nf){
      nf.dataError=''; nf.dataTxHash='';
      if(!this.walletConnected){ nf.dataError='Connect wallet.'; return; }
      if(!nf.uri && !nf.metadata){ nf.dataError='Please provide URI and/or metadata to update.'; return; }
      try{
        nf.updatingData=true;
        const addr=Alpine.store('walletStore').activeWalletMeta.address;
        const msg={
          '@type':'/dysonprotocol.nameservice.v1.MsgSetNFTMetadata',
          owner: addr,
          class_id: cls.class_id,
          nft_id: nf.id,
          metadata: nf.metadata||'',
          uri: nf.uri||''
        };
        const res=await Alpine.store('walletStore').sendMsg({msg, gasLimit:null, memo:''});
        if(res.success===false) throw new Error(res.rawLog||'Update failed');
        nf.dataTxHash = res.raw?.tx_response?.txhash || res.raw?.result?.txhash || '';
      }catch(e){ nf.dataError=e.message||'Error'; }
      finally{ nf.updatingData=false; }
    },
    
    async moveNft(cls, nf){
      nf.moveError=''; nf.moveTxHash='';
      // Validate all required fields for MsgMoveNft
      if(!this.walletConnected){ nf.moveError='Connect wallet.'; return; }
      if(!nf.moveTo){ // Check for to address
        nf.moveError='To address required';
        return;
      }
      try{
        nf.moving=true;
        const addr=Alpine.store('walletStore').activeWalletMeta.address;
        const msg={
          '@type':'/dysonprotocol.nameservice.v1.MsgMoveNft',
          owner: addr, // The connected wallet address (signer)
          class_id: cls.class_id,
          nft_id: nf.id,
          to_address: nf.moveTo.trim()
        };
        const res=await Alpine.store('walletStore').sendMsg({msg, gasLimit:null, memo:''});
        if(res.success===false) throw new Error(res.rawLog||'Move failed');
        nf.moveTxHash = res.raw?.tx_response?.txhash || res.raw?.result?.txhash || '';
        // Update local state and clear input
        nf.owner=nf.moveTo.trim(); // Update the displayed owner to the new owner
        nf.moveTo=''; // Clear 'to' address
      }catch(e){ nf.moveError=e.message||'Error'; }
      finally{ nf.moving=false; }
    },
    
    async burnNft(cls, nf){
      nf.burnError=''; nf.burnTxHash='';
      if(!this.walletConnected){ nf.burnError='Connect wallet.'; return; }
      try{
        nf.burning=true;
        const addr=Alpine.store('walletStore').activeWalletMeta.address;
        const msg={
          '@type':'/dysonprotocol.nameservice.v1.MsgBurnNFT',
          owner: addr,
          class_id: cls.class_id,
          nft_id: nf.id
        };
        const res=await Alpine.store('walletStore').sendMsg({msg, gasLimit:null, memo:''});
        if(res.success===false) throw new Error(res.rawLog||'Burn failed');
        nf.burnTxHash = res.raw?.tx_response?.txhash || res.raw?.result?.txhash || '';
        // remove from list after successful burn
        cls.nfts = cls.nfts.filter(x=>x.id!==nf.id);
      }catch(e){ nf.burnError=e.message||'Error'; }
      finally{ nf.burning=false; }
    },
    
    async setNftListed(cls, nf){
      nf.listedError=''; nf.listedTxHash='';
      if(!this.walletConnected){ nf.listedError='Connect wallet.'; return; }
      try{
        nf.updatingListed=true;
        const addr=Alpine.store('walletStore').activeWalletMeta.address;
        const msg={
          '@type':'/dysonprotocol.nameservice.v1.MsgSetListed',
          nft_owner: addr,
          nft_class_id: cls.class_id,
          nft_id: nf.id,
          listed: nf.listed
        };
        const res=await Alpine.store('walletStore').sendMsg({msg, gasLimit:null, memo:''});
        if(res.success===false) throw new Error(res.rawLog||'Set listed failed');
        nf.listedTxHash = res.raw?.tx_response?.txhash || res.raw?.result?.txhash || '';
        // Update the NFT data to reflect the change
        if(nf.nftData){
          nf.nftData.listed = nf.listed;
        }
      }catch(e){ nf.listedError=e.message||'Error'; }
      finally{ nf.updatingListed=false; }
    },
  }));

  // Utility function for scrolling to anchors
  window.scrollToAnchor = function(anchor) {
    const element = document.getElementById(anchor);
    if (element) {
      element.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  };

  // Handle hash changes for deep linking
  window.addEventListener('hashchange', () => {
    const hash = window.location.hash.substring(1);
    if (hash) {
      setTimeout(() => scrollToAnchor(hash), 100);
    }
  });

  // Handle initial hash on page load
  document.addEventListener('DOMContentLoaded', () => {
    const hash = window.location.hash.substring(1);
    if (hash) {
      setTimeout(() => scrollToAnchor(hash), 500);
    }
  });
}); 