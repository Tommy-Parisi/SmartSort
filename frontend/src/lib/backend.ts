import { invoke } from '@tauri-apps/api/core';

export interface SortOptions {
  cluster_sensitivity?: 'low' | 'medium' | 'high';
  folder_naming_style?: 'simple' | 'descriptive' | 'detailed';
  include_subfolders?: boolean;
  dry_run?: boolean;
}

export interface PipelineStats {
  files_ingested: number;
  files_extracted: number;
  extraction_failures: number;
  files_embedded: number;
  files_clustered: number;
  final_clusters: number;
  dry_run: boolean;
}

export interface FolderInfo {
  name: string;
  cluster_id: number;
  files: string[];
  file_count: number;
}

export interface PreviewResult {
  status: string;
  estimated_clusters: number;
  files_found: number;
  message: string;
}

export interface SortResult {
  status: string;
  message: string;
  progress: number;
  stages_completed: number;
  total_stages: number;
  files_processed: number;
  clusters_found: number;
  folders_created: FolderInfo[];
  errors: string[];
  stats: PipelineStats;
}

export async function runSorter(folderPath: string, options?: SortOptions): Promise<SortResult> {
  try {
    console.log('Running sorter on:', folderPath, 'with options:', options);
    const result = await invoke<SortResult>('run_sort', { folderPath, options });
    console.log('Sort result:', result);
    return result;
  } catch (error) {
    console.error('Error running sorter:', error);
    throw error;
  }
}

export async function previewSort(folderPath: string, options?: SortOptions): Promise<PreviewResult> {
  try {
    console.log('Running preview for:', folderPath, 'with options:', options);
    const previewResult = await invoke<PreviewResult>('preview_sort', { folderPath, options });
    console.log('Preview result:', previewResult);
    return previewResult;
  } catch (error) {
    console.error('Error previewing sort:', error);
    throw error;
  }
} 