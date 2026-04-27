<script lang="ts">
  import { goto } from '$app/navigation';
  import { onMount } from 'svelte';
  import SortFlowLayout from '$lib/components/SortFlowLayout.svelte';
  import StatCard from '$lib/components/StatCard.svelte';
  import FolderRow from '$lib/components/FolderRow.svelte';
  import { sortStore, resetSort } from '$lib/stores/sort';
  import { tauriUndoSort, tauriStartDaemon } from '$lib/tauri';

  let store = $sortStore;
  $: store = $sortStore;

  let undoing = false;
  let enablingWatch = false;
  let error = '';
  let showAll = false;
  const VISIBLE_FOLDERS = 5;

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

  function backToHome() {
    resetSort();
    goto('/');
  }

  $: sortedFolders = store.folderTree?.folders.filter(f => f.files.length > 0) ?? [];
  $: visibleFolders = showAll ? sortedFolders : sortedFolders.slice(0, VISIBLE_FOLDERS);
  $: hiddenCount = sortedFolders.length - VISIBLE_FOLDERS;
  $: folderLabel = store.selectedFolder?.replace(/^.*\//, '') ?? 'folder';
</script>

<SortFlowLayout step={4}>
  <div class="content-area">
    <p class="section-label">{store.selectedFolder ?? 'folder'} sorted</p>

    <!-- Stat cards -->
    <div class="stats-row">
      <StatCard value={store.filesSorted} label="files sorted" />
      <StatCard value={store.foldersCreated} label="folders created" />
      <StatCard value={store.filesUnsorted} label="not sorted" />
    </div>

    <!-- Folder tree -->
    <div class="tree-section">
      <div class="tree-header">
        <span class="tree-label">Your folders</span>
        <span class="tree-hint">Click to expand</span>
      </div>
      <div class="folder-list">
        {#each visibleFolders as folder}
          <FolderRow
            folderId={folder.cluster_id}
            folderName={store.pendingRenames[folder.cluster_id] ?? folder.folder_name}
            files={folder.files}
            editable={true}
            on:rename={handleRename}
          />
        {/each}
        {#if !showAll && hiddenCount > 0}
          <button class="show-more-btn" on:click={() => (showAll = true)}>
            + {hiddenCount} more {hiddenCount === 1 ? 'folder' : 'folders'}
          </button>
        {/if}
        {#if sortedFolders.length === 0}
          <p class="empty-folders">No folders created.</p>
        {/if}
      </div>
    </div>

    {#if error}
      <p class="error-text">{error}</p>
    {/if}
  </div>

  <svelte:fragment slot="footer-left">
    {#if store.filesUnsorted > 0}
      <span class="unsorted-note">
        {store.filesUnsorted} {store.filesUnsorted === 1 ? 'file' : 'files'} stayed in place
      </span>
    {/if}
  </svelte:fragment>

  <svelte:fragment slot="footer-right">
    <button class="btn-ghost" disabled={undoing} on:click={undoAll}>
      {undoing ? 'Undoing…' : 'Undo sort'}
    </button>
    <button class="btn-ghost" disabled={enablingWatch} on:click={enableWatch}>
      {enablingWatch ? 'Enabling…' : 'Enable watch mode'}
    </button>
    <button class="btn-primary" on:click={backToHome}>
      ← Back to home
    </button>
  </svelte:fragment>
</SortFlowLayout>

<style>
  .content-area {
    flex: 1;
    overflow-y: auto;
    padding: 24px;
    display: flex;
    flex-direction: column;
    gap: 16px;
    max-width: 580px;
  }

  .section-label {
    margin: 0;
    font-size: 10px;
    font-weight: 600;
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.06em;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .stats-row {
    display: flex;
    gap: 8px;
  }

  .tree-section {
    border: 0.5px solid var(--border);
    border-radius: 9px;
    overflow: hidden;
  }

  .tree-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 9px 14px;
    border-bottom: 0.5px solid var(--border);
    background: var(--bg-secondary);
  }

  .tree-label {
    font-size: 11px;
    font-weight: 500;
    color: var(--text);
  }

  .tree-hint {
    font-size: 11px;
    color: var(--text-secondary);
  }

  .folder-list {
    max-height: 260px;
    overflow-y: auto;
  }

  .show-more-btn {
    display: block;
    width: 100%;
    padding: 9px 14px;
    background: none;
    border: none;
    border-top: 0.5px solid var(--border);
    font-size: 12px;
    color: var(--text-secondary);
    cursor: pointer;
    text-align: left;
    font-family: inherit;
  }

  .show-more-btn:hover {
    background: var(--bg-secondary);
    color: var(--text);
  }

  .empty-folders {
    margin: 0;
    padding: 16px;
    font-size: 12px;
    color: var(--text-secondary);
    text-align: center;
  }

  .error-text {
    margin: 0;
    font-size: 11px;
    color: var(--error);
  }

  /* Footer */
  .unsorted-note {
    font-size: 11px;
    color: var(--text-secondary);
  }

  .btn-ghost {
    background: none;
    border: 0.5px solid var(--border-strong);
    border-radius: 6px;
    padding: 8px 16px;
    font-size: 12px;
    cursor: pointer;
    color: var(--text);
    white-space: nowrap;
  }

  .btn-ghost:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }

  .btn-ghost:hover:not(:disabled) {
    background: var(--bg-secondary);
  }

  .btn-primary {
    padding: 8px 18px;
    background: var(--text);
    color: var(--bg);
    border: none;
    border-radius: 6px;
    font-size: 12px;
    font-weight: 500;
    cursor: pointer;
    white-space: nowrap;
  }

  .btn-primary:hover {
    opacity: 0.85;
  }
</style>
