function app() {
  return {
    pools: [],
    loading: false,
    error: '',
    load() {
      this.loading = true;
      this.error = '';
      const owner = document.body?.dataset?.scriptAddress || '';
      const prefix = 'pools/';
      const params = new URLSearchParams();
      params.set('owner', owner);
      params.set('index_prefix', prefix);
      params.set('pagination.limit', '1000');
      const url = '/dysonprotocol/storage/v1/storage_list?' + params.toString();
      fetch(url)
        .then((r) => r.json())
        .then((j) => {
          const es = Array.isArray(j.entries) ? j.entries : [];
          this.pools = es.map((e) => {
            let p = {};
            try {
              p = JSON.parse(e.data || '{}') || {};
            } catch {}
            if (p && p.pool_id == null) {
              const idx = e.index || '';
              const tail = idx.split('/').pop() || '';
              const n = parseInt(tail, 10);
              p.pool_id = Number.isFinite(n) ? n : tail;
            }
            return {
              pool_id: p.pool_id,
              base: p.base || {},
              quote: p.quote || {},
              total_shares: p.total_shares,
              shares_denom: p.shares_denom,
              num_trades: p.num_trades || 0,
              created: p.created || '',
              updated: p.updated || '',
            };
          });
        })
        .catch((e) => {
          this.error = String((e && e.message) || e);
        })
        .finally(() => {
          this.loading = false;
        });
    },
  };
}


