<script lang="ts">
  import { goto } from '$app/navigation';
  import { onMount, tick } from 'svelte';
  import { sortStore } from '$lib/stores/sort';
  import type { PreviewFolder, PreviewFile } from '$lib/stores/sort';
  import { tauriConfirmSort, tauriReassignFiles, tauriGetFilePreview } from '$lib/tauri';
  import type { FilePreview } from '$lib/tauri';

  let store = $sortStore;
  $: store = $sortStore;

  // ── Data ──────────────────────────────────────────────────────────────────
  let previewFolders: PreviewFolder[] = [];
  let unsortedFiles: PreviewFile[] = [];

  $: sortedPreviewFolders = [...previewFolders].sort((a, b) => b.files.length - a.files.length);

  // ── File Preview ──────────────────────────────────────────────────────────
  let previewingFile: PreviewFile | null = null;
  let filePreview: FilePreview | null = null;
  let loadingPreview = false;
  let textContent = '';

  async function showFilePreview(file: PreviewFile) {
    if (!store.selectedFolder) return;
    previewingFile = file;
    loadingPreview = true;
    filePreview = null;
    textContent = '';

    try {
      const filePath = `${store.selectedFolder}/${file.filename}`;
      filePreview = await tauriGetFilePreview(filePath);
      
      if (filePreview.mime_type === 'text/plain') {
        textContent = atob(filePreview.data);
      }
    } catch (err) {
      console.error(err);
    } finally {
      loadingPreview = false;
    }
  }

  function closePreview() {
    previewingFile = null;
    filePreview = null;
    textContent = '';
  }

  // ── Card interaction ──────────────────────────────────────────────────────
  let editingCardId:    number | null = null;
  let editingCardValue = '';
  let expandedCardIds  = new Set<number>();   // multiple expansion
  let reassigningId:   number | null = null;
  let flashingCardIds  = new Set<number>();
  let newFolderEditingId: number | null = null;

  // ── Drag & drop ───────────────────────────────────────────────────────────
  let draggedFile:      PreviewFile | null = null;
  let draggedFolder:    PreviewFolder | null = null;
  let dragOverFolderId: number | null = null;
  let dragOverUnsorted  = false;
  let dragCandidate:
    | { kind: 'file'; file: PreviewFile; pointerId: number; startX: number; startY: number }
    | { kind: 'folder'; folder: PreviewFolder; pointerId: number; startX: number; startY: number }
    | null = null;
  let isPointerDragging = false;
  let dragPointer = { x: 0, y: 0 };
  let suppressCardClick = false;

  // ── Unsorted panel ────────────────────────────────────────────────────────
  let openUnsortedMoveFile: string | null = null;

  // ── Confirm ───────────────────────────────────────────────────────────────
  let confirming = false;
  let error = '';
  let lastUndo: {
    previewFolders: PreviewFolder[];
    unsortedFiles: PreviewFile[];
    expandedCardIds: Set<number>;
    label: string;
  } | null = null;

  // ── Stats ─────────────────────────────────────────────────────────────────
  $: totalFiles   = previewFolders.reduce((s, f) => s + f.files.length, 0);
  $: totalFolders = previewFolders.length;

  // ── Ext badge colors ──────────────────────────────────────────────────────
  const EXT_COLORS: Record<string, [string, string]> = {
    pdf:  ['#FAECE7', '#712B13'],
    docx: ['#E6F1FB', '#0C447C'],
    doc:  ['#E6F1FB', '#0C447C'],
    js:   ['#EAF3DE', '#27500A'],
    ts:   ['#EAF3DE', '#27500A'],
    jsx:  ['#EAF3DE', '#27500A'],
    tsx:  ['#EAF3DE', '#27500A'],
    csv:  ['#FAEEDA', '#633806'],
    xlsx: ['#FAEEDA', '#633806'],
    xls:  ['#FAEEDA', '#633806'],
    py:   ['#E1F5EE', '#085041'],
    jpg:  ['#EEEDFE', '#534AB7'],
    jpeg: ['#EEEDFE', '#534AB7'],
    png:  ['#EEEDFE', '#534AB7'],
    heic: ['#EEEDFE', '#534AB7'],
    mp4:  ['#F5E8FE', '#6B3DA8'],
    mov:  ['#F5E8FE', '#6B3DA8'],
  };
  function extStyle(ext: string): string {
    const [bg, color] = EXT_COLORS[ext] ?? ['#F1EFE8', '#444441'];
    return `background:${bg};color:${color}`;
  }
  function trunc(s: string, n: number): string {
    return s.length > n ? s.slice(0, n - 1) + '…' : s;
  }

  function cloneFile(file: PreviewFile): PreviewFile {
    return { ...file };
  }

  function cloneFolder(folder: PreviewFolder): PreviewFolder {
    return { ...folder, files: folder.files.map(cloneFile) };
  }

  function snapshotState(label: string) {
    lastUndo = {
      previewFolders: previewFolders.map(cloneFolder),
      unsortedFiles: unsortedFiles.map(cloneFile),
      expandedCardIds: new Set(expandedCardIds),
      label,
    };
  }

  function undoLastMove() {
    if (!lastUndo) return;
    previewFolders = lastUndo.previewFolders.map(cloneFolder);
    unsortedFiles = lastUndo.unsortedFiles.map(cloneFile);
    expandedCardIds = new Set(lastUndo.expandedCardIds);
    lastUndo = null;
    clearPointerDrag();
  }

  // ── Init ──────────────────────────────────────────────────────────────────
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

    expandedCardIds = new Set(previewFolders.map(f => f.cluster_id));

    const unsorted = rawFolders.find(f => f.cluster_id === -1 || f.folder_name === 'Unsorted');
    unsortedFiles = (unsorted?.files ?? []).map(file => ({
      filename: file.name,
      ext: file.extension.replace(/^\./, '').toLowerCase(),
      originalClusterId: -1,
      currentClusterId: null,
    }));

    const onPointerMove = (e: PointerEvent) => handlePointerMove(e);
    const onPointerUp = (e: PointerEvent) => handlePointerUp(e);
    const onPointerCancel = () => clearPointerDrag();
    const onWindowBlur = () => clearPointerDrag();

    window.addEventListener('pointermove', onPointerMove);
    window.addEventListener('pointerup', onPointerUp);
    window.addEventListener('pointercancel', onPointerCancel);
    window.addEventListener('blur', onWindowBlur);

    return () => {
      window.removeEventListener('pointermove', onPointerMove);
      window.removeEventListener('pointerup', onPointerUp);
      window.removeEventListener('pointercancel', onPointerCancel);
      window.removeEventListener('blur', onWindowBlur);
    };
  });

  // ── Auto-focus action ─────────────────────────────────────────────────────
  function autoFocus(node: HTMLInputElement) {
    tick().then(() => node.focus());
  }

  // ── Flash helper ──────────────────────────────────────────────────────────
  function flashCard(id: number) {
    flashingCardIds = new Set([...flashingCardIds, id]);
    setTimeout(() => {
      flashingCardIds = new Set([...flashingCardIds].filter(i => i !== id));
    }, 500);
  }

  // ── Expand toggle (multiple) ──────────────────────────────────────────────
  function toggleExpanded(id: number) {
    if (expandedCardIds.has(id)) {
      expandedCardIds.delete(id);
      expandedCardIds = new Set(expandedCardIds); // trigger reactivity
    } else {
      expandedCardIds = new Set([...expandedCardIds, id]);
    }
  }

  // ── Rename ────────────────────────────────────────────────────────────────
  function startCardEdit(e: MouseEvent, folder: PreviewFolder) {
    e.stopPropagation();
    editingCardId    = folder.cluster_id;
    editingCardValue = folder.name;
  }

  function commitCardEdit() {
    if (editingCardId === null) return;
    const id = editingCardId;
    if (editingCardValue.trim()) {
      previewFolders = previewFolders.map(f =>
        f.cluster_id === id ? { ...f, name: editingCardValue.trim() } : f
      );
      if (newFolderEditingId === id) newFolderEditingId = null;
    }
    editingCardId    = null;
    editingCardValue = '';
  }

  function cardNameKeydown(e: KeyboardEvent) {
    if (e.key === 'Enter')  { e.preventDefault(); commitCardEdit(); }
    if (e.key === 'Escape') { editingCardId = null; editingCardValue = ''; }
  }

  // ── Move helpers ──────────────────────────────────────────────────────────
  function removeFromSource(file: PreviewFile) {
    if (file.currentClusterId === null) {
      unsortedFiles = unsortedFiles.filter(f => f.filename !== file.filename);
    } else {
      previewFolders = previewFolders.map(f =>
        f.cluster_id === file.currentClusterId
          ? { ...f, files: f.files.filter(pf => pf.filename !== file.filename) }
          : f
      );
    }
  }

  function moveFileTo(file: PreviewFile, toId: number) {
    removeFromSource(file);
    previewFolders = previewFolders.map(f =>
      f.cluster_id === toId
        ? { ...f, files: [...f.files, { ...file, currentClusterId: toId }] }
        : f
    );
  }

  function moveFileToUnsorted(file: PreviewFile) {
    if (file.currentClusterId === null) return; // already unsorted
    removeFromSource(file);
    unsortedFiles = [...unsortedFiles, { ...file, currentClusterId: null }];
  }

  function removeFileFromCard(file: PreviewFile, folderId: number) {
    snapshotState(`Move ${file.filename}`);
    previewFolders = previewFolders.map(f =>
      f.cluster_id === folderId
        ? { ...f, files: f.files.filter(pf => pf.filename !== file.filename) }
        : f
    );
    unsortedFiles = [...unsortedFiles, { ...file, currentClusterId: null }];
  }

  function moveUnsortedFile(filename: string, val: string) {
    openUnsortedMoveFile = null;
    if (!val) return;
    const toId = parseInt(val);
    const file = unsortedFiles.find(f => f.filename === filename);
    if (!file) return;
    snapshotState(`Move ${file.filename}`);
    moveFileTo(file, toId);
  }

  function mergeFolderInto(sourceId: number, targetId: number) {
    const sourceFolder = previewFolders.find(f => f.cluster_id === sourceId);
    if (!sourceFolder || sourceId === targetId) return;

    previewFolders = previewFolders
      .filter(f => f.cluster_id !== sourceId)
      .map(f =>
        f.cluster_id === targetId
          ? {
              ...f,
              files: [
                ...f.files,
                ...sourceFolder.files.map(file => ({ ...file, currentClusterId: targetId })),
              ],
            }
          : f
      );

    expandedCardIds.delete(sourceId);
    expandedCardIds = new Set([...expandedCardIds, targetId]);
    flashCard(targetId);
  }

  // ── Pointer drag: source ─────────────────────────────────────────────────
  function onFilePointerDown(e: PointerEvent, file: PreviewFile) {
    if (e.button !== 0) return;
    dragCandidate = {
      kind: 'file',
      file,
      pointerId: e.pointerId,
      startX: e.clientX,
      startY: e.clientY,
    };
    dragPointer = { x: e.clientX, y: e.clientY };
  }

  function onFolderPointerDown(e: PointerEvent, folder: PreviewFolder) {
    if (e.button !== 0) return;
    const target = e.target as HTMLElement | null;
    if (target?.closest('.card-delete, .card-name, .card-name-input, .card-files, .card-file-remove, button, input, select')) {
      return;
    }

    dragCandidate = {
      kind: 'folder',
      folder,
      pointerId: e.pointerId,
      startX: e.clientX,
      startY: e.clientY,
    };
    dragPointer = { x: e.clientX, y: e.clientY };
  }

  function handlePointerMove(e: PointerEvent) {
    if (!dragCandidate || e.pointerId !== dragCandidate.pointerId) return;

    dragPointer = { x: e.clientX, y: e.clientY };
    if (!isPointerDragging) {
      const dx = e.clientX - dragCandidate.startX;
      const dy = e.clientY - dragCandidate.startY;
      if (Math.hypot(dx, dy) < 6) return;

      isPointerDragging = true;
      if (dragCandidate.kind === 'file') {
        draggedFile = dragCandidate.file;
        console.log('pointerdrag start file', draggedFile.filename);
      } else {
        draggedFolder = dragCandidate.folder;
        console.log('pointerdrag start folder', draggedFolder.name);
      }
    }

    updatePointerDropTarget(e.clientX, e.clientY);
    e.preventDefault();
  }

  function handlePointerUp(e: PointerEvent) {
    if (!dragCandidate || e.pointerId !== dragCandidate.pointerId) return;

    if (isPointerDragging && draggedFile) {
      if (dragOverFolderId !== null && draggedFile.currentClusterId !== dragOverFolderId) {
        snapshotState(`Move ${draggedFile.filename}`);
        moveFileTo(draggedFile, dragOverFolderId);
        flashCard(dragOverFolderId);
      } else if (dragOverUnsorted && draggedFile.currentClusterId !== null) {
        snapshotState(`Move ${draggedFile.filename}`);
        moveFileToUnsorted(draggedFile);
      }
      suppressCardClick = true;
    } else if (isPointerDragging && draggedFolder) {
      if (dragOverFolderId !== null && dragOverFolderId !== draggedFolder.cluster_id) {
        snapshotState(`Merge ${draggedFolder.name}`);
        mergeFolderInto(draggedFolder.cluster_id, dragOverFolderId);
      }
      suppressCardClick = true;
    } else if (!isPointerDragging && dragCandidate.kind === 'file') {
      showFilePreview(dragCandidate.file);
    }

    clearPointerDrag();
  }

  function updatePointerDropTarget(x: number, y: number) {
    dragOverFolderId = null;
    dragOverUnsorted = false;
    if (!draggedFile && !draggedFolder) return;

    const hovered = document.elementFromPoint(x, y) as HTMLElement | null;
    const folderTarget = hovered?.closest<HTMLElement>('[data-folder-drop]');
    if (folderTarget) {
      const id = Number(folderTarget.dataset.folderDrop);
      const isValidFileTarget = draggedFile && draggedFile.currentClusterId !== id;
      const isValidFolderTarget = draggedFolder && draggedFolder.cluster_id !== id;
      if (!Number.isNaN(id) && (isValidFileTarget || isValidFolderTarget)) {
        dragOverFolderId = id;
        return;
      }
    }

    const unsortedTarget = hovered?.closest<HTMLElement>('[data-unsorted-drop]');
    if (unsortedTarget && draggedFile && draggedFile.currentClusterId !== null) {
      dragOverUnsorted = true;
    }
  }

  function clearPointerDrag() {
    dragCandidate = null;
    draggedFile = null;
    draggedFolder = null;
    dragOverFolderId = null;
    dragOverUnsorted = false;
    isPointerDragging = false;
  }

  // ── Delete folder ─────────────────────────────────────────────────────────
  async function deleteFolder(e: MouseEvent, folder: PreviewFolder) {
    e.stopPropagation();
    const id = folder.cluster_id;
    reassigningId = id;
    try {
      const filenames = folder.files.map(f => f.filename);
      const assignments = await tauriReassignFiles(filenames, id);
      const addedToUnsorted: PreviewFile[] = [];

      previewFolders = previewFolders
        .filter(f => f.cluster_id !== id)
        .map(f => {
          const incoming = assignments.filter(a => a.cluster_id === f.cluster_id);
          if (incoming.length === 0) return f;
          flashCard(f.cluster_id);
          return {
            ...f,
            files: [...f.files, ...incoming.map(a => ({
              filename: a.filename,
              ext: a.filename.split('.').pop()?.toLowerCase() ?? '',
              originalClusterId: id,
              currentClusterId: f.cluster_id,
            }))],
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
    } catch {
      unsortedFiles = [...unsortedFiles, ...folder.files.map(f => ({ ...f, currentClusterId: null }))];
      previewFolders = previewFolders.filter(f => f.cluster_id !== id);
    } finally {
      reassigningId = null;
    }
  }

  // ── New folder ────────────────────────────────────────────────────────────
  function addNewFolder() {
    const id = Date.now();
    previewFolders     = [...previewFolders, { cluster_id: id, name: 'New Folder', files: [], isNew: true }];
    newFolderEditingId = id;
    editingCardId      = id;
    editingCardValue   = 'New Folder';
  }

  // ── Confirm ───────────────────────────────────────────────────────────────
  async function confirmSort() {
    confirming = true;
    error = '';
    try {
      await tauriConfirmSort(store.selectedFolder!, previewFolders);
      sortStore.update(s => ({ ...s, stage: 'done' }));
      goto('/done');
    } catch (e: any) {
      error = typeof e === 'string' ? e : 'Failed to move files.';
      confirming = false;
    }
  }

  function handleFolderCardClick(id: number) {
    if (suppressCardClick) {
      suppressCardClick = false;
      return;
    }
    toggleExpanded(id);
  }
</script>

<div class="page">
  <div class="main">

    <!-- ── Left panel: unsorted ───────────────────────────────────────────── -->
    <!-- svelte-ignore a11y_no_static_element_interactions -->
    <div
      class="left-panel"
      data-unsorted-drop="true"
      class:drag-over={dragOverUnsorted}
    >
      <p class="panel-header">unsorted · {unsortedFiles.length} files</p>
      <div class="panel-scroll">
        {#if unsortedFiles.length === 0}
          <p class="empty-state">{dragOverUnsorted ? 'Drop to unsort' : 'All files sorted'}</p>
        {:else}
          {#each unsortedFiles as file (file.filename)}
            <!-- svelte-ignore a11y_no_static_element_interactions -->
            <div
              class="file-row"
              class:pointer-dragging={draggedFile?.filename === file.filename}
              on:pointerdown={e => onFilePointerDown(e, file)}
            >
              <span class="ext-badge" style={extStyle(file.ext)}>{file.ext || '?'}</span>
              <span class="file-name">{trunc(file.filename, 24)}</span>
              {#if openUnsortedMoveFile === file.filename}
                <select
                  class="move-select"
                  on:pointerdown|stopPropagation
                  on:change={e => moveUnsortedFile(file.filename, (e.target as HTMLSelectElement).value)}
                  on:blur={() => (openUnsortedMoveFile = null)}
                >
                  <option value="" disabled selected>Move to…</option>
                  {#each sortedPreviewFolders as dest}
                    <option value={String(dest.cluster_id)}>{dest.name}</option>
                  {/each}
                </select>
              {:else}
                <button
                  class="move-btn"
                  type="button"
                  on:pointerdown|stopPropagation
                  on:click|stopPropagation={() => (openUnsortedMoveFile = file.filename)}
                  title="Move to folder"
                >→</button>
              {/if}
            </div>
          {/each}
        {/if}
      </div>
    </div>

    <!-- ── Right panel: folder cards ─────────────────────────────────────── -->
    <div class="right-panel">
      <p class="panel-header">{totalFolders} folders · {totalFiles} files</p>
      <div class="panel-scroll">
        <div class="drag-help">
          Drag a file onto a folder to move it. Drag a folder onto another folder to merge them.
        </div>
        <div class="cards-grid">

          {#each sortedPreviewFolders as folder (folder.cluster_id)}
            <!-- svelte-ignore a11y_no_static_element_interactions a11y_click_events_have_key_events -->
            <div
              class="folder-card"
              data-folder-drop={folder.cluster_id}
              class:drag-over={dragOverFolderId === folder.cluster_id}
              class:pointer-dragging={draggedFolder?.cluster_id === folder.cluster_id}
              class:flash={flashingCardIds.has(folder.cluster_id)}
              on:pointerdown={e => onFolderPointerDown(e, folder)}
              on:click={() => handleFolderCardClick(folder.cluster_id)}
            >
              <!-- pointer-events: none wrapper so child elements don't intercept dragover -->
              <div class="card-content">
                <!-- × delete -->
                {#if reassigningId !== folder.cluster_id}
                  <button
                    class="card-delete pe-auto"
                    type="button"
                    on:pointerdown|stopPropagation
                    on:click={e => deleteFolder(e, folder)}
                    tabindex="-1"
                    title="Delete folder"
                  >×</button>
                {/if}

                <!-- Folder name -->
                {#if editingCardId === folder.cluster_id}
                  <input
                    class="card-name-input pe-auto"
                    bind:value={editingCardValue}
                    on:pointerdown|stopPropagation
                    on:blur={commitCardEdit}
                    on:keydown={cardNameKeydown}
                    on:click|stopPropagation
                    use:autoFocus
                  />
                {:else}
                  <span
                    class="card-name pe-auto"
                    on:pointerdown|stopPropagation
                    on:click|stopPropagation={e => startCardEdit(e, folder)}
                    title="Click to rename"
                  >{folder.name}</span>
                {/if}

                <!-- File count -->
                <span class="card-count">{folder.files.length} {folder.files.length === 1 ? 'file' : 'files'}</span>

                <!-- Expanded file list -->
                {#if expandedCardIds.has(folder.cluster_id)}
                  <!-- svelte-ignore a11y_no_static_element_interactions a11y_click_events_have_key_events -->
                  <div class="card-files pe-auto" on:click|stopPropagation>
                    {#each folder.files as file (file.filename)}
                      <!-- svelte-ignore a11y_no_static_element_interactions -->
                      <div
                        class="card-file-row"
                        class:pointer-dragging={draggedFile?.filename === file.filename}
                        on:pointerdown={e => onFilePointerDown(e, file)}
                      >
                        <span class="ext-badge sm" style={extStyle(file.ext)}>{file.ext || '?'}</span>
                        <span class="card-file-name">{trunc(file.filename, 18)}</span>
                        <button
                          class="card-file-remove"
                          type="button"
                          on:pointerdown|stopPropagation
                          on:click|stopPropagation={() => removeFileFromCard(file, folder.cluster_id)}
                          title="Send to unsorted"
                        >×</button>
                      </div>
                    {/each}
                    {#if folder.files.length === 0}
                      <p class="card-empty">No files — drop one here</p>
                    {/if}
                  </div>
                {/if}
              </div>

              <!-- Spinner overlay -->
              {#if reassigningId === folder.cluster_id}
                <div class="card-overlay">
                  <div class="spinner"></div>
                </div>
              {/if}
            </div>
          {/each}

          <!-- + New folder card -->
          <button class="folder-card new-card" type="button" on:click={addNewFolder}>
            <span class="new-label">+ New folder</span>
          </button>

        </div>
      </div>
    </div>

  </div>

  <!-- ── Bottom bar ─────────────────────────────────────────────────────── -->
  <div class="bottom-bar">
    <button class="btn-ghost" on:click={() => goto('/')}>Back</button>
    <button class="btn-ghost" disabled={!lastUndo} on:click={undoLastMove}>
      {lastUndo ? `Undo ${lastUndo.label}` : 'Undo'}
    </button>
    {#if error}
      <p class="error-text">{error}</p>
    {/if}
    <button class="btn-primary" disabled={confirming} on:click={confirmSort}>
      {confirming ? 'Moving…' : 'Move files →'}
    </button>
  </div>

</div>

{#if previewingFile}
  <!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
  <div class="modal-backdrop" on:click={closePreview}>
    <div class="modal-content" on:click|stopPropagation>
      <div class="modal-header">
        <div class="header-left">
          <span class="ext-badge" style={extStyle(previewingFile.ext)}>{previewingFile.ext || '?'}</span>
          <span class="modal-title">{previewingFile.filename}</span>
        </div>
        <button class="close-btn" on:click={closePreview}>×</button>
      </div>
      <div class="modal-body">
        {#if loadingPreview}
          <div class="loading-state">
            <div class="spinner"></div>
            <span>Loading preview…</span>
          </div>
        {:else if filePreview}
          {#if filePreview.mime_type.startsWith('image/')}
            <img class="preview-media" src={`data:${filePreview.mime_type};base64,${filePreview.data}`} alt={previewingFile.filename} />
          {:else if filePreview.mime_type === 'application/pdf'}
            <iframe class="preview-media" title="PDF Preview" src={`data:application/pdf;base64,${filePreview.data}`} />
          {:else if filePreview.mime_type === 'text/plain'}
            <pre class="preview-text">{textContent || 'Empty file.'}</pre>
          {:else}
            <div class="loading-state">
              <p>No preview for this file type ({filePreview.mime_type})</p>
            </div>
          {/if}
        {:else}
          <div class="loading-state">
            <p>Failed to load preview.</p>
          </div>
        {/if}
      </div>
    </div>
  </div>
{/if}

{#if isPointerDragging && draggedFile}
  <div class="drag-preview" style={`left:${dragPointer.x + 14}px;top:${dragPointer.y + 14}px;`}>
    <span class="ext-badge sm" style={extStyle(draggedFile.ext)}>{draggedFile.ext || '?'}</span>
    <span>{trunc(draggedFile.filename, 28)}</span>
  </div>
{/if}

{#if isPointerDragging && draggedFolder}
  <div class="drag-preview" style={`left:${dragPointer.x + 14}px;top:${dragPointer.y + 14}px;`}>
    <strong>{trunc(draggedFolder.name, 24)}</strong>
    <span>{draggedFolder.files.length} {draggedFolder.files.length === 1 ? 'file' : 'files'}</span>
  </div>
{/if}

<style>
  .page {
    display: flex;
    flex-direction: column;
    height: 100vh;
    overflow: hidden;
    background: var(--bg);
  }

  .main {
    display: flex;
    flex: 1;
    overflow: hidden;
    min-height: 0;
  }

  .panel-header {
    margin: 0;
    padding: 10px 14px 8px;
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: var(--text-secondary);
    flex-shrink: 0;
    border-bottom: 0.5px solid var(--border);
  }

  .panel-scroll {
    flex: 1;
    overflow-y: auto;
    min-height: 0;
  }

  /* ── Left panel ── */
  .left-panel {
    width: 260px;
    flex-shrink: 0;
    display: flex;
    flex-direction: column;
    border-right: 0.5px solid var(--border);
    background: var(--bg);
    overflow: hidden;
    transition: background 100ms;
  }

  .left-panel.drag-over {
    background: var(--accent-bg);
  }
  /* extend the drag-over tint to the header too */
  .left-panel.drag-over .panel-header {
    border-bottom-color: var(--accent);
  }

  .empty-state {
    margin: 0;
    padding: 24px 14px;
    font-size: 13px;
    color: var(--text-secondary);
    text-align: center;
  }

  /* ── File rows (left panel + drag source) ── */
  .file-row {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 6px 12px;
    cursor: pointer;
    touch-action: none;
    transition: background 100ms;
  }
  .file-row:hover  { background: var(--bg-secondary); }
  .file-row:active { cursor: grabbing; }
  .file-row.pointer-dragging {
    opacity: 0.45;
  }

  .file-name {
    flex: 1;
    font-size: 12px;
    color: var(--text);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    user-select: none;
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
  .file-row:hover .move-btn { opacity: 1; }

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

  /* ── Ext badge ── */
  .ext-badge {
    font-size: 10px;
    font-weight: 600;
    padding: 1px 5px;
    border-radius: 3px;
    text-transform: lowercase;
    flex-shrink: 0;
    min-width: 28px;
    text-align: center;
    line-height: 1.4;
  }
  .ext-badge.sm {
    font-size: 9px;
    min-width: 22px;
    padding: 1px 4px;
  }

  /* ── Right panel ── */
  .right-panel {
    flex: 1;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    background: var(--bg-secondary);
  }

  .cards-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
    gap: 12px;
    padding: 16px;
    align-content: start;
  }

  .drag-help {
    padding: 12px 16px 0;
    font-size: 12px;
    color: var(--text-secondary);
  }

  /* ── Pointer-events helpers ── */
  .card-content { pointer-events: none; }
  .pe-auto { pointer-events: auto; }

  /* ── Folder card ── */
  .folder-card {
    position: relative;
    background: var(--bg);
    border: 0.5px solid var(--border);
    border-radius: 8px;
    padding: 12px;
    cursor: pointer;
    text-align: left;
    transition: border-color 100ms, background 100ms;
    min-height: 72px;
  }
  .folder-card:hover { border-color: var(--border-strong); }
  .folder-card.pointer-dragging {
    opacity: 0.45;
  }

  .folder-card.drag-over {
    border: 1.5px solid var(--accent);
    background: var(--accent-bg);
  }

  @keyframes card-flash {
    0%   { background: #E1F5EE; }
    100% { background: var(--bg); }
  }
  .folder-card.flash {
    animation: card-flash 500ms ease forwards;
  }

  /* ── Card × delete ── */
  .card-delete {
    position: absolute;
    top: 6px;
    right: 7px;
    background: none;
    border: none;
    font-size: 12px;
    line-height: 1;
    color: var(--text-secondary);
    cursor: pointer;
    padding: 2px 3px;
    opacity: 0;
    transition: opacity 100ms;
  }
  .folder-card:hover .card-delete { opacity: 1; }

  /* ── Card name ── */
  .card-name {
    display: block;
    font-size: 13px;
    font-weight: 500;
    color: var(--text);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    padding-right: 14px;
    cursor: text;
    user-select: none;
  }
  .card-name:hover {
    text-decoration: underline;
    text-underline-offset: 2px;
  }

  .card-name-input {
    display: block;
    width: 100%;
    font-size: 13px;
    font-weight: 500;
    color: var(--text);
    background: transparent;
    border: none;
    border-bottom: 1px solid var(--accent);
    outline: none;
    padding: 0 14px 0 0;
    font-family: inherit;
    user-select: text;
  }

  .card-count {
    display: block;
    margin-top: 4px;
    font-size: 11px;
    color: var(--text-secondary);
  }

  /* ── Expanded file list inside card ── */
  .card-files {
    margin-top: 10px;
    border-top: 0.5px solid var(--border);
    padding-top: 6px;
  }

  .card-file-row {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 3px 0;
    border-radius: 3px;
    cursor: pointer;
    touch-action: none;
    transition: background 100ms;
  }
  .card-file-row:hover  { background: var(--bg-secondary); }
  .card-file-row:active { cursor: grabbing; }
  .card-file-row.pointer-dragging {
    opacity: 0.45;
  }

  .card-file-name {
    flex: 1;
    font-size: 11px;
    color: var(--text);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    user-select: none;
  }

  .card-file-remove {
    background: none;
    border: none;
    font-size: 11px;
    color: var(--text-secondary);
    cursor: pointer;
    padding: 1px 3px;
    opacity: 0;
    transition: opacity 100ms;
    flex-shrink: 0;
  }
  .card-file-row:hover .card-file-remove { opacity: 1; }

  .card-empty {
    margin: 4px 0 0;
    font-size: 11px;
    color: var(--text-secondary);
    font-style: italic;
  }

  /* ── Spinner overlay ── */
  .card-overlay {
    position: absolute;
    inset: 0;
    background: rgba(255, 255, 255, 0.85);
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 2;
  }

  .spinner {
    width: 18px;
    height: 18px;
    border: 2px solid rgba(0, 0, 0, 0.1);
    border-top-color: rgba(0, 0, 0, 0.45);
    border-radius: 50%;
    animation: spin 0.7s linear infinite;
  }
  @keyframes spin { to { transform: rotate(360deg); } }

  /* ── New folder card ── */
  .new-card {
    border-style: dashed;
    display: flex;
    align-items: center;
    justify-content: center;
    background: transparent;
    cursor: pointer;
    min-height: 72px;
  }
  .new-card:hover {
    background: var(--bg);
    border-color: var(--border-strong);
  }
  .new-label {
    font-size: 12px;
    color: var(--text-secondary);
  }

  /* ── Bottom bar ── */
  .bottom-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 20px;
    border-top: 0.5px solid var(--border);
    background: var(--bg);
    flex-shrink: 0;
    gap: 12px;
  }

  .error-text {
    flex: 1;
    margin: 0;
    font-size: 12px;
    color: var(--error);
    text-align: center;
  }

  .btn-ghost {
    background: none;
    border: 0.5px solid var(--border-strong);
    border-radius: 6px;
    padding: 9px 20px;
    font-size: 13px;
    cursor: pointer;
    color: var(--text);
    flex-shrink: 0;
  }
  .btn-ghost:hover { background: var(--bg-secondary); }

  .btn-primary {
    padding: 9px 24px;
    background: var(--text);
    color: var(--bg);
    border: none;
    border-radius: 6px;
    font-size: 13px;
    font-weight: 500;
    cursor: pointer;
    flex-shrink: 0;
  }
  .btn-primary:disabled       { opacity: 0.4; cursor: not-allowed; }
  .btn-primary:hover:not(:disabled) { opacity: 0.85; }

  /* ── File Preview Modal ── */
  .modal-backdrop {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.4);
    backdrop-filter: blur(4px);
    z-index: 1000;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 40px;
  }

  .modal-content {
    background: var(--bg);
    border-radius: 12px;
    width: 100%;
    max-width: 600px;
    max-height: 80vh;
    display: flex;
    flex-direction: column;
    box-shadow: 0 12px 40px rgba(0, 0, 0, 0.2);
    border: 0.5px solid var(--border-strong);
    overflow: hidden;
  }

  .modal-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 16px 20px;
    border-bottom: 0.5px solid var(--border);
  }

  .header-left {
    display: flex;
    align-items: center;
    gap: 10px;
    overflow: hidden;
  }

  .modal-title {
    font-size: 14px;
    font-weight: 600;
    color: var(--text);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .close-btn {
    background: none;
    border: none;
    font-size: 20px;
    color: var(--text-secondary);
    cursor: pointer;
    padding: 4px;
    line-height: 1;
  }
  .close-btn:hover { color: var(--text); }

  .modal-body {
    flex: 1;
    overflow-y: auto;
    padding: 20px;
    background: var(--bg-secondary);
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    min-height: 200px;
  }

  .loading-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 12px;
    padding: 40px 0;
    color: var(--text-secondary);
    font-size: 13px;
    text-align: center;
  }

  .preview-text {
    margin: 0;
    width: 100%;
    font-family: var(--font-mono, monospace);
    font-size: 12px;
    line-height: 1.6;
    color: var(--text);
    white-space: pre-wrap;
    word-break: break-all;
    align-self: flex-start;
  }

  .preview-media {
    max-width: 100%;
    max-height: 60vh;
    border: none;
    border-radius: 4px;
    background: white;
  }

  iframe.preview-media {
    width: 100%;
    height: 60vh;
  }

  .drag-preview {
    position: fixed;
    z-index: 2000;
    display: inline-flex;
    align-items: center;
    gap: 8px;
    max-width: 240px;
    padding: 6px 10px;
    border: 0.5px solid var(--border-strong);
    border-radius: 8px;
    background: rgba(255, 255, 255, 0.96);
    box-shadow: 0 8px 22px rgba(0, 0, 0, 0.12);
    color: var(--text);
    font-size: 12px;
    pointer-events: none;
  }
</style>
