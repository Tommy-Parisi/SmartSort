<script lang="ts">
  import { goto } from '$app/navigation';
  import { open } from '@tauri-apps/plugin-dialog';
  import Logo from '$lib/components/Logo.svelte';
  import Toggle from '$lib/components/Toggle.svelte';
  import TrialBanner from '$lib/components/TrialBanner.svelte';
  import { sortStore, resetSort } from '$lib/stores/sort';
  import { tauriGetLicenseStatus } from '$lib/tauri';
  import { onMount } from 'svelte';

  let store = $sortStore;
  $: store = $sortStore;

  let isDragOver = false;
  let showActivateModal = false;
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
    } catch {
      // backend not running in dev — leave defaults
    }
  });

  async function pickFolder() {
    try {
      const picked = await open({ directory: true, multiple: false });
      if (picked && typeof picked === 'string') {
        sortStore.update(s => ({ ...s, selectedFolder: picked }));
      }
    } catch (e) {
      console.error(e);
    }
  }

  function handleDragOver(e: DragEvent) {
    e.preventDefault();
    isDragOver = true;
  }

  function handleDragLeave(e: DragEvent) {
    e.preventDefault();
    isDragOver = false;
  }

  function handleDrop(e: DragEvent) {
    e.preventDefault();
    isDragOver = false;
    const items = e.dataTransfer?.items;
    if (!items) return;
    for (let i = 0; i < items.length; i++) {
      const entry = items[i].webkitGetAsEntry?.();
      if (entry?.isDirectory) {
        sortStore.update(s => ({ ...s, selectedFolder: (entry as any).fullPath }));
        break;
      }
    }
  }

  function startSort() {
    if (!store.selectedFolder) return;
    resetSort();
    sortStore.update(s => ({ ...s, stage: 'processing' }));
    goto('/processing');
  }

  async function activateLicense() {
    if (!licenseKey.trim()) return;
    activating = true;
    activateError = '';
    try {
      const { tauriActivateLicense, tauriGetLicenseStatus } = await import('$lib/tauri');
      await tauriActivateLicense(licenseKey.trim());
      const status = await tauriGetLicenseStatus();
      sortStore.update(s => ({
        ...s,
        licenseValid: status.valid,
        licenseTrial: status.trial,
        filesRemaining: status.filesRemaining,
      }));
      showActivateModal = false;
      licenseKey = '';
    } catch (e: any) {
      activateError = typeof e === 'string' ? e : 'Invalid license key.';
    } finally {
      activating = false;
    }
  }
</script>

