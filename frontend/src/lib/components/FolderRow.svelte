<script lang="ts">
  import { createEventDispatcher, onMount, tick } from 'svelte';
  import FileItem from './FileItem.svelte';
  import type { FileEntry, PreviewFolder, PreviewFile } from '../stores/sort';

  // ── New preview-editor props ───────────────────────────────────────────────
  export let folder: PreviewFolder | undefined = undefined;
  export let allFolders: PreviewFolder[] = [];
  export let highlighted = false;
  export let autoFocus = false;

  // ── Legacy props (done page — kept for compatibility) ─────────────────────
  export let folderId: number = 0;
  export let folderName: string = '';
  export let files: FileEntry[] = [];
  export let editable = false;

  const dispatch = createEventDispatcher<{
    rename:   { id: number; name: string };
    delete:   { id: number };
    movefile: { filename: string; fromId: number; toId: number | null };
  }>();

  // ── Derived mode ──────────────────────────────────────────────────────────
  $: isPreview = folder !== undefined;
  $: _id   = isPreview ? folder!.cluster_id : folderId;
  $: _name = isPreview ? folder!.name : folderName;

  // ── Local state ───────────────────────────────────────────────────────────
  let expanded    = false;
  let editing     = false;
  let editValue   = '';
  let reassigning = false;            // local — set on delete click
  let openMoveFile: string | null = null;

  // ── Flash animation ───────────────────────────────────────────────────────
  let flashActive = false;
  let prevHighlighted = false;
  let flashTimer: ReturnType<typeof setTimeout>;

  $: {
    if (highlighted && !prevHighlighted) {
      flashActive = true;
      clearTimeout(flashTimer);
      flashTimer = setTimeout(() => { flashActive = false; }, 600);
    }
    prevHighlighted = highlighted;
  }

  onMount(() => { if (autoFocus) startEdit(); });

  // ── Actions ───────────────────────────────────────────────────────────────

  function focusNode(node: HTMLElement) {
    tick().then(() => node.focus());
  }

  function startEdit() {
    editing   = true;
    editValue = _name;
  }

  function commitEdit() {
    editing = false;
    if (editValue.trim() && editValue.trim() !== _name) {
      dispatch('rename', { id: _id, name: editValue.trim() });
    }
  }

  function onKeydown(e: KeyboardEvent) {
    if (e.key === 'Enter')  commitEdit();
    if (e.key === 'Escape') { editing = false; editValue = _name; }
  }

  function handleDelete(e: MouseEvent) {
    e.stopPropagation();
    reassigning = true;
    dispatch('delete', { id: _id });
  }

  function handleMoveSelect(file: PreviewFile, e: Event) {
    const val = (e.target as HTMLSelectElement).value;
    openMoveFile = null;
    if (!val) return;
    const toId = val === 'unsorted' ? null : parseInt(val);
    dispatch('movefile', { filename: file.filename, fromId: _id, toId });
  }
</script>

