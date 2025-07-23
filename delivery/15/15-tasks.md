# PBI-15: Migrate Wallet Management to dys2 Standard

- **PBI ID**: 15
- **Actor**: Developer
- **User Story**: As a developer, I want to replace the legacy `dys1` `dyson.js` and Alpine.js-based wallet management with a new, vanilla JavaScript `dyson.js` module that uses CosmJS and works directly in the browser via import maps, so that the application is aligned with the `dys2` architecture, is more maintainable, and removes frontend framework dependencies.
- **Status**: Proposed
- **Conditions of Satisfaction (CoS)**:
    1. A new `dyson.js` module is created in `nuance/storage/static/js/`.
    2. The new module provides functionality to connect Keplr, and to create, import, and connect to local (encrypted) CosmJS wallets.
    3. The new module can build, sign, and broadcast transactions, including gas estimation via simulation.
    4. The `nuance/script.py` `/wallet` endpoint serves a self-contained HTML page that uses the new `dyson.js` and does not rely on Alpine.js.
    5. The old `wallet.html` template and `walletStore.js` are removed.

---

## 1. Current State Analysis

### Legacy `dys1` System (To Be Deprecated)
The current frontend logic, particularly visible in `nuance/storage/templates/base.html`, is built around an older `dys1` architecture. It relies on:
- A `dyson.js` file that was historically served by the `dys1` node itself.
- A global `dysonVueStore` object for state management and transaction dispatching.
- Functions like `dysonUseKeplr` and `connectWallet()` that are tied to this legacy system.

This approach is outdated and incompatible with the `dys2` chain's architecture.

### In-Progress `dys2` System (The Foundation)
The groundwork for the new `dys2`-compatible system has already been laid across several files:
- **`nuance/storage/static/js/dysonTxUtils.js`**: This file is the new core, containing a comprehensive set of vanilla JavaScript functions for all stages of the transaction lifecycle: creating, encoding, signing, simulating, and broadcasting. It communicates directly with the Cosmos SDK REST API endpoints.
- **`nuance/storage/static/js/walletStore.js`**: This file acts as a state management layer for wallets, but is tightly coupled with Alpine.js. Its logic will be migrated into the new `dyson.js` module and this file will be deleted.

The current UI for wallet management exists as an Alpine.js-driven template (`nuance/storage/templates/wallet.html`), which will be entirely replaced by a dynamically generated, vanilla JavaScript-controlled page.

### The Alpine.js Dependency (To Be Removed)
The primary issue with the current `dys2` implementation is its tight coupling with the Alpine.js framework. `walletStore.js` is written as an Alpine store, and `wallet.html` uses `x-data`, `x-show`, `@click`, etc., to create a reactive UI. The migration requires removing this dependency and reimplementing the same functionality in vanilla JavaScript.

## 2. How to Use the Import Map (`importmap.json`)

The `dys2` frontend will not use a JavaScript bundler (like Webpack or Rollup). Instead, it leverages **Import Maps**, a modern browser feature that allows developers to use "bare" import specifiers, which the browser resolves to full URLs at runtime.

The configuration is in `nuance/storage/static/importmap.json`.

**Example:**
Instead of needing a build step to resolve `@cosmjs/proto-signing`, you can write the import directly in your JavaScript module:
```javascript
import { DirectSecp256k1HdWallet } from "@cosmjs/proto-signing";
```

To enable this, the dynamically generated wallet page from `nuance/script.py` must include a `<script type="importmap">` tag in its `<head>`, pointing to or containing the contents of `importmap.json`.

```html
<script type="importmap" src="/static/importmap.json"></script>
```

This approach simplifies the development workflow and reduces frontend build complexity.

## 3. How to Write the New `dyson.js`

A new `nuance/storage/static/js/dyson.js` file must be created. This file will serve as a vanilla JavaScript replacement for `walletStore.js`, providing a public API for the UI to interact with.

### Key Responsibilities:
1.  **State Management**: It will manage the application state (e.g., `activeWallet`, `localWallets`) using module-scoped variables and persist state to `localStorage`.
2.  **DOM Manipulation**: It will be responsible for all UI updates, replacing the reactive bindings provided by Alpine.js. This involves adding/removing classes, setting text content, and managing element visibility based on state changes.
3.  **Event Handling**: It will attach event listeners to UI elements (buttons, inputs) to trigger wallet actions.
4.  **Abstraction**: It will import and use the low-level functions from `dysonTxUtils.js`, providing a simpler, high-level API to the rest of the application.

### Proposed Public API (to be exported from `dyson.js`):
```javascript
// To be called by an inline script on page load
function init() {
  // - Load wallets from localStorage
  // - Attach event listeners to all buttons and inputs in the wallet UI
  // - Attempt to reconnect to the last used wallet
}

// Connect to Keplr extension
async function connectKeplr() { /* ... */ }

// Disconnect any active wallet
function disconnectWallet() { /* ... */ }

// Import a new local wallet from a mnemonic
async function importLocalWallet(name, mnemonic, password) { /* ... */ }

// Connect to a previously imported local wallet
async function connectLocalWallet(name, password) { /* ... */ }

// Generate a new mnemonic phrase
async function generateMnemonic(wordCount = 24) { /* ... */ }

// Primary function for executing Dyson Protocol scripts
async function runDysonScript({ scriptAddress, functionName, args, kwargs, ... }) {
  // This function will orchestrate the full tx lifecycle:
  // 1. Get the active wallet instance.
  // 2. Automatically estimate gas via simulation.
  // 3. Construct the fee object.
  // 4. Call the `runScript` utility from dysonTxUtils.js to broadcast.
  // 5. Return the parsed script response.
}
```

