<script lang="ts">
  import { goto } from '$app/navigation';
  import { onMount } from 'svelte';
  import Logo from '$lib/components/Logo.svelte';
  import FolderRow from '$lib/components/FolderRow.svelte';
  import { sortStore } from '$lib/stores/sort';
  import type { PreviewFolder, PreviewFile } from '$lib/stores/sort';
  import { tauriConfirmSort, tauriReassignFiles } from '$lib/tauri';

  let store = $sortStore;
  $: store = $sortStore;

  // ── Editor state ──────────────────────────────────────────────────────────

  let previewFolders: PreviewFolder[] = [];
  let unsortedFiles: PreviewFile[] = [];
  let highlightedIds = new Set<number>();
  let newFolderEditingId: number | null = null;

  // ── Confirmation state ────────────────────────────────────────────────────

  let confirming = false;
  let error = '';

  // ── Unsorted section move dropdown state ─────────────────────────────────

  let openUnsortedMoveFile: string | null = null;

  // ── Stats ─────────────────────────────────────────────────────────────────

  $: totalFiles   = previewFolders.reduce((s, f) => s + f.files.length, 0) + unsortedFiles.length;
  $: totalFolders = previewFolders.length;

  // ── Initialise from folderTree ────────────────────────────────────────────

  onMount(() => {
    if (!store.folderTree) { goto('/'); return; }

    const rawFolders = store.folderTree.folders;

    previewFolders = rawFolders
      .filter(f => f.cluster_id !== -1 && f.folder_name !== 'Unsorted')
      .map(f => ({
        cluster_id: f.cluster_id,
        name: store.pendingRenames[f.cluster_id] ?? f.folder_name,
        files: f.files.map(file => ({
          filename: file.name,
          ext: file.extension.replace(/^\./, '').toLowerCase(),
          originalClusterId: f.cluster_id,
          currentClusterId: f.cluster_id,
        })),
      }));

    const unsorted = rawFolders.find(f => f.cluster_id === -1 || f.folder_name === 'Unsorted');
    unsortedFiles = (unsorted?.files ?? []).map(file => ({
      filename: file.name,
      ext: file.extension.replace(/^\./, '').toLowerCase(),
      originalClusterId: -1,
      currentClusterId: null,
    }));
  });

  // ── Rename handler ────────────────────────────────────────────────────────

  function handleRename(e: CustomEvent<{ id: number; name: string }>) {
    const { id, name } = e.detail;
    previewFolders = previewFolders.map(f =>
      f.cluster_id === id ? { ...f, name } : f
    );
    if (newFolderEditingId === id) newFolderEditingId = null;
  }

  // ── Delete + reassign handler ─────────────────────────────────────────────

  async function handleDelete(e: CustomEvent<{ id: number }>) {
    const { id } = e.detail;
    const target = previewFolders.find(f => f.cluster_id === id);
    if (!target) return;

    try {
      const filenames = target.files.map(f => f.filename);
      const assignments = await tauriReassignFiles(filenames, id);

      const newHighlights = new Set<number>();
      const addedToUnsorted: PreviewFile[] = [];

      previewFolders = previewFolders
        .filter(f => f.cluster_id !== id)
        .map(f => {
          const incoming = assignments.filter(a => a.cluster_id === f.cluster_id);
          if (incoming.length === 0) return f;
          newHighlights.add(f.cluster_id);
          return {
            ...f,
            files: [
              ...f.files,
              ...incoming.map(a => ({
                filename: a.filename,
                ext: a.filename.split('.').pop()?.toLowerCase() ?? '',
                originalClusterId: id,
                currentClusterId: f.cluster_id,
              })),
            ],
          };
        });

      for (const a of assignments.filter(a => a.cluster_id === -1)) {
        addedToUnsorted.push({
          filename: a.filename,
          ext: a.filename.split('.').pop()?.toLowerCase() ?? '',
          originalClusterId: id,
          currentClusterId: null,
        });
      }
      if (addedToUnsorted.length > 0) {
        unsortedFiles = [...unsortedFiles, ...addedToUnsorted];
      }

      if (newHighlights.size > 0) {
        highlightedIds = newHighlights;
        setTimeout(() => { highlightedIds = new Set(); }, 700);
      }
    } catch {
      // Backend unavailable — move all files to unsorted, remove folder
      unsortedFiles = [
        ...unsortedFiles,
        ...target.files.map(f => ({ ...f, currentClusterId: null })),
      ];
      previewFolders = previewFolders.filter(f => f.cluster_id !== id);
    }
  }

  // ── Move file between folders ─────────────────────────────────────────────

  function handleMoveFile(e: CustomEvent<{ filename: string; fromId: number; toId: number | null }>) {
    const { filename, fromId, toId } = e.detail;

    let moved: PreviewFile | undefined;
    previewFolders = previewFolders.map(f => {
      if (f.cluster_id !== fromId) return f;
      moved = f.files.find(pf => pf.filename === filename);
      return { ...f, files: f.files.filter(pf => pf.filename !== filename) };
    });
    if (!moved) return;

    const updated: PreviewFile = { ...moved, currentClusterId: toId };
    if (toId === null) {
      unsortedFiles = [...unsortedFiles, updated];
    } else {
      previewFolders = previewFolders.map(f =>
        f.cluster_id === toId ? { ...f, files: [...f.files, updated] } : f
      );
    }
  }

  // ── Move from unsorted ────────────────────────────────────────────────────

  function moveUnsortedFile(filename: string, val: string) {
    openUnsortedMoveFile = null;
    if (!val || val === 'unsorted') return;
    const toId = parseInt(val);
    const file = unsortedFiles.find(f => f.filename === filename);
    if (!file) return;
    unsortedFiles = unsortedFiles.filter(f => f.filename !== filename);
    previewFolders = previewFolders.map(f =>
      f.cluster_id === toId
        ? { ...f, files: [...f.files, { ...file, currentClusterId: toId }] }
        : f
    );
  }

  // ── New folder ────────────────────────────────────────────────────────────

  function addNewFolder() {
    const id = Date.now();
    previewFolders = [
      ...previewFolders,
      { cluster_id: id, name: 'New Folder', files: [], isNew: true },
    ];
    newFolderEditingId = id;
  }

  // ── Confirm ───────────────────────────────────────────────────────────────

  async function confirmSort() {
    confirming = true;
    error = '';
    try {
      await tauriConfirmSort(previewFolders);
      sortStore.update(s => ({ ...s, stage: 'done' }));
      goto('/done');
    } catch (e: any) {
      error = typeof e === 'string' ? e : 'Failed to move files.';
      confirming = false;
    }
  }
