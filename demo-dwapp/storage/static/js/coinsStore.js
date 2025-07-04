// coinsStore.js - manages fetching and displaying bank balances on /coins page
// This file is automatically served and included by base.html via render_script_tags()

// Ensure code runs after Alpine framework is initialised

document.addEventListener('alpine:init', () => {
  Alpine.data('balancesComponent', () => ({
    balances: [],
    loading: false,
    error: '',

    // Computed: whether a wallet is currently connected
    get walletConnected() {
      return !!Alpine.store('walletStore')?.activeWalletMeta;
    },

    /** Fetch balances and denom metadata, populate this.balances */
    async loadBalances() {
      if (!this.walletConnected) {
        this.balances = [];
        return;
      }

      this.loading = true;
      try {
        const walletStore = Alpine.store('walletStore');
        const apiUrl = walletStore.restUrl;
        const address = walletStore.activeWalletMeta.address;

        // 1) Fetch balances list
        const resp = await fetch(`${apiUrl}/cosmos/bank/v1beta1/balances/${address}`);
        if (!resp.ok) throw new Error(await resp.text());
        const { balances: rawBalances = [] } = await resp.json();

        const results = [];
        for (const bal of rawBalances) {
          const denom = bal.denom;
          let symbol = denom;
          let exponent = 0;

          // 2) Fetch denom metadata (best-effort, ignore failures)
          try {
            const metaRes = await fetch(`${apiUrl}/cosmos/bank/v1beta1/denoms_metadata/${denom}`);
            if (metaRes.ok) {
              const metaJson = await metaRes.json();
              const md = metaJson?.metadata || metaJson?.metadatas?.[0];
              if (md) {
                symbol = md.symbol || denom;
                const unit = (md.denom_units || []).find((u) => u.denom === md.display);
                if (unit && unit.exponent != null) exponent = unit.exponent;
              }
            }
          } catch (_) {
            /* ignore metadata errors */
          }

          // 3) Format amount according to exponent
          const rawAmount = bal.amount;
          let displayAmt = rawAmount;
          if (exponent > 0) {
            displayAmt = (Number(rawAmount) / Math.pow(10, exponent)).toLocaleString();
          }

          results.push({ denom, symbol, amount: displayAmt });
        }

        this.balances = results;
      } catch (e) {
        console.error('loadBalances error', e);
        this.error = e.message;
      } finally {
        this.loading = false;
      }
    },

    /** Alpine component initialiser */
    init() {
      // Load balances initially and whenever the wallet connection changes
      this.loadBalances();
      this.$watch(() => Alpine.store('walletStore').activeWalletMeta, () => this.loadBalances());
    },
  }));
});

// --- Send Funds Alpine component ---
document.addEventListener('alpine:init', () => {
  Alpine.data('sendFundsComponent', () => ({
    to: '',
    amount: '',
    denom: 'udys,
    sending: false,
    txHash: '',
    error: '',

    get walletConnected() {
      return !!Alpine.store('walletStore')?.activeWalletMeta;
    },

    async submit() {
      if (!this.walletConnected) {
        this.error = 'Connect a wallet first.';
        return;
      }
      if (!this.to || !this.amount) {
        this.error = 'Recipient and amount are required.';
        return;
      }
      this.sending = true;
      this.error = '';
      this.txHash = '';
      try {
        const walletStore = Alpine.store('walletStore');
        const fromAddr = walletStore.activeWalletMeta.address;
        const msg = {
          '@type': '/cosmos.bank.v1beta1.MsgSend',
          from_address: fromAddr,
          to_address: this.to.trim(),
          amount: [
            {
              denom: this.denom,
              amount: String(this.amount).trim(),
            },
          ],
        };
        const result = await walletStore.sendMsg({ msg, gasLimit: null, memo: '' });
        if (result.success) {
          this.txHash = result.raw?.tx_response?.txhash || result.raw?.result?.txhash || '';
          // Refresh balances via custom event
          window.dispatchEvent(new CustomEvent('balances-refresh'));
          // Clear form
          this.amount = '';
        } else {
          this.error = result.rawLog || 'Transaction failed';
        }
      } catch (e) {
        console.error('sendFunds error', e);
        this.error = e.message;
      } finally {
        this.sending = false;
      }
    },
  }));
});

// --- balancesComponent listens for refresh events ---
window.addEventListener('balances-refresh', () => {
  try {
    const compEl = document.querySelector('#balances');
    if (compEl && compEl.__x) {
      compEl.__x.$data.loadBalances();
    }
  } catch (_) {}
}); 