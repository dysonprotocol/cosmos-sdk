// nftStore.js - Alpine components for NFT browsing & bidding

document.addEventListener('alpine:init', () => {
  // --- NFT Classes Component ---
  Alpine.data('nftClassesComponent', () => ({
    classes: [],
    loading: false,
    error: '',
    async load() {
      this.loading = true;
      this.error = '';
      try {
        const res = await fetch('/dysonprotocol/nft/v1beta1/classes');
        if (!res.ok) throw new Error(await res.text());
        const json = await res.json();
        this.classes = (json.classes || []).map((c) => ({
          class_id: c.id,
          description: c.description || '',
        }));
      } catch (e) {
        console.error(e);
        this.error = e.message;
      } finally {
        this.loading = false;
      }
    },
    init() {
      this.load();
    },
  }));

  // --- NFTs Component ---
  Alpine.data('nftsComponent', () => ({
    nfts: [],
    loading: false,
    error: '',
    classId: '',
    ownerAddress: '',
    classMeta: null,
    classAlwaysListed: false,
    init() {
      // Look for JSON <script> config inside component
      const cfgTag = this.$el.querySelector('script.nfts-config[type="application/json"]');
      if (cfgTag) {
        try {
          const cfg = JSON.parse(cfgTag.textContent.trim());
          this.classId = cfg.classId || '';
          this.ownerAddress = cfg.ownerAddress || '';
        } catch (e) {
          console.error('Invalid NFT config JSON', e);
        }
      }
      this.load();
    },
    get walletAddress() {
      return Alpine.store('walletStore')?.activeWalletMeta?.address || '';
    },
    async load() {
      this.loading = true;
      this.error = '';
      try {
        // If classId provided, fetch class metadata first
        if (this.classId) {
          try {
            const clsRes = await fetch(`/dysonprotocol/nft/v1beta1/classes/${encodeURIComponent(this.classId)}`);
            if (clsRes.ok) {
              const clsJson = await clsRes.json();
              this.classMeta = clsJson.class || null;
              this.classAlwaysListed = this.classMeta?.data?.always_listed || false;
            }
          } catch (_) {}
        }

        let url = '/dysonprotocol/nft/v1beta1/nfts?';
        if (this.classId) url += `class_id=${encodeURIComponent(this.classId)}`;
        if (this.ownerAddress) url += `${this.classId ? '&' : ''}owner=${encodeURIComponent(this.ownerAddress)}`;
        const res = await fetch(url);
        if (!res.ok) throw new Error(await res.text());
        const json = await res.json();
        this.nfts = (json.nfts || []).map((n) => ({
          class_id: n.class_id,
          id: n.id,
          uniqueKey: `${n.class_id}-${n.id}`,
          owner: n.owner || '',
          uri: n.uri || '',
          uriHash: n.uri_hash || '',
          listed: false, // will fetch below
          newBid: '',
          bidding: false,
          bidTxHash: '',
          bidError: '',
          // valuation & bids
          valuationAmount: '',
          valuationDenom: 'dys',
          currentBidAmount: '',
          currentBidDenom: 'dys',
          currentBidder: '',
          hasActiveBid: false,
          newValuation: '',
          newValuationSet: '',
          settingValuation: false,
          setValTxHash: '',
          setValError: '',
          // ownership / actions
          processingBid: false,
          ownerActionTxHash: '',
          ownerActionError: '',
          togglingListed: false,
          canBid: false,
          metadata: '',
          valuationExpiry: '',
          bidTimestamp: '',
        }));
        // fetch metadata to get listed & owner flags
        for (const nft of this.nfts) {
          try {
            // Owner endpoint gives authoritative owner value
            const ownerRes = await fetch(`/dysonprotocol/nft/v1beta1/owner/${encodeURIComponent(nft.class_id)}/${encodeURIComponent(nft.id)}`);
            if (ownerRes.ok) {
              const ownerJson = await ownerRes.json();
              nft.owner = ownerJson.owner || nft.owner || '';
            }
          } catch (_) {}

          try {
            // NFT endpoint provides metadata such as listed flag
            const nftRes = await fetch(`/dysonprotocol/nft/v1beta1/nfts/${encodeURIComponent(nft.class_id)}/${encodeURIComponent(nft.id)}`);
            if (nftRes.ok) {
              const nftJson = await nftRes.json();
              const data = nftJson.nft?.data;
              nft.listed = data?.listed || false;
              nft.uri = nftJson.nft?.uri || nft.uri;
              nft.uriHash = nftJson.nft?.uri_hash || nft.uriHash;
              // valuation & bid info
              nft.valuationAmount = data?.valuation?.amount || '';
              nft.valuationDenom = data?.valuation?.denom || 'dys';
              nft.currentBidAmount = data?.current_bid?.amount || '';
              nft.currentBidDenom = data?.current_bid?.denom || 'dys';
              nft.currentBidder = data?.current_bidder || '';
              nft.hasActiveBid = Boolean(nft.currentBidAmount && nft.currentBidder);
              nft.valuationExpiry = data?.valuation_expiry || '';
              nft.bidTimestamp = data?.bid_timestamp || '';
              nft.metadata = data?.metadata || '';
            }
          } catch (e) {
            console.error('Error fetching NFT data', e);
          }

          nft.canBid = nft.listed || this.classAlwaysListed;
        }
      } catch (e) {
        console.error(e);
        this.error = e.message;
      } finally {
        this.loading = false;
      }
    },
    async placeBid(nft) {
      nft.bidError = '';
      nft.bidTxHash = '';
      if (!this.walletAddress) {
        nft.bidError = 'Connect wallet';
        return;
      }
      if (!nft.newBid) {
        nft.bidError = 'Amount required';
        return;
      }
      if (!this.canBid(nft)) {
        nft.bidError = 'NFT is not listed for bidding';
        console.error('Bid blocked: NFT not listed', nft.class_id, nft.id);
        return;
      }
      try {
        nft.bidding = true;
        const msg = {
          '@type': '/dysonprotocol.nameservice.v1.MsgPlaceBid',
          bidder: this.walletAddress,
          nft_class_id: nft.class_id,
          nft_id: nft.id,
          'bid_amount': { denom: 'dys', amount: String(nft.newBid).trim() },
        };
        const res = await Alpine.store('walletStore').sendMsg({ msg, gasLimit: null });
        if (res.success === false) throw new Error(res.rawLog || 'Tx failed');
        nft.bidTxHash = res.raw?.tx_response?.txhash || res.raw?.result?.txhash || '';
        nft.newBid = '';
      } catch (e) {
        nft.bidError = e.message;
      } finally {
        nft.bidding = false;
      }
    },
    async acceptBid(nft) {
      await this.processBid(nft, true);
    },
    async rejectBid(nft) {
      await this.processBid(nft, false);
    },
    async processBid(nft, accept) {
      nft.ownerActionError = '';
      nft.ownerActionTxHash = '';
      if (!this.isOwner(nft)) {
        nft.ownerActionError = 'Not owner';
        return;
      }
      if (!nft.hasActiveBid) {
        nft.ownerActionError = 'No active bid to process';
        return;
      }
      try {
        nft.processingBid = true;
        const msg = {
          '@type': accept ? '/dysonprotocol.nameservice.v1.MsgAcceptBid' : '/dysonprotocol.nameservice.v1.MsgRejectBid',
          owner: this.walletAddress,
          nft_class_id: nft.class_id,
          nft_id: nft.id,
        };
        if (!accept) {
          // Include new valuation when rejecting a bid
          const amountStr = String(nft.newValuation || nft.valuationAmount || nft.currentBidAmount || '').trim();
          if (!amountStr) {
            nft.ownerActionError = 'New valuation required';
            nft.processingBid = false;
            return;
          }
          msg.new_valuation = { denom: nft.valuationDenom || 'dys', amount: amountStr };
        }
        const res = await Alpine.store('walletStore').sendMsg({ msg, gasLimit: null });
        if (res.success === false) throw new Error(res.rawLog || 'Tx failed');
        nft.ownerActionTxHash = res.raw?.tx_response?.txhash || res.raw?.result?.txhash || '';
        if (!accept) nft.newValuation = '';
        // reload listing info maybe
      } catch (e) {
        nft.ownerActionError = e.message;
      } finally {
        nft.processingBid = false;
      }
    },
    async toggleListed(nft) {
      if (!this.isOwner(nft)) return;
      nft.togglingListed = true;
      nft.ownerActionError = '';
      nft.ownerActionTxHash = '';
      try {
        const msg = {
          '@type': '/dysonprotocol.nameservice.v1.MsgSetListed',
          nft_owner: this.walletAddress,
          nft_class_id: nft.class_id,
          nft_id: nft.id,
          listed: nft.listed,
        };
        const res = await Alpine.store('walletStore').sendMsg({ msg, gasLimit: null });
        if (res.success === false) throw new Error(res.rawLog || 'Tx failed');
        nft.ownerActionTxHash = res.raw?.tx_response?.txhash || res.raw?.result?.txhash || '';
      } catch (e) {
        nft.ownerActionError = e.message;
      } finally {
        nft.togglingListed = false;
      }
    },
    async setValuation(nft) {
      nft.setValError = '';
      nft.setValTxHash = '';
      if (!this.isOwner(nft)) {
        nft.setValError = 'Not owner';
        return;
      }
      if (!nft.newValuationSet) {
        nft.setValError = 'Amount required';
        return;
      }
      try {
        nft.settingValuation = true;
        const msg = {
          '@type': '/dysonprotocol.nameservice.v1.MsgSetValuation',
          owner: this.walletAddress,
          nft_class_id: nft.class_id,
          nft_id: nft.id,
          valuation: { denom: 'dys', amount: String(nft.newValuationSet).trim() },
        };
        const res = await Alpine.store('walletStore').sendMsg({ msg, gasLimit: null });
        if (res.success === false) throw new Error(res.rawLog || 'Tx failed');
        nft.setValTxHash = res.raw?.tx_response?.txhash || res.raw?.result?.txhash || '';
        nft.newValuationSet = '';
      } catch (e) {
        nft.setValError = e.message;
      } finally {
        nft.settingValuation = false;
      }
    },
    canBid(nft) {
      return nft.canBid;
    },
    isOwner(nft) {
      return this.walletAddress && nft.owner === this.walletAddress;
    },
  }));
}); 