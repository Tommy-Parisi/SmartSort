import { Command } from '@tauri-apps/api/shell';

export async function runSorter(folderPath: string) {
  const command = new Command('python3', ['sorter.py', folderPath], {
    cwd: '../backend'
  });

  const output = await command.execute();
  console.log('Python output:', output.stdout);
}