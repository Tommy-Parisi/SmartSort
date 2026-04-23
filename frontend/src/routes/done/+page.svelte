<script lang="ts">
  import { goto } from '$app/navigation';
  import { onMount } from 'svelte';
  import Logo from '$lib/components/Logo.svelte';
  import StatCard from '$lib/components/StatCard.svelte';
  import FolderRow from '$lib/components/FolderRow.svelte';
  import { sortStore } from '$lib/stores/sort';
  import { tauriUndoSort, tauriStartDaemon } from '$lib/tauri';

  let store = $sortStore;
  $: store = $sortStore;

  let undoing = false;
  let enablingWatch = false;
  let error = '';

  onMount(() => {
    if (!store.folderTree) goto('/');
  });

  function handleRename(e: CustomEvent<{ id: number; name: string }>) {
    sortStore.update(s => ({
      ...s,
      pendingRenames: { ...s.pendingRenames, [e.detail.id]: e.detail.name },
    }));
  }

  async function undoAll() {
    undoing = true;
    error = '';
    try {
      await tauriUndoSort();
      goto('/');
    } catch (e: any) {
      error = typeof e === 'string' ? e : 'Undo failed.';
      undoing = false;
    }
  }

  async function enableWatch() {
    if (!store.selectedFolder) return;
    enablingWatch = true;
    error = '';
    try {
      await tauriStartDaemon([store.selectedFolder]);
      sortStore.update(s => ({ ...s, stage: 'watching' }));
      goto('/watch');
    } catch (e: any) {
      error = typeof e === 'string' ? e : 'Failed to enable watch mode.';
      enablingWatch = false;
    }
  }

  $: sortedFolders = store.folderTree?.folders.filter(f => f.files.length > 0) ?? [];
</script>

<div class="page">
  <div class="logo-row">
    <Logo />
    <span class="done-badge">done</span>
  </div>

  <div class="content">
    <!-- Stat cards -->
    <div class="stats-row">
      <StatCard value={store.filesSorted} label="files sorted" />
      <StatCard value={store.foldersCreated} label="folders created" />
      <StatCard value={store.filesUnsorted} label="not sorted" />
    </div>

    <!-- Actions -->
    <div class="actions">
      <button class="btn-ghost" disabled={undoing} on:click={undoAll}>
        {undoing ? 'Undoing…' : 'Undo all'}
      </button>
      <button class="btn-primary" disabled={enablingWatch} on:click={enableWatch}>
        {enablingWatch ? 'Enabling…' : 'Enable watch mode'}
      </button>
    </div>

    {#if error}
      <p class="error-text">{error}</p>
    {/if}

    <!-- Filesystem sandbox -->
    <div class="sandbox-section">
      <p class="sandbox-label">your folders</p>
      <p class="helper">Click any folder to see what's inside. Click a name to rename.</p>

      <div class="folder-list">
        {#each sortedFolders as folder}
          <FolderRow
            folderId={folder.cluster_id}
            folderName={store.pendingRenames[folder.cluster_id] ?? folder.folder_name}
            files={folder.files}
            editable={true}
            on:rename={handleRename}
          />
        {/each}
      </div>

      {#if store.filesUnsorted > 0}
        <div class="unsorted-note">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
          </svg>
          {store.filesUnsorted} {store.filesUnsorted === 1 ? 'file' : 'files'} stayed in place — not enough similarity to any folder.
        </div>
      {/if}
    </div>
  </div>
</div>

<style>
  .page {
    max-width: 520px;
    margin: 0 auto;
    padding: 0 20px 40px;
  }

  .logo-row {
    position: relative;
    display: flex;
    align-items: flex-start;
    justify-content: center;
  }

  .done-badge {
    position: absolute;
    right: 0;
    top: 36px;
    background: var(--accent-bg);
    color: var(--accent);
    border: 0.5px solid var(--accent);
    border-radius: 4px;
    font-size: 11px;
    font-weight: 600;
    padding: 2px 8px;
  }

  .content {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .stats-row {
    display: flex;
    gap: 8px;
  }

  .actions {
    display: flex;
    gap: 8px;
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

  .btn-ghost:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }

  .btn-ghost:hover:not(:disabled) {
    background: var(--bg-secondary);
  }

  .btn-primary {
    flex: 1;
    padding: 10px;
    background: var(--text);
    color: var(--bg);
    border: none;
    border-radius: 6px;
    font-size: 14px;
    font-weight: 500;
    cursor: pointer;
  }

  .btn-primary:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }

  .btn-primary:hover:not(:disabled) {
    opacity: 0.85;
  }

  .error-text {
    margin: 0;
    font-size: 12px;
    color: var(--error);
  }

  .sandbox-section {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .sandbox-label {
    margin: 0;
    font-size: 11px;
    font-weight: 600;
    text-transform: lowercase;
    letter-spacing: 0.04em;
    color: var(--text-secondary);
  }

  .helper {
    margin: 0;
    font-size: 12px;
    color: var(--text-secondary);
  }

  .folder-list {
    border: 0.5px solid var(--border);
    border-radius: 8px;
    overflow: hidden;
    max-height: 280px;
    overflow-y: auto;
  }

  .unsorted-note {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 12px;
    color: var(--text-secondary);
    padding: 8px 0;
  }
</style>