<div class="folder-row" class:flash={flashActive}>
  <!-- ── Row header ──────────────────────────────────────────────────────── -->
  <div
    class="row-header"
    role="button"
    tabindex="0"
    on:click={() => !editing && (expanded = !expanded)}
    on:keydown={e => e.key === 'Enter' && !editing && (expanded = !expanded)}
  >
    {#if isPreview}
      <button class="icon-btn delete-btn" type="button" title="Delete folder" on:click={handleDelete} tabindex="-1">×</button>
    {/if}

    <svg class="folder-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
      <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
    </svg>

    {#if editing}
      <input
        class="name-input"
        bind:value={editValue}
        on:blur={commitEdit}
        on:keydown={onKeydown}
        on:click|stopPropagation
        use:focusNode
      />
    {:else if editable || isPreview}
      <button class="name editable" type="button" on:click|stopPropagation={startEdit}>{_name}</button>
    {:else}
      <span class="name">{_name}</span>
    {/if}

    {#if reassigning}
      <div class="reassigning">
        <div class="spinner"></div>
        <span class="reassigning-label">re-sorting {folder?.files.length ?? 0} files…</span>
      </div>
    {:else}
      <span class="count">{isPreview ? folder!.files.length : files.length}</span>
    {/if}

    <svg class="chevron" class:open={expanded} width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <polyline points="6,9 12,15 18,9"/>
    </svg>
  </div>

  <!-- ── File list ──────────────────────────────────────────────────────── -->
  {#if expanded}
    <div class="file-list">
      {#if isPreview}
        {#each folder!.files as file (file.filename)}
          <div class="file-row">
            <span class="ext-badge">{file.ext || '?'}</span>
            <span class="file-name">{file.filename}</span>
            {#if openMoveFile === file.filename}
              <select
                class="move-select"
                on:change={e => handleMoveSelect(file, e)}
                on:blur={() => (openMoveFile = null)}
                use:focusNode
              >
                <option value="" disabled selected>Move to…</option>
                {#each allFolders.filter(f => f.cluster_id !== _id) as dest}
                  <option value={String(dest.cluster_id)}>{dest.name}</option>
                {/each}
                <option value="unsorted">Unsorted</option>
              </select>
            {:else}
              <button
                class="icon-btn move-btn"
                type="button"
                title="Move file"
                on:click|stopPropagation={() => (openMoveFile = file.filename)}
              >→</button>
            {/if}
          </div>
        {/each}
        {#if folder!.files.length === 0}
          <p class="empty-note">No files</p>
        {/if}
      {:else}
        {#each files as file}
          <FileItem name={file.name} extension={file.extension} />
        {/each}
      {/if}
    </div>
  {/if}
</div>

<style>
  .folder-row {
    border-bottom: 0.5px solid var(--border);
  }

  /* ── Flash animation ── */
  @keyframes flash-green {
    0%   { background: #E1F5EE; }
    100% { background: transparent; }
  }
  .folder-row.flash .row-header {
    animation: flash-green 600ms ease forwards;
  }

  /* ── Row header ── */
  .row-header {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 10px 12px;
    cursor: pointer;
    user-select: none;
    transition: background 100ms;
  }

  .row-header:hover {
    background: var(--bg-secondary);
  }

  /* ── Delete button (hidden until hover) ── */
  .delete-btn {
    opacity: 0;
    transition: opacity 100ms;
    font-size: 14px;
    line-height: 1;
    color: var(--text-secondary);
    padding: 0 2px;
  }
  .row-header:hover .delete-btn {
    opacity: 1;
  }

  /* ── Shared icon button reset ── */
  .icon-btn {
    background: none;
    border: none;
    cursor: pointer;
    flex-shrink: 0;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .folder-icon {
    color: var(--text-secondary);
    flex-shrink: 0;
  }

  .name {
    flex: 1;
    font-size: 13px;
    color: var(--text);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  button.name {
    background: none;
    border: none;
    padding: 0;
    text-align: left;
    font-family: inherit;
    font-size: 13px;
    color: var(--text);
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .name.editable:hover {
    text-decoration: underline;
    text-underline-offset: 2px;
    cursor: text;
  }

  .name-input {
    flex: 1;
    border: none;
    border-bottom: 1px solid var(--accent);
    background: transparent;
    font-size: 13px;
    color: var(--text);
    outline: none;
    padding: 0;
    font-family: inherit;
  }

  /* ── Count badge ── */
  .count {
    font-size: 11px;
    color: var(--text-secondary);
    background: var(--bg-secondary);
    border: 0.5px solid var(--border);
    border-radius: 8px;
    padding: 1px 7px;
    flex-shrink: 0;
  }

  /* ── Reassigning state ── */
  .reassigning {
    display: flex;
    align-items: center;
    gap: 5px;
    flex-shrink: 0;
  }

  .reassigning-label {
    font-size: 11px;
    color: var(--text-secondary);
  }

  .spinner {
    width: 10px;
    height: 10px;
    border: 1px solid rgba(0, 0, 0, 0.12);
    border-top-color: rgba(0, 0, 0, 0.5);
    border-radius: 50%;
    animation: spin 0.6s linear infinite;
    flex-shrink: 0;
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }

  /* ── Chevron ── */
  .chevron {
    color: var(--text-secondary);
    transition: transform 0.15s;
    flex-shrink: 0;
  }
  .chevron.open {
    transform: rotate(180deg);
  }

  /* ── File list ── */
  .file-list {
    padding: 4px 12px 8px 36px;
    background: var(--bg-secondary);
  }

  /* ── Preview-mode file rows ── */
  .file-row {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 4px 0;
    transition: background 100ms;
    border-radius: 4px;
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

  /* ── Move button (hidden until row hover) ── */
  .move-btn {
    opacity: 0;
    transition: opacity 100ms;
    font-size: 12px;
    color: var(--text-secondary);
    padding: 2px 4px;
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
  }

  .empty-note {
    margin: 4px 0;
    font-size: 11px;
    color: var(--text-secondary);
    font-style: italic;
  }
</style>
