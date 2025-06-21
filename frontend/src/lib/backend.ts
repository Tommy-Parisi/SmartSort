import { invoke } from '@tauri-apps/api/core';

export interface SortOptions {
  clusterSensitivity: 'low' | 'medium' | 'high';
  folderNamingStyle: 'simple' | 'descriptive' | 'detailed';
  includeSubfolders: boolean;
}

export async function runSorter(folderPath: string, options: SortOptions): Promise<void> {
  try {
    // For now, just log the operation
    // In the future, this could integrate with the Python backend
    console.log('Running sorter on:', folderPath);
    console.log('Options:', options);
    
    // TODO: Implement actual sorting logic
    throw new Error('Sorting functionality not yet implemented');
  } catch (error) {
    console.error('Error running sorter:', error);
    throw error;
  }
}

export async function previewSort(folderPath: string, options: SortOptions): Promise<number> {
  try {
    console.log('Running preview for:', folderPath);
    console.log('Options:', options);
    
    // Use the new Rust command instead of Python
    const clusterCount = await invoke<number>('preview_sort', {
      folderPath,
      options
    });
    
    console.log('Preview result:', clusterCount);
    return clusterCount;
  } catch (error) {
    console.error('Error previewing sort:', error);
    throw error;
  }
} 