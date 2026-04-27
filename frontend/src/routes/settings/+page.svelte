<script lang="ts">
  import { onMount } from 'svelte';
  import ShellLayout from '$lib/components/ShellLayout.svelte';
  import Toggle from '$lib/components/Toggle.svelte';
  import { sortStore } from '$lib/stores/sort';
  import { tauriGetLicenseStatus, tauriActivateLicense, tauriOpenLogFolder } from '$lib/tauri';

  let store = $sortStore;
  $: store = $sortStore;

  let licenseKey = '';
  let activateError = '';
  let activating = false;

  onMount(async () => {
    try {
      const status = await tauriGetLicenseStatus();
      sortStore.update(s => ({
        ...s,
        licenseValid: status.valid,
        licenseTrial: status.trial,
        filesRemaining: status.filesRemaining,
      }));
    } catch { /* dev */ }
  });

  async function activateLicense() {
    if (!licenseKey.trim()) return;
    activating = true;
    activateError = '';
    try {
      await tauriActivateLicense(licenseKey.trim());
      const status = await tauriGetLicenseStatus();
      sortStore.update(s => ({
        ...s,
        licenseValid: status.valid,
        licenseTrial: status.trial,
        filesRemaining: status.filesRemaining,
      }));
      licenseKey = '';
    } catch (e: any) {
      activateError = typeof e === 'string' ? e : 'Invalid license key.';
    } finally {
      activating = false;
    }
  }
</script>

<ShellLayout>
  <div class="content">

    <!-- License section -->
    <section class="section">
      <p class="section-label">License</p>
      <div class="settings-list">
        <div class="setting-row">
          {#if store.licenseValid && !store.licenseTrial}
            <span class="setting-name">Status</span>
            <span class="license-badge pro">Pro — unlimited files</span>
          {:else}
            <span class="setting-name">Status</span>
            <span class="license-badge trial">Trial — 500 file limit</span>
          {/if}
        </div>

        {#if store.licenseTrial || !store.licenseValid}
          <div class="setting-row activate-row">
            <input
              class="key-input"
              type="text"
              placeholder="License key"
              bind:value={licenseKey}
              on:keydown={e => e.key === 'Enter' && activateLicense()}
            />
            <button
              class="btn-activate"
              disabled={activating || !licenseKey.trim()}
              on:click={activateLicense}
            >
              {activating ? '…' : 'Activate'}
            </button>
          </div>
          {#if activateError}
            <p class="error-text">{activateError}</p>
          {/if}
        {/if}
      </div>
    </section>

    <!-- Sorting section -->
    <section class="section">
      <p class="section-label">Sorting</p>
      <div class="settings-list toggle-list">
        <Toggle
          label="Preview before sorting"
          bind:checked={$sortStore.previewMode}
        />
        <div class="row-divider"></div>
        <Toggle
          label="Watch mode"
          bind:checked={$sortStore.watchMode}
        />
      </div>
    </section>

    <!-- About section -->
    <section class="section">
      <p class="section-label">About</p>
      <div class="settings-list">
        <div class="setting-row">
          <span class="setting-name">Smart Sort</span>
          <span class="setting-value">v0.1.0</span>
        </div>
        <div class="row-divider"></div>
        <div class="setting-row">
          <span class="setting-name">Log folder</span>
          <button class="btn-link" on:click={() => tauriOpenLogFolder()}>
            Open in Finder →
          </button>
        </div>
      </div>
    </section>

  </div>
</ShellLayout>

<style>
  .content {
    padding: 24px;
    width: 100%;
    max-width: 520px;
    display: flex;
    flex-direction: column;
    gap: 24px;
  }

  .section {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .section-label {
    margin: 0;
    font-size: 10px;
    font-weight: 600;
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }

  .settings-list {
    border: 0.5px solid var(--border);
    border-radius: 9px;
    overflow: hidden;
  }

  .toggle-list {
    padding: 4px 14px;
  }

  .row-divider {
    height: 0.5px;
    background: var(--border);
    margin: 0 -14px;
  }

  .setting-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 11px 14px;
    gap: 12px;
  }

  .setting-row + .setting-row {
    border-top: 0.5px solid var(--border);
  }

  .activate-row {
    gap: 8px;
  }

  .setting-name {
    font-size: 13px;
    color: var(--text);
  }

  .setting-value {
    font-size: 12px;
    color: var(--text-secondary);
  }

  .license-badge {
    font-size: 11px;
    font-weight: 500;
    padding: 2px 8px;
    border-radius: 4px;
  }

  .license-badge.pro {
    background: var(--accent-bg);
    color: var(--accent);
    border: 0.5px solid var(--accent);
  }

  .license-badge.trial {
    background: var(--hover-bg);
    color: var(--text-secondary);
    border: 0.5px solid var(--border-strong);
  }

  .key-input {
    flex: 1;
    border: 0.5px solid var(--border-strong);
    border-radius: 6px;
    padding: 7px 10px;
    font-size: 12px;
    font-family: monospace;
    background: var(--bg);
    color: var(--text);
    outline: none;
    min-width: 0;
  }

  .key-input:focus {
    border-color: var(--accent);
  }

  .btn-activate {
    flex-shrink: 0;
    background: var(--text);
    color: var(--bg);
    border: none;
    border-radius: 6px;
    padding: 7px 16px;
    font-size: 12px;
    font-weight: 500;
    cursor: pointer;
  }

  .btn-activate:disabled {
    opacity: 0.35;
    cursor: not-allowed;
  }

  .btn-activate:hover:not(:disabled) {
    opacity: 0.85;
  }

  .btn-link {
    background: none;
    border: none;
    padding: 0;
    font-size: 12px;
    color: var(--accent);
    cursor: pointer;
    font-family: inherit;
  }

  .btn-link:hover {
    text-decoration: underline;
    text-underline-offset: 2px;
  }

  .error-text {
    margin: 0;
    padding: 0 14px 10px;
    font-size: 11px;
    color: var(--error);
  }
</style>
