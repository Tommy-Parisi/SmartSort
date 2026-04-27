<script lang="ts">
  import { goto } from '$app/navigation';
  import { open } from '@tauri-apps/plugin-dialog';
  import ShellLayout from '$lib/components/ShellLayout.svelte';
  import Toggle from '$lib/components/Toggle.svelte';
  import TrialBanner from '$lib/components/TrialBanner.svelte';
  import { sortStore, resetSort } from '$lib/stores/sort';
  import { tauriGetLicenseStatus, tauriGetHistory, tauriActivateLicense, type SortSession } from '$lib/tauri';
  import { onMount } from 'svelte';

  let store = $sortStore;
  $: store = $sortStore;

  let isDragOver = false;
  let showActivateModal = false;
  let licenseKey = '';
  let activateError = '';
  let activating = false;
  let recentSessions: SortSession[] = [];
  let historyLoading = true;

  onMount(async () => {
    try {
      const [status, history] = await Promise.all([
        tauriGetLicenseStatus(),
        tauriGetHistory(),
      ]);
      sortStore.update(s => ({
        ...s,
        licenseValid: status.valid,
        licenseTrial: status.trial,
        filesRemaining: status.filesRemaining,
      }));
      recentSessions = history;
    } catch {
      // backend not running in dev
    } finally {
      historyLoading = false;
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
    sortStore.update(s => ({ ...s, selectedFolder: store.selectedFolder, stage: 'processing' }));
    goto('/processing');
  }

  async function activateLicense() {
    if (!licenseKey.trim()) return;
    activating = true;
    activateError = '';
    try {
      await tauriActivateLicense(licenseKey.trim());
      const { tauriGetLicenseStatus: getStatus } = await import('$lib/tauri');
      const status = await getStatus();
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

  function folderBasename(path: string): string {
    return path.split('/').pop() || path;
  }
</script>

<ShellLayout>
  <div class="content">
    <p class="section-label">New sort</p>

    <!-- Drop zone -->
    <div
      class="dropzone"
      class:drag-over={isDragOver}
      class:selected={!!store.selectedFolder}
      on:click={pickFolder}
      on:dragover={handleDragOver}
      on:dragleave={handleDragLeave}
      on:drop={handleDrop}
      role="button"
      tabindex="0"
      on:keydown={e => e.key === 'Enter' && pickFolder()}
      aria-label="Select or drop a folder"
    >
      <svg class="drop-icon" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
        <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
      </svg>
      {#if store.selectedFolder}
        <p class="drop-main">{folderBasename(store.selectedFolder)}</p>
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

    <!-- Toggles -->
    <div class="toggles">
      <Toggle
        label="Watch mode — keep this folder sorted automatically"
        bind:checked={$sortStore.watchMode}
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

    <!-- Recent sorts -->
    <div class="recent-section">
      <p class="section-label">Recent</p>

      {#if historyLoading}
        <p class="empty-hint">Loading…</p>
      {:else if recentSessions.length === 0}
        <p class="empty-hint">No sorts yet. Drop a folder above to get started.</p>
      {:else}
        <div class="recent-list">
          {#each recentSessions as session}
            <div class="recent-row">
              <svg class="recent-icon" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7">
                <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
              </svg>
              <span class="recent-folder">{folderBasename(session.folder)}</span>
              <span class="recent-date">{session.date}</span>
              <span class="recent-stats">{session.files_sorted} files</span>
              <span class="recent-badge">{session.folders_created} folders</span>
            </div>
          {/each}
        </div>
      {/if}
    </div>
  </div>
</ShellLayout>

<!-- Activate modal -->
{#if showActivateModal}
  <div class="modal-backdrop"
    on:click|self={() => (showActivateModal = false)}
    on:keydown={e => e.key === 'Escape' && (showActivateModal = false)}
    role="dialog" aria-modal="true" tabindex="-1"
  >
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
        <button class="btn-primary-sm" disabled={activating || !licenseKey.trim()} on:click={activateLicense}>
          {activating ? 'Activating…' : 'Activate'}
        </button>
      </div>
    </div>
  </div>
{/if}

<style>
  .content {
    padding: 48px 0 40px;
    width: 100%;
    max-width: 460px;
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  .section-label {
    margin: 0 0 4px;
    font-size: 10px;
    font-weight: 600;
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }

  /* Drop zone */
  .dropzone {
    border: 1px dashed var(--border-strong);
    border-radius: 10px;
    padding: 32px 24px;
    text-align: center;
    cursor: pointer;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 5px;
    background: var(--bg);
    transition: border-color 0.15s, background 0.15s;
  }

  .dropzone:hover,
  .dropzone.drag-over {
    border-color: var(--text-secondary);
    background: var(--bg-secondary);
  }

  .dropzone.selected {
    border-style: solid;
    border-color: var(--accent);
    border-width: 1.5px;
  }

  .drop-icon {
    opacity: 0.2;
    margin-bottom: 4px;
  }

  .dropzone.selected .drop-icon {
    opacity: 0.6;
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

  /* Toggles */
  .toggles {
    border: 1px solid var(--border-strong);
    border-radius: 8px;
    padding: 4px 14px;
  }

  .toggle-divider {
    height: 0.5px;
    background: var(--border);
    margin: 0 -14px;
  }

  /* Buttons */
  .btn-primary {
    width: 100%;
    padding: 11px;
    background: var(--text);
    color: var(--bg);
    border: none;
    border-radius: 6px;
    font-size: 13px;
    font-weight: 500;
    cursor: pointer;
    transition: opacity 0.15s;
  }

  .btn-primary:disabled {
    background: var(--btn-disabled-bg);
    color: var(--btn-disabled-text);
    cursor: not-allowed;
  }

  .btn-primary:hover:not(:disabled) {
    opacity: 0.85;
  }

  /* Recent section */
  .recent-section {
    margin-top: 10px;
  }

  .empty-hint {
    margin: 0;
    font-size: 12px;
    color: var(--text-secondary);
    padding: 8px 0;
  }

  .recent-list {
    border: 1px solid var(--border-strong);
    border-radius: 8px;
    overflow: hidden;
  }

  .recent-row {
    display: flex;
    align-items: center;
    gap: 7px;
    padding: 8px 12px;
    border-bottom: 1px solid var(--border-strong);
    font-size: 12px;
  }

  .recent-row:last-child {
    border-bottom: none;
  }

  .recent-row:hover {
    background: var(--bg-secondary);
  }

  .recent-icon {
    color: var(--text-secondary);
    flex-shrink: 0;
    opacity: 0.5;
  }

  .recent-folder {
    font-weight: 500;
    color: var(--text);
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .recent-date {
    color: var(--text-secondary);
    flex-shrink: 0;
    font-size: 11px;
  }

  .recent-stats {
    color: var(--text-secondary);
    flex-shrink: 0;
    font-size: 11px;
  }

  .recent-badge {
    background: var(--bg-secondary);
    border: 0.5px solid var(--border);
    border-radius: 4px;
    padding: 1px 6px;
    font-size: 10px;
    color: var(--text-secondary);
    flex-shrink: 0;
    white-space: nowrap;
  }

  /* Modal */
  .modal-backdrop {
    position: fixed;
    inset: 0;
    background: rgba(0,0,0,0.35);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 100;
  }

  .modal {
    background: var(--bg);
    border: 0.5px solid var(--border-strong);
    border-radius: 10px;
    padding: 24px;
    width: 340px;
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  .modal h2 {
    margin: 0;
    font-size: 15px;
    font-weight: 500;
  }

  .modal-desc {
    margin: 0;
    font-size: 12px;
    color: var(--text-secondary);
  }

  .key-input {
    border: 0.5px solid var(--border-strong);
    border-radius: 6px;
    padding: 9px 12px;
    font-size: 13px;
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
    font-size: 11px;
    color: var(--error);
  }

  .modal-actions {
    display: flex;
    gap: 8px;
    justify-content: flex-end;
    margin-top: 4px;
  }

  .btn-ghost {
    background: none;
    border: 0.5px solid var(--border-strong);
    border-radius: 6px;
    padding: 8px 18px;
    font-size: 13px;
    cursor: pointer;
    color: var(--text);
  }

  .btn-ghost:hover {
    background: var(--bg-secondary);
  }

  .btn-primary-sm {
    padding: 8px 18px;
    background: var(--text);
    color: var(--bg);
    border: none;
    border-radius: 6px;
    font-size: 13px;
    font-weight: 500;
    cursor: pointer;
  }

  .btn-primary-sm:disabled {
    opacity: 0.35;
    cursor: not-allowed;
  }

  .btn-primary-sm:hover:not(:disabled) {
    opacity: 0.85;
  }
</style>