<div class="page">
  <Logo subtitle="Organize your files with one click" />

  <div class="content">
    <!-- Drop zone -->
    <div
      class="dropzone {isDragOver ? 'drag-over' : ''} {store.selectedFolder ? 'selected' : ''}"
      on:click={pickFolder}
      on:dragover={handleDragOver}
      on:dragleave={handleDragLeave}
      on:drop={handleDrop}
      role="button"
      tabindex="0"
      on:keydown={e => e.key === 'Enter' && pickFolder()}
      aria-label="Select or drop a folder"
    >
      <svg class="drop-icon" width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
        <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
      </svg>
      {#if store.selectedFolder}
        <p class="drop-main">{store.selectedFolder.split('/').pop() || store.selectedFolder}</p>
        <p class="drop-sub">{store.selectedFolder}</p>
        <p class="drop-hint">Click to change folder</p>
      {:else}
        <p class="drop-main">Drop a folder here</p>
        <p class="drop-hint">or click to browse</p>
      {/if}
    </div>

    <!-- Trial banner -->
    {#if store.licenseTrial && !store.licenseValid}
      <TrialBanner filesRemaining={store.filesRemaining} on:activate={() => (showActivateModal = true)} />
    {/if}

    <!-- Settings -->
    <div class="settings">
      <Toggle
        label="Watch mode — keep this folder sorted automatically"
        bind:checked={$sortStore.watchMode}
      />
      <div class="divider"></div>
      <Toggle
        label="Preview before sorting — review folders before files move"
        bind:checked={$sortStore.previewMode}
      />
    </div>

    <!-- CTA -->
    <button
      class="btn-primary"
      disabled={!store.selectedFolder}
      on:click={startSort}
    >
      Sort folder
    </button>
  </div>
</div>

<!-- Activate modal -->
{#if showActivateModal}
  <div class="modal-backdrop" on:click|self={() => (showActivateModal = false)} on:keydown={e => e.key === 'Escape' && (showActivateModal = false)} role="dialog" aria-modal="true" tabindex="-1">
    <div class="modal">
      <h2>Activate license</h2>
      <p class="modal-desc">Enter your license key to unlock unlimited sorting.</p>
      <input
        class="key-input"
        type="text"
        placeholder="XXXX-XXXX-XXXX-XXXX"
        bind:value={licenseKey}
        on:keydown={e => e.key === 'Enter' && activateLicense()}
      />
      {#if activateError}
        <p class="error-text">{activateError}</p>
      {/if}
      <div class="modal-actions">
        <button class="btn-ghost" on:click={() => (showActivateModal = false)}>Cancel</button>
        <button class="btn-primary" disabled={activating || !licenseKey.trim()} on:click={activateLicense}>
          {activating ? 'Activating…' : 'Activate'}
        </button>
      </div>
    </div>
  </div>
{/if}

<style>
  .page {
    max-width: 520px;
    margin: 0 auto;
    padding: 0 20px 40px;
  }

  .content {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  /* Drop zone */
  .dropzone {
    border: 1.5px dashed var(--border-strong);
    border-radius: 8px;
    padding: 40px 24px;
    text-align: center;
    cursor: pointer;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 6px;
    transition: border-color 0.15s, background 0.15s;
  }

  .dropzone:hover,
  .dropzone.drag-over {
    border-color: var(--text);
    background: var(--bg-secondary);
  }

  .dropzone.selected {
    border-style: solid;
    border-color: var(--accent);
  }

  .drop-icon {
    color: var(--text-secondary);
    margin-bottom: 4px;
  }

  .dropzone.selected .drop-icon {
    color: var(--accent);
  }

  .drop-main {
    margin: 0;
    font-size: 14px;
    font-weight: 500;
    color: var(--text);
    word-break: break-all;
  }

  .drop-sub {
    margin: 0;
    font-size: 11px;
    color: var(--text-secondary);
    word-break: break-all;
  }

  .drop-hint {
    margin: 0;
    font-size: 12px;
    color: var(--text-secondary);
  }

  /* Settings */
  .settings {
    border: 0.5px solid var(--border);
    border-radius: 8px;
    padding: 4px 16px;
  }

  .divider {
    height: 0.5px;
    background: var(--border);
    margin: 0 -16px;
  }

  /* Buttons */
  .btn-primary {
    width: 100%;
    padding: 12px;
    background: var(--text);
    color: var(--bg);
    border: none;
    border-radius: 6px;
    font-size: 14px;
    font-weight: 500;
    cursor: pointer;
    transition: opacity 0.15s;
  }

  .btn-primary:disabled {
    opacity: 0.3;
    cursor: not-allowed;
  }

  .btn-primary:hover:not(:disabled) {
    opacity: 0.85;
  }

  .btn-ghost {
    background: none;
    border: 0.5px solid var(--border-strong);
    border-radius: 6px;
    padding: 10px 20px;
    font-size: 14px;
    cursor: pointer;
    color: var(--text);
  }

  .btn-ghost:hover {
    background: var(--bg-secondary);
  }

  /* Modal */
  .modal-backdrop {
    position: fixed;
    inset: 0;
    background: rgba(0,0,0,0.4);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 100;
  }

  .modal {
    background: var(--bg);
    border: 0.5px solid var(--border-strong);
    border-radius: 10px;
    padding: 28px 24px;
    width: 340px;
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .modal h2 {
    margin: 0;
    font-size: 16px;
    font-weight: 600;
  }

  .modal-desc {
    margin: 0;
    font-size: 13px;
    color: var(--text-secondary);
  }

  .key-input {
    border: 0.5px solid var(--border-strong);
    border-radius: 6px;
    padding: 10px 12px;
    font-size: 14px;
    width: 100%;
    outline: none;
    background: var(--bg);
    color: var(--text);
    font-family: monospace;
  }

  .key-input:focus {
    border-color: var(--accent);
  }

  .error-text {
    margin: 0;
    font-size: 12px;
    color: var(--error);
  }

  .modal-actions {
    display: flex;
    gap: 8px;
    justify-content: flex-end;
    margin-top: 4px;
  }

  .modal-actions .btn-primary {
    width: auto;
    padding: 10px 20px;
  }
</style>