</script>

<div class="page">
  <Logo subtitle="{totalFolders} folders · {totalFiles} files" />

  <div class="content">
    <p class="helper">Review before anything moves. Click a name to rename, × to delete a folder.</p>

    <!-- ── Folder list ─────────────────────────────────────────────────── -->
    <div class="folder-list">
      {#each previewFolders as folder (folder.cluster_id)}
        <FolderRow
          {folder}
          allFolders={previewFolders}
          highlighted={highlightedIds.has(folder.cluster_id)}
          autoFocus={newFolderEditingId === folder.cluster_id}
          on:rename={handleRename}
          on:delete={handleDelete}
          on:movefile={handleMoveFile}
        />
      {/each}
    </div>

    <!-- ── + New folder ───────────────────────────────────────────────── -->
    <button class="btn-new-folder" type="button" on:click={addNewFolder}>
      + New folder
    </button>

    <!-- ── Unsorted section ───────────────────────────────────────────── -->
    {#if unsortedFiles.length > 0}
      <div class="unsorted-section">
        <p class="unsorted-header">Unsorted · {unsortedFiles.length} files</p>
        <div class="unsorted-file-list">
          {#each unsortedFiles as file (file.filename)}
            <div class="file-row">
              <span class="ext-badge">{file.ext || '?'}</span>
              <span class="file-name">{file.filename}</span>
              {#if openUnsortedMoveFile === file.filename}
                <select
                  class="move-select"
                  on:change={e => moveUnsortedFile(file.filename, (e.target as HTMLSelectElement).value)}
                  on:blur={() => (openUnsortedMoveFile = null)}
                >
                  <option value="" disabled selected>Move to…</option>
                  {#each previewFolders as dest}
                    <option value={String(dest.cluster_id)}>{dest.name}</option>
                  {/each}
                </select>
              {:else}
                <button
                  class="move-btn"
                  type="button"
                  title="Move file"
                  on:click={() => (openUnsortedMoveFile = file.filename)}
                >→</button>
              {/if}
            </div>
          {/each}
        </div>
      </div>
    {/if}

    {#if error}
      <p class="error-text">{error}</p>
    {/if}

    <!-- ── Actions ────────────────────────────────────────────────────── -->
    <div class="actions">
      <button class="btn-ghost" on:click={() => goto('/')}>Back</button>
      <button class="btn-primary" disabled={confirming} on:click={confirmSort}>
        {confirming ? 'Moving…' : 'Move files'}
      </button>
    </div>
  </div>
</div>

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

  .helper {
    margin: 0;
    font-size: 12px;
    color: var(--text-secondary);
  }

  /* ── Folder list ── */
  .folder-list {
    border: 0.5px solid var(--border);
    border-radius: 8px;
    overflow: hidden;
    max-height: 360px;
    overflow-y: auto;
  }

  /* ── New folder button ── */
  .btn-new-folder {
    align-self: flex-start;
    background: none;
    border: 0.5px dashed var(--border-strong);
    border-radius: 6px;
    padding: 6px 14px;
    font-size: 12px;
    color: var(--text-secondary);
    cursor: pointer;
    transition: background 100ms, color 100ms;
  }
  .btn-new-folder:hover {
    background: var(--bg-secondary);
    color: var(--text);
  }

  /* ── Unsorted section ── */
  .unsorted-section {
    border: 0.5px solid var(--border);
    border-radius: 8px;
    overflow: hidden;
  }

  .unsorted-header {
    margin: 0;
    padding: 8px 12px;
    font-size: 11px;
    font-weight: 600;
    color: var(--text-secondary);
    text-transform: lowercase;
    letter-spacing: 0.03em;
    border-bottom: 0.5px solid var(--border);
  }

  .unsorted-file-list {
    padding: 4px 12px 8px 12px;
    background: var(--bg-secondary);
    max-height: 180px;
    overflow-y: auto;
  }

  /* ── Shared file row (unsorted section) ── */
  .file-row {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 4px 0;
    border-radius: 4px;
    transition: background 100ms;
  }
  .file-row:hover {
    background: var(--bg-secondary);
  }

  .ext-badge {
    font-size: 10px;
    font-weight: 600;
    padding: 1px 5px;
    border-radius: 3px;
    background: #F1EFE8;
    color: #444441;
    text-transform: lowercase;
    flex-shrink: 0;
    min-width: 28px;
    text-align: center;
  }

  .file-name {
    flex: 1;
    font-size: 12px;
    color: var(--text);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .move-btn {
    opacity: 0;
    transition: opacity 100ms;
    font-size: 12px;
    color: var(--text-secondary);
    background: none;
    border: none;
    cursor: pointer;
    padding: 2px 4px;
    flex-shrink: 0;
  }
  .file-row:hover .move-btn {
    opacity: 1;
  }

  .move-select {
    font-size: 12px;
    border: 0.5px solid var(--border-strong);
    border-radius: 4px;
    background: var(--bg);
    color: var(--text);
    padding: 2px 4px;
    outline: none;
    cursor: pointer;
    flex-shrink: 0;
  }

  /* ── Error ── */
  .error-text {
    margin: 0;
    font-size: 12px;
    color: var(--error);
  }

  /* ── Actions ── */
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
  .btn-ghost:hover {
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
</style>
