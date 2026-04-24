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

  // Stable display order — set once on load, not re-sorted on file count changes.
  // This prevents folders from jumping when a file is removed (X button).
  let displayOrder: number[] = [];
  $: sortedPreviewFolders = [
    ...displayOrder
      .map(id => previewFolders.find(f => f.cluster_id === id))
      .filter((f): f is PreviewFolder => !!f),
    ...previewFolders.filter(f => !displayOrder.includes(f.cluster_id)),
  ];

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
  let expandedCardIds  = new Set<number>();
  let flashingCardIds  = new Set<number>();
  let newFolderEditingId: number | null = null;
  let reclustering     = false;

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

  // ── Unsorted panel ────────────────────────────────────────────────────────
  let openUnsortedMoveFile: string | null = null;
  let unsortedSearch = '';
  let pinnedFilenames = new Set<string>();
  let collapsedTypes = new Set<string>();
  type UnsortedSortMode = 'default' | 'alpha-asc' | 'alpha-desc' | 'by-type';
  let unsortedSortMode: UnsortedSortMode = 'default';

  $: searchedUnsorted = unsortedSearch
    ? unsortedFiles.filter(f => f.filename.toLowerCase().includes(unsortedSearch.toLowerCase()))
    : unsortedFiles;
  $: pinnedUnsorted   = searchedUnsorted.filter(f =>  pinnedFilenames.has(f.filename));
  $: unpinnedUnsorted = searchedUnsorted.filter(f => !pinnedFilenames.has(f.filename));
  $: sortedUnpinned = (() => {
    const files = [...unpinnedUnsorted];
    if (unsortedSortMode === 'alpha-asc')  return files.sort((a, b) => a.filename.localeCompare(b.filename));
    if (unsortedSortMode === 'alpha-desc') return files.sort((a, b) => b.filename.localeCompare(a.filename));
    return files;
  })();
  $: typeGroups = (() => {
    if (unsortedSortMode !== 'by-type') return [] as [string, PreviewFile[]][];
    const groups = new Map<string, PreviewFile[]>();
    for (const f of unpinnedUnsorted) {
      const ext = f.ext || 'other';
      if (!groups.has(ext)) groups.set(ext, []);
      groups.get(ext)!.push(f);
    }
    return [...groups.entries()].sort((a, b) => b[1].length - a[1].length);
  })();

  // ── Sort ──────────────────────────────────────────────────────────────────
  type SortMode = 'count-desc' | 'count-asc' | 'alpha-asc' | 'alpha-desc';
  let sortMode: SortMode = 'count-desc';

  function applySort(mode: SortMode) {
    sortMode = mode;
    const folders = [...previewFolders];
    if (mode === 'count-desc')  folders.sort((a, b) => b.files.length - a.files.length);
    else if (mode === 'count-asc')  folders.sort((a, b) => a.files.length - b.files.length);
    else if (mode === 'alpha-asc')  folders.sort((a, b) => a.name.localeCompare(b.name));
    else if (mode === 'alpha-desc') folders.sort((a, b) => b.name.localeCompare(a.name));
    displayOrder = folders.map(f => f.cluster_id);
  }

  // ── Trash ─────────────────────────────────────────────────────────────────
  let trashedFiles: PreviewFile[] = [];
  let trashExpanded = false;
  let dragOverTrash = false;

  function restoreFromTrash(file: PreviewFile) {
    trashedFiles = trashedFiles.filter(f => f.filename !== file.filename);
    unsortedFiles = [...unsortedFiles, { ...file, currentClusterId: null }];
  }

  // ── Confirm ───────────────────────────────────────────────────────────────
  let confirming = false;
  let error = '';

  // Undo stack (up to 5 levels)
  type UndoSnapshot = {
    previewFolders: PreviewFolder[];
    unsortedFiles: PreviewFile[];
    trashedFiles: PreviewFile[];
    expandedCardIds: Set<number>;
    displayOrder: number[];
    label: string;
  };
  let undoStack: UndoSnapshot[] = [];

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
    const snap: UndoSnapshot = {
      previewFolders: previewFolders.map(cloneFolder),
      unsortedFiles: unsortedFiles.map(cloneFile),
      trashedFiles: trashedFiles.map(cloneFile),
      expandedCardIds: new Set(expandedCardIds),
      displayOrder: [...displayOrder],
      label,
    };
    undoStack = [...undoStack.slice(-4), snap]; // keep last 5
  }

  function undoLastMove() {
    const snap = undoStack[undoStack.length - 1];
    if (!snap) return;
    undoStack = undoStack.slice(0, -1);
    previewFolders = snap.previewFolders.map(cloneFolder);
    unsortedFiles = snap.unsortedFiles.map(cloneFile);
    trashedFiles = snap.trashedFiles.map(cloneFile);
    expandedCardIds = new Set(snap.expandedCardIds);
    displayOrder = [...snap.displayOrder];
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

    expandedCardIds = new Set(); // cards start collapsed
    displayOrder = [...previewFolders]
      .sort((a, b) => b.files.length - a.files.length)
      .map(f => f.cluster_id);

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
    // Block the browser's selectstart event whenever a drag candidate is held.
    // This is the last line of defence — selectstart fires before any text is
    // visually highlighted, so preventing it here kills selection at the root.
    const onSelectStart = (e: Event) => { if (dragCandidate) e.preventDefault(); };

    window.addEventListener('pointermove', onPointerMove);
    window.addEventListener('pointerup', onPointerUp);
    window.addEventListener('pointercancel', onPointerCancel);
    window.addEventListener('blur', onWindowBlur);
    window.addEventListener('selectstart', onSelectStart);

    return () => {
      window.removeEventListener('pointermove', onPointerMove);
      window.removeEventListener('pointerup', onPointerUp);
      window.removeEventListener('pointercancel', onPointerCancel);
      window.removeEventListener('blur', onWindowBlur);
      window.removeEventListener('selectstart', onSelectStart);
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
      // File may be in unsortedFiles or trashedFiles
      unsortedFiles = unsortedFiles.filter(f => f.filename !== file.filename);
      trashedFiles  = trashedFiles.filter(f => f.filename !== file.filename);
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

  function trashFileFromCard(file: PreviewFile, folderId: number) {
    snapshotState(`Trash ${file.filename}`);
    previewFolders = previewFolders.map(f =>
      f.cluster_id === folderId
        ? { ...f, files: f.files.filter(pf => pf.filename !== file.filename) }
        : f
    );
    trashedFiles = [...trashedFiles, { ...file, currentClusterId: null }];
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

    displayOrder = displayOrder.filter(id => id !== sourceId);
    expandedCardIds.delete(sourceId);
    expandedCardIds = new Set([...expandedCardIds, targetId]);
    flashCard(targetId);
  }

  function togglePin(filename: string) {
    if (pinnedFilenames.has(filename)) pinnedFilenames.delete(filename);
    else pinnedFilenames.add(filename);
    pinnedFilenames = new Set(pinnedFilenames);
  }

  function toggleTypeGroup(ext: string) {
    if (collapsedTypes.has(ext)) collapsedTypes.delete(ext);
    else collapsedTypes.add(ext);
    collapsedTypes = new Set(collapsedTypes);
  }

  function moveUnsortedUp(file: PreviewFile) {
    if (unsortedSortMode !== 'default' || unsortedSearch) return;
    const unpinned = unsortedFiles.filter(f => !pinnedFilenames.has(f.filename));
    const idx = unpinned.findIndex(f => f.filename === file.filename);
    if (idx <= 0) return;
    const arr = [...unsortedFiles];
    const aIdx = arr.findIndex(f => f.filename === unpinned[idx].filename);
    const bIdx = arr.findIndex(f => f.filename === unpinned[idx - 1].filename);
    [arr[aIdx], arr[bIdx]] = [arr[bIdx], arr[aIdx]];
    unsortedFiles = arr;
  }

  function moveUnsortedDown(file: PreviewFile) {
    if (unsortedSortMode !== 'default' || unsortedSearch) return;
    const unpinned = unsortedFiles.filter(f => !pinnedFilenames.has(f.filename));
    const idx = unpinned.findIndex(f => f.filename === file.filename);
    if (idx < 0 || idx >= unpinned.length - 1) return;
    const arr = [...unsortedFiles];
    const aIdx = arr.findIndex(f => f.filename === unpinned[idx].filename);
    const bIdx = arr.findIndex(f => f.filename === unpinned[idx + 1].filename);
    [arr[aIdx], arr[bIdx]] = [arr[bIdx], arr[aIdx]];
    unsortedFiles = arr;
  }

  // ── Pointer drag: source ─────────────────────────────────────────────────
  function onFilePointerDown(e: PointerEvent, file: PreviewFile) {
    if (e.button !== 0) return;
    document.body.classList.add('dragging');
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

    document.body.classList.add('dragging');
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

    // Prevent browser text-selection default for every move while a drag candidate
    // is held — not just after the threshold. Without this, moves < 6px never call
    // preventDefault and the browser happily starts selecting text.
    e.preventDefault();

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
  }

  function handlePointerUp(e: PointerEvent) {
    if (!dragCandidate || e.pointerId !== dragCandidate.pointerId) return;

    if (isPointerDragging && draggedFile) {
      if (dragOverTrash) {
        snapshotState(`Trash ${draggedFile.filename}`);
        removeFromSource(draggedFile);
        trashedFiles = [...trashedFiles, { ...draggedFile, currentClusterId: null }];
      } else if (dragOverFolderId !== null && draggedFile.currentClusterId !== dragOverFolderId) {
        snapshotState(`Move ${draggedFile.filename}`);
        moveFileTo(draggedFile, dragOverFolderId);
        flashCard(dragOverFolderId);
      } else if (dragOverUnsorted && draggedFile.currentClusterId !== null) {
        snapshotState(`Move ${draggedFile.filename}`);
        moveFileToUnsorted(draggedFile);
      }
    } else if (isPointerDragging && draggedFolder) {
      if (dragOverTrash) {
        snapshotState(`Trash ${draggedFolder.name}`);
        const id = draggedFolder.cluster_id;
        trashedFiles = [...trashedFiles, ...draggedFolder.files.map(f => ({ ...f, currentClusterId: null }))];
        previewFolders = previewFolders.filter(f => f.cluster_id !== id);
        displayOrder   = displayOrder.filter(did => did !== id);
        expandedCardIds.delete(id);
        expandedCardIds = new Set(expandedCardIds);
      } else if (dragOverFolderId !== null && dragOverFolderId !== draggedFolder.cluster_id) {
        snapshotState(`Merge ${draggedFolder.name}`);
        mergeFolderInto(draggedFolder.cluster_id, dragOverFolderId);
      }
    } else if (!isPointerDragging && dragCandidate.kind === 'file') {
      showFilePreview(dragCandidate.file);
    }

    clearPointerDrag();
  }

  function updatePointerDropTarget(x: number, y: number) {
    dragOverFolderId = null;
    dragOverUnsorted = false;
    dragOverTrash    = false;
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

    const trashTarget = hovered?.closest<HTMLElement>('[data-trash-drop]');
    if (trashTarget && (draggedFile || draggedFolder)) { dragOverTrash = true; return; }

    if (draggedFile) {
      const unsortedTarget = hovered?.closest<HTMLElement>('[data-unsorted-drop]');
      if (unsortedTarget && draggedFile.currentClusterId !== null) {
        dragOverUnsorted = true;
      }
    }
  }

  function clearPointerDrag() {
    dragCandidate    = null;
    draggedFile      = null;
    draggedFolder    = null;
    dragOverFolderId = null;
    dragOverUnsorted = false;
    dragOverTrash    = false;
    isPointerDragging = false;
    document.body.classList.remove('dragging');
  }

  // ── Delete folder (reclusters deleted files into remaining clusters) ──────
  async function deleteFolder(e: MouseEvent, folder: PreviewFolder) {
    e.stopPropagation();
    snapshotState(`Delete ${folder.name}`);
    const id = folder.cluster_id;

    // Remove folder from display immediately
    previewFolders = previewFolders.filter(f => f.cluster_id !== id);
    displayOrder = displayOrder.filter(did => did !== id);
    expandedCardIds.delete(id);
    expandedCardIds = new Set(expandedCardIds);

    reclustering = true;
    try {
      const filenames = folder.files.map(f => f.filename);
      const assignments = await tauriReassignFiles(filenames, id);
      const addedToUnsorted: PreviewFile[] = [];
      const assignedFilenames = new Set<string>();

      previewFolders = previewFolders.map(f => {
        const incoming = assignments.filter(a => a.cluster_id === f.cluster_id);
        if (incoming.length === 0) return f;
        flashCard(f.cluster_id);
        incoming.forEach(a => assignedFilenames.add(a.filename));
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

      // Unassigned or below-threshold files → unsorted
      for (const f of folder.files) {
        if (!assignedFilenames.has(f.filename)) {
          addedToUnsorted.push({ ...f, currentClusterId: null });
        }
      }
      if (addedToUnsorted.length > 0) {
        unsortedFiles = [...unsortedFiles, ...addedToUnsorted];
      }
    } catch {
      // Fallback: move all to unsorted if FAISS index unavailable
      unsortedFiles = [...unsortedFiles, ...folder.files.map(f => ({ ...f, currentClusterId: null }))];
    } finally {
      reclustering = false;
    }
  }

  // ── New folder ────────────────────────────────────────────────────────────
  function addNewFolder() {
    const id = Date.now();
    previewFolders     = [...previewFolders, { cluster_id: id, name: 'New Folder', files: [], isNew: true }];
    displayOrder       = [...displayOrder, id];
    expandedCardIds    = new Set([...expandedCardIds, id]);
    newFolderEditingId = id;
    editingCardId      = id;
    editingCardValue   = 'New Folder';
  }

  // ── Confirm ───────────────────────────────────────────────────────────────
  async function confirmSort() {
    confirming = true;
    error = '';
    try {
      await tauriConfirmSort(
        store.selectedFolder!,
        previewFolders,
        trashedFiles.map(f => f.filename),
      );
      sortStore.update(s => ({ ...s, stage: 'done' }));
      goto('/done');
    } catch (e: any) {
      error = typeof e === 'string' ? e : 'Failed to move files.';
      confirming = false;
    }
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
      <!-- Header + controls -->
      <div class="unsorted-header">
        <span class="unsorted-title">unsorted · {unsortedFiles.length} files</span>
        <div class="unsorted-controls">
          <input
            class="unsorted-search"
            type="text"
            placeholder="Search…"
            bind:value={unsortedSearch}
            on:pointerdown|stopPropagation
          />
          <div class="sort-bar compact">
            <button class="sort-btn" class:active={unsortedSortMode === 'default'}    on:click={() => unsortedSortMode = 'default'}    title="Default order">—</button>
            <button class="sort-btn" class:active={unsortedSortMode === 'alpha-asc'}  on:click={() => unsortedSortMode = 'alpha-asc'}  title="A → Z">A→Z</button>
            <button class="sort-btn" class:active={unsortedSortMode === 'alpha-desc'} on:click={() => unsortedSortMode = 'alpha-desc'} title="Z → A">Z→A</button>
            <button class="sort-btn" class:active={unsortedSortMode === 'by-type'}    on:click={() => unsortedSortMode = 'by-type'}    title="Group by type">Type</button>
          </div>
        </div>
      </div>

      <div class="panel-scroll">
        {#if unsortedFiles.length === 0}
          <p class="empty-state">{dragOverUnsorted ? 'Drop to unsort' : 'All files sorted'}</p>
        {:else if searchedUnsorted.length === 0}
          <p class="empty-state">No matches</p>
        {:else}

          <!-- Pinned files -->
          {#if pinnedUnsorted.length > 0}
            <p class="section-label">Pinned</p>
            {#each pinnedUnsorted as file (file.filename)}
              <!-- svelte-ignore a11y_no_static_element_interactions -->
              <div
                class="file-row pinned-row"
                class:pointer-dragging={draggedFile?.filename === file.filename}
                on:pointerdown={e => onFilePointerDown(e, file)}
              >
                <span class="ext-badge" style={extStyle(file.ext)}>{file.ext || '?'}</span>
                <span class="file-name">{trunc(file.filename, 19)}</span>
                <button class="pin-btn pinned" type="button" on:pointerdown|stopPropagation on:click|stopPropagation={() => togglePin(file.filename)} title="Unpin"><svg class="pin-icon" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M9.5 2.5L13.5 6.5L10 8.5L10 11L6 11L6 8.5L2.5 6.5L6.5 2.5L9.5 2.5Z" fill="currentColor" stroke="currentColor" stroke-width="0.5" stroke-linejoin="round"/><line x1="8" y1="11" x2="8" y2="14.5" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/></svg></button>
                {#if openUnsortedMoveFile === file.filename}
                  <select class="move-select" on:pointerdown|stopPropagation on:change={e => moveUnsortedFile(file.filename, (e.target as HTMLSelectElement).value)} on:blur={() => (openUnsortedMoveFile = null)}>
                    <option value="" disabled selected>Move to…</option>
                    {#each sortedPreviewFolders as dest}<option value={String(dest.cluster_id)}>{dest.name}</option>{/each}
                  </select>
                {:else}
                  <button class="move-btn" type="button" on:pointerdown|stopPropagation on:click|stopPropagation={() => (openUnsortedMoveFile = file.filename)} title="Move to folder">→</button>
                {/if}
              </div>
            {/each}
            <div class="section-divider"></div>
          {/if}

          <!-- By-type grouped view -->
          {#if unsortedSortMode === 'by-type'}
            {#each typeGroups as [ext, files] (ext)}
              <button class="type-group-header" type="button" on:click={() => toggleTypeGroup(ext)}>
                <span class="ext-badge sm" style={extStyle(ext)}>{ext || '?'}</span>
                <span class="type-group-label">{files.length} {files.length === 1 ? 'file' : 'files'}</span>
                <span class="chevron" class:open={!collapsedTypes.has(ext)}>^</span>
              </button>
              {#if !collapsedTypes.has(ext)}
                {#each files as file (file.filename)}
                  <!-- svelte-ignore a11y_no_static_element_interactions -->
                  <div class="file-row" class:pointer-dragging={draggedFile?.filename === file.filename} on:pointerdown={e => onFilePointerDown(e, file)}>
                    <span class="ext-badge" style={extStyle(file.ext)}>{file.ext || '?'}</span>
                    <span class="file-name">{trunc(file.filename, 19)}</span>
                    <button class="pin-btn" type="button" on:pointerdown|stopPropagation on:click|stopPropagation={() => togglePin(file.filename)} title="Pin to top"><svg class="pin-icon" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M9.5 2.5L13.5 6.5L10 8.5L10 11L6 11L6 8.5L2.5 6.5L6.5 2.5L9.5 2.5Z" fill="currentColor" stroke="currentColor" stroke-width="0.5" stroke-linejoin="round"/><line x1="8" y1="11" x2="8" y2="14.5" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/></svg></button>
                    {#if openUnsortedMoveFile === file.filename}
                      <select class="move-select" on:pointerdown|stopPropagation on:change={e => moveUnsortedFile(file.filename, (e.target as HTMLSelectElement).value)} on:blur={() => (openUnsortedMoveFile = null)}>
                        <option value="" disabled selected>Move to…</option>
                        {#each sortedPreviewFolders as dest}<option value={String(dest.cluster_id)}>{dest.name}</option>{/each}
                      </select>
                    {:else}
                      <button class="move-btn" type="button" on:pointerdown|stopPropagation on:click|stopPropagation={() => (openUnsortedMoveFile = file.filename)} title="Move to folder">→</button>
                    {/if}
                  </div>
                {/each}
              {/if}
            {/each}

          <!-- Default / alpha sorted view -->
          {:else}
            {#each sortedUnpinned as file, i (file.filename)}
              <!-- svelte-ignore a11y_no_static_element_interactions -->
              <div class="file-row" class:pointer-dragging={draggedFile?.filename === file.filename} on:pointerdown={e => onFilePointerDown(e, file)}>
                <span class="ext-badge" style={extStyle(file.ext)}>{file.ext || '?'}</span>
                <span class="file-name">{trunc(file.filename, 17)}</span>
                {#if unsortedSortMode === 'default' && !unsortedSearch}
                  <button class="order-btn" type="button" on:pointerdown|stopPropagation on:click|stopPropagation={() => moveUnsortedUp(file)}   disabled={i === 0}                         title="Move up">↑</button>
                  <button class="order-btn" type="button" on:pointerdown|stopPropagation on:click|stopPropagation={() => moveUnsortedDown(file)} disabled={i === sortedUnpinned.length - 1} title="Move down">↓</button>
                {/if}
                <button class="pin-btn" type="button" on:pointerdown|stopPropagation on:click|stopPropagation={() => togglePin(file.filename)} title="Pin to top"><svg class="pin-icon" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M9.5 2.5L13.5 6.5L10 8.5L10 11L6 11L6 8.5L2.5 6.5L6.5 2.5L9.5 2.5Z" fill="currentColor" stroke="currentColor" stroke-width="0.5" stroke-linejoin="round"/><line x1="8" y1="11" x2="8" y2="14.5" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/></svg></button>
                {#if openUnsortedMoveFile === file.filename}
                  <select class="move-select" on:pointerdown|stopPropagation on:change={e => moveUnsortedFile(file.filename, (e.target as HTMLSelectElement).value)} on:blur={() => (openUnsortedMoveFile = null)}>
                    <option value="" disabled selected>Move to…</option>
                    {#each sortedPreviewFolders as dest}<option value={String(dest.cluster_id)}>{dest.name}</option>{/each}
                  </select>
                {:else}
                  <button class="move-btn" type="button" on:pointerdown|stopPropagation on:click|stopPropagation={() => (openUnsortedMoveFile = file.filename)} title="Move to folder">→</button>
                {/if}
              </div>
            {/each}
          {/if}

        {/if}
      </div>

      <!-- Reclustering frosted-glass overlay -->
      {#if reclustering}
        <div class="recluster-overlay">
          <div class="spinner"></div>
          <span>Reclustering…</span>
        </div>
      {/if}

      <!-- Trash zone -->
      <!-- svelte-ignore a11y_no_static_element_interactions -->
      <div
        class="trash-zone"
        data-trash-drop="true"
        class:drag-over={dragOverTrash}
      >
        <button
          class="trash-header"
          type="button"
          on:click={() => trashExpanded = !trashExpanded}
        >
          <span class="trash-icon">🗑</span>
          <span>Trash · {trashedFiles.length} {trashedFiles.length === 1 ? 'file' : 'files'}</span>
          <span class="trash-chevron" class:open={trashExpanded}>^</span>
        </button>
        {#if trashExpanded && trashedFiles.length > 0}
          <div class="trash-files">
            <!-- svelte-ignore a11y_no_static_element_interactions -->
            {#each trashedFiles as file (file.filename)}
              <div
                class="file-row trash-file-row"
                class:pointer-dragging={draggedFile?.filename === file.filename}
                on:pointerdown={e => onFilePointerDown(e, file)}
              >
                <span class="ext-badge" style={extStyle(file.ext)}>{file.ext || '?'}</span>
                <span class="file-name">{trunc(file.filename, 20)}</span>
                <button
                  class="restore-btn"
                  type="button"
                  on:pointerdown|stopPropagation
                  on:click={() => restoreFromTrash(file)}
                  title="Restore to unsorted"
                >↩</button>
              </div>
            {/each}
          </div>
        {/if}
        {#if trashExpanded && trashedFiles.length === 0}
          <p class="empty-state" style="padding:10px 14px;font-size:11px;">
            {dragOverTrash ? 'Drop to delete on confirm' : 'No files in trash'}
          </p>
        {/if}
      </div>
    </div>

    <!-- ── Right panel: folder cards ─────────────────────────────────────── -->
    <div class="right-panel">
      <div class="panel-header-row">
        <span class="panel-header-text">{totalFolders} folders · {totalFiles} files</span>
        <div class="sort-bar">
          <button class="sort-btn" class:active={sortMode === 'count-desc'} on:click={() => applySort('count-desc')} title="Most files first">↓ #</button>
          <button class="sort-btn" class:active={sortMode === 'count-asc'}  on:click={() => applySort('count-asc')}  title="Fewest files first">↑ #</button>
          <button class="sort-btn" class:active={sortMode === 'alpha-asc'}  on:click={() => applySort('alpha-asc')}  title="A → Z">A→Z</button>
          <button class="sort-btn" class:active={sortMode === 'alpha-desc'} on:click={() => applySort('alpha-desc')} title="Z → A">Z→A</button>
        </div>
        <button
          class="undo-btn"
          disabled={undoStack.length === 0}
          on:click={undoLastMove}
          title={undoStack.length > 0 ? `Undo: ${undoStack[undoStack.length - 1].label}` : 'Nothing to undo'}
        >
          ↩ Undo{#if undoStack.length > 0}<span class="undo-count">{undoStack.length}</span>{/if}
        </button>
      </div>
      <div class="panel-scroll">
        <div class="drag-help">
          Drag files or folders to reorganize. Drag to 🗑 to permanently delete on confirm.
        </div>
        <div class="cards-grid" class:has-expanded={expandedCardIds.size > 0}>

          {#each sortedPreviewFolders as folder (folder.cluster_id)}
            <!-- svelte-ignore a11y_no_static_element_interactions -->
            <div
              class="folder-card"
              data-folder-drop={folder.cluster_id}
              class:drag-over={dragOverFolderId === folder.cluster_id}
              class:pointer-dragging={draggedFolder?.cluster_id === folder.cluster_id}
              class:flash={flashingCardIds.has(folder.cluster_id)}
              class:expanded={expandedCardIds.has(folder.cluster_id)}
              on:pointerdown={e => onFolderPointerDown(e, folder)}
            >
              <!-- pointer-events: none wrapper so child elements don't intercept dragover -->
              <div class="card-content">
                <!-- × delete -->
                <button
                  class="card-delete pe-auto"
                  type="button"
                  on:pointerdown|stopPropagation
                  on:click={e => deleteFolder(e, folder)}
                  tabindex="-1"
                  title="Delete folder"
                >×</button>

                <!-- Folder name (click to rename) -->
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

                <!-- Collapse/expand toggle (chevron + file count) -->
                <button
                  class="card-toggle pe-auto"
                  type="button"
                  on:pointerdown|stopPropagation
                  on:click|stopPropagation={() => toggleExpanded(folder.cluster_id)}
                  title={expandedCardIds.has(folder.cluster_id) ? 'Collapse' : 'Expand'}
                >
                  <span class="chevron" class:open={expandedCardIds.has(folder.cluster_id)}>^</span>
                  <span class="card-count">{folder.files.length} {folder.files.length === 1 ? 'file' : 'files'}</span>
                </button>

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
                        <button
                          class="card-file-trash"
                          type="button"
                          on:pointerdown|stopPropagation
                          on:click|stopPropagation={() => trashFileFromCard(file, folder.cluster_id)}
                          title="Delete on confirm"
                        >🗑</button>
                      </div>
                    {/each}
                    {#if folder.files.length === 0}
                      <p class="card-empty">No files — drop one here</p>
                    {/if}
                  </div>
                {/if}
              </div>
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
            <iframe class="preview-media" title="PDF Preview" src={`data:application/pdf;base64,${filePreview.data}`}></iframe>
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
    position: relative;
  }

  /* Frosted-glass reclustering overlay */
  .recluster-overlay {
    position: absolute;
    inset: 0;
    background: rgba(255, 255, 255, 0.72);
    backdrop-filter: blur(10px);
    -webkit-backdrop-filter: blur(10px);
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 10px;
    font-size: 12px;
    color: var(--text-secondary);
    z-index: 20;
    pointer-events: all;
  }

  .left-panel.drag-over {
    background: var(--accent-bg);
  }
  /* extend the drag-over tint to the unsorted header too */
  .left-panel.drag-over .unsorted-header {
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
    user-select: none;
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

  /* ── Unsorted panel header + controls ── */
  .unsorted-header {
    flex-shrink: 0;
    border-bottom: 0.5px solid var(--border);
    padding: 8px 10px;
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .unsorted-title {
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: var(--text-secondary);
    padding: 0 4px;
  }

  .unsorted-controls {
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .unsorted-search {
    flex: 1;
    min-width: 0;
    font-size: 11px;
    font-family: inherit;
    border: 0.5px solid var(--border-strong);
    border-radius: 4px;
    padding: 4px 8px;
    background: var(--bg);
    color: var(--text);
    outline: none;
  }
  .unsorted-search:focus { border-color: var(--accent); }
  .unsorted-search::placeholder { color: var(--text-secondary); opacity: 0.7; }

  /* Compact sort bar in unsorted panel */
  .sort-bar.compact .sort-btn {
    font-size: 10px;
    padding: 2px 5px;
  }

  /* Pinned section */
  .section-label {
    margin: 0;
    padding: 5px 14px 2px;
    font-size: 10px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--text-secondary);
    opacity: 0.55;
  }

  .section-divider {
    height: 0.5px;
    background: var(--border);
    margin: 4px 12px 2px;
  }

  .pinned-row { background: rgba(0, 0, 0, 0.02); }

  .pin-btn {
    opacity: 0;
    transition: opacity 100ms;
    background: none;
    border: none;
    cursor: pointer;
    padding: 2px 2px;
    flex-shrink: 0;
    line-height: 1;
    color: #b8a030;
    display: flex;
    align-items: center;
  }
  .pin-icon {
    width: 11px;
    height: 11px;
  }
  .file-row:hover .pin-btn { opacity: 0.45; }
  .pin-btn.pinned { opacity: 1; }
  .pin-btn:hover { opacity: 1 !important; }

  /* Type group header */
  .type-group-header {
    width: 100%;
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 4px 12px;
    background: none;
    border: none;
    border-bottom: 0.5px solid var(--border);
    cursor: pointer;
    font-size: 11px;
    font-family: inherit;
    color: var(--text-secondary);
    text-align: left;
  }
  .type-group-header:hover { background: var(--bg-secondary); color: var(--text); }
  .type-group-label { flex: 1; }

  /* Up/down order buttons */
  .order-btn {
    opacity: 0;
    transition: opacity 100ms;
    font-size: 11px;
    color: var(--text-secondary);
    background: none;
    border: none;
    cursor: pointer;
    padding: 1px 2px;
    flex-shrink: 0;
    line-height: 1;
  }
  .file-row:hover .order-btn { opacity: 1; }
  .order-btn:disabled { opacity: 0.18 !important; cursor: not-allowed; }

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

  /* Header row: title + sort bar + undo */
  .panel-header-row {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 14px;
    border-bottom: 0.5px solid var(--border);
    flex-shrink: 0;
  }

  .panel-header-text {
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: var(--text-secondary);
    flex: 1;
    white-space: nowrap;
  }

  /* Sort buttons */
  .sort-bar {
    display: flex;
    gap: 2px;
  }

  .sort-btn {
    background: none;
    border: 0.5px solid var(--border);
    border-radius: 4px;
    padding: 3px 7px;
    font-size: 11px;
    color: var(--text-secondary);
    cursor: pointer;
    white-space: nowrap;
  }
  .sort-btn:hover { background: var(--bg); color: var(--text); }
  .sort-btn.active {
    background: var(--text);
    color: var(--bg);
    border-color: var(--text);
  }

  /* Undo button (with optional count badge) */
  .undo-btn {
    display: flex;
    align-items: center;
    gap: 5px;
    background: var(--text);
    color: var(--bg);
    border: none;
    border-radius: 5px;
    padding: 5px 11px;
    font-size: 12px;
    font-weight: 500;
    cursor: pointer;
    flex-shrink: 0;
    transition: opacity 120ms;
  }
  .undo-btn:hover:not(:disabled) { opacity: 0.8; }
  .undo-btn:disabled { opacity: 0.18; cursor: not-allowed; }

  .undo-count {
    background: var(--accent);
    color: #fff;
    font-size: 9px;
    font-weight: 700;
    padding: 1px 4px;
    border-radius: 8px;
    line-height: 1.4;
  }

  /* ── Trash zone (bottom of left panel) ── */
  .trash-zone {
    border-top: 1px solid rgba(192, 57, 43, 0.25);
    flex-shrink: 0;
    background: rgba(192, 57, 43, 0.04);
    transition: background 100ms, border-color 100ms;
  }
  .trash-zone.drag-over {
    background: rgba(192, 57, 43, 0.12);
    border-top-color: var(--error);
  }

  .trash-header {
    width: 100%;
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 8px 12px;
    background: none;
    border: none;
    cursor: pointer;
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: var(--error);
    text-align: left;
    opacity: 0.7;
  }
  .trash-header:hover { opacity: 1; }
  .trash-zone.drag-over .trash-header { opacity: 1; }

  .trash-icon { font-size: 13px; }

  .trash-chevron {
    margin-left: auto;
    display: inline-block;
    font-size: 9px;
    transition: transform 150ms;
    transform: rotate(180deg);
  }
  .trash-chevron.open { transform: rotate(0deg); }

  .trash-files {
    padding: 0 0 6px;
  }

  .trash-file-row {
    opacity: 0.55;
  }
  .trash-file-row:hover { opacity: 1; }

  .restore-btn {
    opacity: 0;
    transition: opacity 100ms;
    font-size: 12px;
    color: var(--accent);
    background: none;
    border: none;
    cursor: pointer;
    padding: 2px 4px;
    flex-shrink: 0;
  }
  .trash-file-row:hover .restore-btn { opacity: 1; }

  .cards-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
    gap: 12px;
    padding: 16px;
    align-content: start;
    align-items: start;
  }

  /* Focus expand: expanded card spans 2 columns, slightly larger, others dim */
  .folder-card {
    transition: opacity 200ms, box-shadow 200ms;
  }
  .folder-card.expanded {
    grid-column: span 2;
    box-shadow: 0 3px 16px rgba(0,0,0,0.1);
    border-color: var(--border-strong);
    z-index: 1;
    padding: 14px;
  }
  .folder-card.expanded .card-name {
    font-size: 14px;
  }
  .cards-grid.has-expanded .folder-card:not(.expanded) {
    opacity: 0.55;
  }

  .drag-help {
    padding: 10px 16px 0;
    font-size: 11px;
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

  /* Chevron toggle button (contains file count) */
  .card-toggle {
    display: flex;
    align-items: center;
    gap: 4px;
    width: 100%;
    margin-top: 6px;
    padding: 5px 0 0;
    border: none;
    border-top: 0.5px solid var(--border);
    background: none;
    cursor: pointer;
    color: var(--text-secondary);
    font-size: 11px;
    font-family: inherit;
    line-height: 1;
  }
  .card-toggle:hover { color: var(--text); border-top-color: var(--border-strong); }

  .chevron {
    font-size: 9px;
    line-height: 1;
    flex-shrink: 0;
    display: inline-block;
    transform: rotate(180deg); /* collapsed = ^ rotated = v pointing down */
    transition: transform 150ms;
  }
  .chevron.open {
    transform: rotate(0deg); /* expanded = ^ pointing up */
  }

  .card-count {
    font-size: 11px;
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
    user-select: none;
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

  .card-file-trash {
    background: none;
    border: none;
    font-size: 10px;
    cursor: pointer;
    padding: 1px 2px;
    opacity: 0;
    transition: opacity 100ms;
    flex-shrink: 0;
    filter: grayscale(1);
  }
  .card-file-row:hover .card-file-trash { opacity: 0.7; filter: grayscale(0); }
  .card-file-trash:hover { opacity: 1 !important; }

  .card-empty {
    margin: 4px 0 0;
    font-size: 11px;
    color: var(--text-secondary);
    font-style: italic;
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
