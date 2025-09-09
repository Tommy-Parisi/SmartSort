<script lang="ts">
  export let showFolderSuccess: boolean = false;
  import { createEventDispatcher } from 'svelte';
  import { open } from '@tauri-apps/plugin-dialog';

  const dispatch = createEventDispatcher();

  let isDragOver = false;
  let error: string | null = null;
  let selectedDir: string | null = null;

  async function selectFolder() {
    try {
      const picked = await open({ directory: true, multiple: false });
      if (picked) {
        error = null;
        selectedDir = picked;
        dispatch('folderSelected', { path: picked });
      }
    } catch (err) {
      error = 'An error occurred while selecting folder';
      console.error('Error selecting folder:', err);
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
    <p>Drag and drop a folder here, or</p>
    <button type="button" on:click|stopPropagation={selectFolder}>
      Browse for folder
    </button>
    {#if selectedDir}
      <p>Selected: {selectedDir}</p>
    {/if}
    {#if error}
      <p class="error">{error}</p>
    {/if}
  </div>
</div>

<style>
  .dropzone {
    border: 2px dashed #ccc;
    border-radius: 8px;
    padding: 2rem;
    text-align: center;
    cursor: pointer;
    transition: all 0.2s ease;
    margin: 2rem 0;
  }
  .dropzone:hover,
  .dropzone.drag-over {
    border-color: #007acc;
    background-color: rgba(0, 122, 204, 0.1);
  }
  .dropzone-content {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 1rem;
    pointer-events: none;
  }
  button {
    pointer-events: all;
    padding: 0.5rem 1rem;
    background: #007acc;
    color: white;
    border: none;
    border-radius: 4px;
    cursor: pointer;
  }
  .error {
    color: #dc3545;
    font-size: 0.875rem;
    margin-top: 1rem;
  }
</style>