This new `dyson.js` will effectively become the "brain" of the wallet UI, powered by the utilities in `dysonTxUtils.js`.

## 4. Integration into `nuance/script.py`

The final step is to generate and serve the wallet UI from a new `/wallet` endpoint in `nuance/script.py`. This approach makes the wallet page a self-contained component within the Python script, removing any dependency on external HTML template files.

The Python function for the `/wallet` route will be responsible for constructing the HTML for the main content of the wallet page, which will then be injected into the existing `BASE_TEMPLATE`.

### Important Note on `BASE_TEMPLATE`
The example `render_wallet_page` function below is a conceptual illustration. The actual implementation must integrate with the `BASE_TEMPLATE` constant defined in `nuance/script.py`. The function should generate the HTML for the `<body>` of the wallet page, which is then substituted into the `$body` variable of the `BASE_TEMPLATE`, just as other pages like `_post_list` and `_post_detail` do.

The `BASE_TEMPLATE` itself will also need modification in its `<head>` section to include the necessary scripts for the wallet to function, especially the `importmap` and the new `dyson.js` module script.

### Key requirements for the generated HTML:

1.  **Structure**: The HTML generated by the new function must contain all necessary sections for wallet management:
    *   A section for connecting with browser extensions (Keplr).
    *   A section to display a list of imported local wallets.
    *   A form for importing new local wallets via mnemonic phrase.
    *   A status message area to provide feedback to the user.

2.  **JavaScript Hooks**: All interactive elements (buttons, inputs, etc.) must have unique `id` attributes. This is crucial as it allows the new `dyson.js` module to attach event listeners and manipulate the DOM without relying on a framework. Alpine.js attributes (`x-data`, `@click`, etc.) must not be used.

3.  **Script Injection**: The `BASE_TEMPLATE` must be modified to include the necessary `<script>` tags in the `<head>` to load the import map and the new JavaScript modules. The final script tag should call the `init()` function from `dyson.js` once the DOM is loaded.

### Example Snippet for `nuance/script.py`

```python
# This is a conceptual example. The final implementation will involve
# modifying the wsgi function to add a new route for '/wallet' and
# creating a function that generates the body content.

def _wallet_page(environ, start_response):
    # 1. Define the HTML for the body of the wallet page.
    # All interactive elements have simple 'id' attributes for JS hooks.
    wallet_body_html = f"""
<div class="container mx-auto p-4" id="wallet-page-container">
    <h1 class="text-2xl font-bold mb-4">Wallet Management</h1>

    <!-- Status Message Area -->
    <div id="status-message" class="alert mb-4" style="display: none;"></div>

    <!-- Keplr Connection -->
    <section class="card bg-base-200 shadow-xl mb-8">
      <div class="card-body">
        <h2 class="card-title">Browser Extension</h2>
        <button id="connect-keplr-btn" class="btn btn-primary">Connect with Keplr</button>
        <div id="keplr-not-found" class="alert alert-warning mt-4" style="display: none;">
          Keplr extension not found. Please install it.
        </div>
      </div>
    </section>

    <!-- Imported Wallets List -->
    <section class="card bg-base-200 shadow-xl mb-8">
      <div class="card-body">
        <h2 class="card-title">Imported Wallets</h2>
        <div id="local-wallets-list" class="space-y-4">
            <!-- Wallet items will be rendered here by dyson.js -->
        </div>
        <p id="no-local-wallets" class="text-base-content/70" style="display: none;">No local wallets found.</p>
      </div>
    </section>

    <!-- Import New Wallet Form -->
    <section class="card bg-base-200 shadow-xl">
      <div class="card-body">
        <h2 class="card-title">Import New Wallet</h2>
        <div class="form-control space-y-4">
            <input id="wallet-name-input" placeholder="Wallet Name" class="input input-bordered" />
            <input id="wallet-password-input" type="password" placeholder="Password" class="input input-bordered" />
            <textarea id="mnemonic-textarea" placeholder="Mnemonic phrase..." class="textarea textarea-bordered"></textarea>
            
            <div class="flex gap-2">
              <button id="generate-12-words-btn" class="btn btn-outline btn-sm">Generate 12 Words</button>
              <button id="generate-24-words-btn" class="btn btn-outline btn-sm">Generate 24 Words</button>
            </div>

            <label class="label cursor-pointer justify-start">
                <input type="checkbox" id="mnemonic-backup-checkbox" class="checkbox checkbox-primary" />
                <span class="label-text ml-2">I have backed up my mnemonic.</span>
            </label>
            <button id="import-wallet-btn" class="btn btn-primary">Import Wallet</button>
        </div>
      </div>
    </section>
</div>
"""

    # 2. Substitute the body content into the main BASE_TEMPLATE
    html_content = BASE_TEMPLATE.substitute(
        title="Wallet Management",
        body=wallet_body_html
    )

    # 3. Return the response
    start_response("200 OK", [CONTENT_TYPE_HTML] + HEADERS)
    return [html_content.encode()]

# The main wsgi function would be updated to include a route like:
# elif path_info == "wallet":
#     return _wallet_page(environ, start_response)

```

This implementation ensures that `nuance/script.py` is the single source of truth for the wallet page, completely decoupling it from any templating engine or frontend framework. The old `wallet.html` and `walletStore.js` files can then be safely deleted. 