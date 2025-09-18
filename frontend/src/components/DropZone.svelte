<script lang="ts">
  export let showFolderSuccess: boolean = false;
  export let onFolderSelected: (path: string) => void;
  
  let isDragOver = false;
  let error: string | null = null;
  let selectedDir: string | null = null;

  async function selectFolder() {
    console.log('selectFolder called');
    console.log('onFolderSelected prop:', onFolderSelected);
    
    try {
      // Check if we're in a Tauri environment
      if (typeof window !== 'undefined' && '__TAURI__' in window) {
        console.log('Tauri environment detected');
        
        // Use the core Tauri API
        const { invoke } = await import('@tauri-apps/api/core');
        console.log('invoke function imported:', typeof invoke);
        
        // Call our custom Tauri command
        const picked = await invoke('select_folder');
        console.log('Folder picked:', picked);
        
        if (picked && typeof picked === 'string') {
          error = null;
          selectedDir = picked;
          
          if (typeof onFolderSelected === 'function') {
            console.log('Calling onFolderSelected with:', picked);
            onFolderSelected(picked);
            console.log('onFolderSelected called successfully');
          } else {
            console.error('onFolderSelected is not a function:', onFolderSelected);
          }
        }
      } else {
        // Fallback for non-Tauri environment
        console.log('Not in Tauri environment, using fallback');
        error = 'Folder selection is only available in the desktop app. Please use Tauri dev mode.';
      }
    } catch (err) {
      console.error('Error in selectFolder:', err);
      error = 'An error occurred while selecting folder: ' + (err as Error).message;
    }
  }
</script>

<div
  class="dropzone {isDragOver ? 'drag-over' : ''}"
  role="button"
  tabindex="0"
  on:click={selectFolder}
  on:keydown={(e) => e.key === 'Enter' && selectFolder()}
>
  <div class="dropzone-content">
    <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
      <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
    </svg>
    <h2>Select Folder</h2>
    <p>Click to browse for a folder</p>
    <button type="button" on:click|stopPropagation={selectFolder}>
      Browse for folder
    </button>
    {#if selectedDir}
      <p class="selected-path">Selected: {selectedDir}</p>
    {/if}
    {#if error}
      <p class="error">{error}</p>
    {/if}
  </div>
</div>

<style>
  .dropzone {
    border: 2px dashed var(--border-color);
    border-radius: 8px;
    padding: 2rem;
    text-align: center;
    cursor: pointer;
    transition: all 0.3s ease;
    margin: 2rem 0;
    background-color: var(--bg-primary);
    color: var(--text-secondary);
  }
  
  .dropzone:hover,
  .dropzone.drag-over {
    border-color: var(--accent-color);
    background-color: color-mix(in srgb, var(--accent-color) 10%, var(--bg-primary));
  }
  
  .dropzone-content {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 1rem;
    pointer-events: none;
  }
  
  .dropzone h2 {
    color: var(--text-primary);
    margin: 0;
    font-size: 1.5rem;
  }
  
  .dropzone p {
    color: var(--text-secondary);
    margin: 0;
  }
  
  button {
    pointer-events: all;
    padding: 0.6rem 1.2rem;
    background: var(--accent-color);
    color: white;
    border: none;
    border-radius: 6px;
    cursor: pointer;
    font-size: 1rem;
    transition: background-color 0.2s;
    box-shadow: 0 2px 4px var(--shadow);
  }
  
  button:hover {
    background: var(--accent-hover);
  }
  
  .error {
    color: var(--error-text);
    font-size: 0.875rem;
    margin-top: 1rem;
    pointer-events: all;
  }
  
  .selected-path {
    color: #10b981; /* Green for success - works in both themes */
    font-size: 0.875rem;
    margin-top: 1rem;
    word-break: break-all;
    pointer-events: all;
  }
</style>
