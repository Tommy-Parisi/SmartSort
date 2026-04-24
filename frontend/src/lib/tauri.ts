import { invoke } from '@tauri-apps/api/core';
import { listen, type UnlistenFn } from '@tauri-apps/api/event';
import type { FolderTree, Activity, PreviewFolder } from './stores/sort';

// ── Event payloads ────────────────────────────────────────────────────────────

export interface FileAssignedEvent {
  filename: string;
  cluster_id: number;
  folder_name: string;
  files_processed: number;
  files_total: number;
  stage: 'extracting' | 'embedding' | 'clustering' | 'naming' | 'placing';
}

export interface FolderDiscoveredEvent {
  cluster_id: number;
  folder_name: string;
  estimated_capacity: number;
}

export interface SortCompleteEvent {
  folders_created: number;
  files_sorted: number;
  files_unsorted: number;
  folder_tree: FolderTree;
}

export interface DaemonFilePlacedEvent {
  filename: string;
  folder_name: string;
  timestamp: number;
}

export interface DaemonStatus {
  running: boolean;
  watchedFolders: string[];
  recentActivity: Activity[];
}

export interface LicenseStatus {
  valid: boolean;
  trial: boolean;
  filesRemaining?: number;
}

// ── Invoke wrappers ───────────────────────────────────────────────────────────

export const tauriStartSort = (
  folderPath: string,
  watchMode: boolean,
  previewMode: boolean
) => invoke<void>('start_sort', { folderPath, watchMode, previewMode });

export interface FileAssignment {
  filename: string;
  cluster_id: number;
  folder_name: string;
}

export const tauriConfirmSort = (
  baseFolder: string,
  previewFolders: PreviewFolder[],
  trashedFilenames: string[],
) => invoke<void>('confirm_sort', { baseFolder, previewFolders, trashedFilenames });

export const tauriReassignFiles = (
  filenames: string[],
  excludeClusterId: number,
) => invoke<FileAssignment[]>('reassign_files', { filenames, excludeClusterId });
export const tauriUndoSort = () =>
  invoke<void>('undo_sort');

export interface FilePreview {
  data: string;
  mime_type: string;
}

export const tauriGetFilePreview = (filePath: string) =>
  invoke<FilePreview>('get_file_preview', { filePath });

export const tauriGetDaemonStatus = () =>
  invoke<any>('get_daemon_status');


export const tauriStartDaemon = (folders: string[]) =>
  invoke<void>('start_daemon', { folders });

export const tauriStopDaemon = () => invoke<void>('stop_daemon');

export const tauriActivateLicense = (key: string) =>
  invoke<void>('activate_license', { key });

export const tauriGetLicenseStatus = () =>
  invoke<LicenseStatus>('get_license_status');

// ── Event listeners ───────────────────────────────────────────────────────────

export const onFileAssigned = (cb: (e: FileAssignedEvent) => void): Promise<UnlistenFn> =>
  listen<FileAssignedEvent>('file-assigned', e => cb(e.payload));

export const onFolderDiscovered = (cb: (e: FolderDiscoveredEvent) => void): Promise<UnlistenFn> =>
  listen<FolderDiscoveredEvent>('folder-discovered', e => cb(e.payload));

export const onSortComplete = (cb: (e: SortCompleteEvent) => void): Promise<UnlistenFn> =>
  listen<SortCompleteEvent>('sort-complete', e => cb(e.payload));

export const onDaemonFilePlaced = (cb: (e: DaemonFilePlacedEvent) => void): Promise<UnlistenFn> =>
  listen<DaemonFilePlacedEvent>('daemon-file-placed', e => cb(e.payload));

export interface SortErrorEvent {
  code?: string;
  message: string;
  trial_limit?: number;
  file_count?: number;
}

export const onSortError = (cb: (e: SortErrorEvent) => void): Promise<UnlistenFn> =>
  listen<SortErrorEvent>('sort-error', e => cb(e.payload));
