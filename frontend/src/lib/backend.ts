import { invoke } from '@tauri-apps/api/core';

export interface SortOptions {
  clusterSensitivity: 'low' | 'medium' | 'high';
  folderNamingStyle: 'simple' | 'descriptive' | 'detailed';
  includeSubfolders: boolean;
}

export interface SortResult {
  folders: {
    name: string;
    files: string[];
  }[];
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

export async function previewSort(folderPath: string, options?: SortOptions): Promise<number> {
  try {
    console.log('Running preview for:', folderPath, 'with options:', options);
    const clusterCount = await invoke<number>('preview_sort', { folderPath, options });
    console.log('Preview result:', clusterCount);
    return clusterCount;
  } catch (error) {
    console.error('Error previewing sort:', error);
    throw error;
  }
} 