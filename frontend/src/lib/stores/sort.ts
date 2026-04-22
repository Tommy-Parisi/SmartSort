import { writable } from 'svelte/store';

export interface PreviewFile {
  filename: string;
  ext: string;
  originalClusterId: number;
  currentClusterId: number | null; // null = unsorted
}

export interface PreviewFolder {
  cluster_id: number;
  name: string;
  files: PreviewFile[];
  isNew?: boolean;
}

export interface FolderDiscovered {
  cluster_id: number;
  folder_name: string;
  estimated_capacity: number;
}

export interface FolderTree {
  folders: FolderTreeEntry[];
}

export interface FolderTreeEntry {
  cluster_id: number;
  folder_name: string;
  files: FileEntry[];
}

export interface FileEntry {
  name: string;
  extension: string;
}

export interface Activity {
  filename: string;
  folder_name: string;
  timestamp: number;
}

export interface Particle {
  id: number;
  x: number;
  y: number;
  startX: number;
  startY: number;
  targetX: number;
  targetY: number;
  folderId: number;
  progress: number;
  duration: number;
  done: boolean;
}

export interface SortStore {
  selectedFolder: string | null;
  watchMode: boolean;
  previewMode: boolean;
  stage: 'idle' | 'processing' | 'preview' | 'done' | 'watching';
  filesProcessed: number;
  filesTotal: number;
  foldersDiscovered: FolderDiscovered[];
  particles: Particle[];
  folderTree: FolderTree | null;
  filesSorted: number;
  foldersCreated: number;
  filesUnsorted: number;
  pendingRenames: Record<number, string>;
  recentActivity: Activity[];
  licenseValid: boolean;
  licenseTrial: boolean;
  filesRemaining: number | undefined;
  previewFolders: PreviewFolder[];
  unsortedFiles: PreviewFile[];
}

const initial: SortStore = {
  selectedFolder: null,
  watchMode: false,
  previewMode: true,
  stage: 'idle',
  filesProcessed: 0,
  filesTotal: 0,
  foldersDiscovered: [],
  particles: [],
  folderTree: null,
  filesSorted: 0,
  foldersCreated: 0,
  filesUnsorted: 0,
  pendingRenames: {},
  recentActivity: [],
  licenseValid: true,
  licenseTrial: false,
  filesRemaining: undefined,
  previewFolders: [],
  unsortedFiles: [],
};

export const sortStore = writable<SortStore>(initial);

export function resetSort() {
  sortStore.update(s => ({
    ...s,
    stage: 'idle',
    filesProcessed: 0,
    filesTotal: 0,
    foldersDiscovered: [],
    particles: [],
    folderTree: null,
    filesSorted: 0,
    foldersCreated: 0,
    filesUnsorted: 0,
    pendingRenames: {},
  }));
}
