import { Command } from '@tauri-apps/plugin-shell';

export async function runSorter(folderPath: string) {
  const command = Command.create('python3', ['sorter.py', folderPath], {
    cwd: '../backend'
  });

  const output = await command.execute();
  console.log('Python output:', output.stdout);
}