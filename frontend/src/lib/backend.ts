import { Command } from '@tauri-apps/api/shell';

export interface SortOptions {
  clusterSensitivity: 'low' | 'medium' | 'high';
  folderNamingStyle: 'simple' | 'descriptive' | 'detailed';
  includeSubfolders: boolean;
}

export async function runSorter(folderPath: string, options: SortOptions): Promise<void> {
  try {
    const args = [
      'sorter.py',
      folderPath,
      '--sensitivity', options.clusterSensitivity,
      '--naming-style', options.folderNamingStyle,
      options.includeSubfolders ? '--include-subfolders' : '--no-subfolders'
    ];

    const command = new Command('python3', args);
    const output = await command.execute();

    if (output.code !== 0) {
      throw new Error(`Sorter failed with code ${output.code}: ${output.stderr}`);
    }

    console.log('Sorter completed successfully:', output.stdout);
  } catch (error) {
    console.error('Error running sorter:', error);
    throw error;
  }
}

export async function previewSort(folderPath: string, options: SortOptions): Promise<number> {
  try {
    const args = [
      'sorter.py',
      folderPath,
      '--preview',
      '--sensitivity', options.clusterSensitivity,
      '--naming-style', options.folderNamingStyle,
      options.includeSubfolders ? '--include-subfolders' : '--no-subfolders'
    ];

    const command = new Command('python3', args);
    const output = await command.execute();

    if (output.code !== 0) {
      throw new Error(`Preview failed with code ${output.code}: ${output.stderr}`);
    }

    // Parse the number of clusters from the output
    const match = output.stdout.match(/Found (\d+) clusters/);
    return match ? parseInt(match[1], 10) : 0;
  } catch (error) {
    console.error('Error previewing sort:', error);
    throw error;
  }
} 