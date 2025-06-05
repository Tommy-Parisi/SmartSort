<script lang="ts">
  import { onMount } from 'svelte';
  import DropZone from './components/DropZone.svelte';
  import SettingsPanel from './components/SettingsPanel.svelte';
  import { runSorter, previewSort, type SortOptions } from './lib/backend';
  
  let previewCount = 0;
  let selectedFolder: string | null = null;
  let isProcessing = false;
  let error: string | null = null;
  
  let sortOptions: SortOptions = {
    clusterSensitivity: 'medium',
    folderNamingStyle: 'simple',
    includeSubfolders: true
  };

  async function handleFiles(event: CustomEvent<File[]>) {
    // TODO: Handle dropped files
    previewCount = event.detail.length;
  }

  async function handleFolderSelect(event: CustomEvent<string>) {
    selectedFolder = event.detail;
    try {
      previewCount = await previewSort(selectedFolder, sortOptions);
      error = null;
    } catch (err) {
      error = err instanceof Error ? err.message : 'An error occurred';
      previewCount = 0;
    }
  }

  async function handleRunSorter() {
    if (!selectedFolder) return;
    
    isProcessing = true;
    error = null;
    
    try {
      await runSorter(selectedFolder, sortOptions);
    } catch (err) {
      error = err instanceof Error ? err.message : 'An error occurred';
    } finally {
      isProcessing = false;
    }
  }

  function handleOptionsChange(event: CustomEvent<SortOptions>) {
    sortOptions = event.detail;
    if (selectedFolder) {
      handleFolderSelect(new CustomEvent('folder', { detail: selectedFolder }));
    }
  }
</script>

<main>
  <header>
    <h1>Synapse Sorter</h1>
    <button class="settings-button" aria-label="Settings">
      <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="12" cy="12" r="3"/>
        <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/>
      </svg>
    </button>
  </header>

  <div class="content">
    <DropZone on:files={handleFiles} on:folder={handleFolderSelect} />
    <SettingsPanel bind:options={sortOptions} on:change={handleOptionsChange} />
    
    {#if error}
      <div class="error-message">
        {error}
      </div>
    {/if}
    
    <div class="action-bar">
      {#if previewCount > 0}
        <span class="preview-count">{previewCount} Clusters Previewed</span>
      {/if}
      <button 
        class="run-button" 
        on:click={handleRunSorter}
        disabled={!selectedFolder || isProcessing}
      >
        {#if isProcessing}
          Processing...
        {:else}
          Run Sorter
        {/if}
      </button>
    </div>
  </div>
</main>

<style>
  :global(body) {
    margin: 0;
    font-family: 'Segoe UI', 'Inter', system-ui, -apple-system, sans-serif;
    background-color: #ffffff;
    color: #333333;
  }

  main {
    min-height: 100vh;
    display: flex;
    flex-direction: column;
  }

  header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 1rem 2rem;
    background-color: #f8f8f8;
    border-bottom: 1px solid #e0e0e0;
  }

  h1 {
    margin: 0;
    font-size: 1.5rem;
    font-weight: 600;
  }

  .settings-button {
    background: none;
    border: none;
    padding: 0.5rem;
    cursor: pointer;
    color: #666;
    border-radius: 4px;
    transition: background-color 0.2s;
  }

  .settings-button:hover {
    background-color: #e0e0e0;
  }

  .content {
    flex: 1;
    padding: 2rem;
    max-width: 1200px;
    margin: 0 auto;
    width: 100%;
    box-sizing: border-box;
  }

  .action-bar {
    display: flex;
    justify-content: flex-end;
    align-items: center;
    gap: 1rem;
    margin-top: 2rem;
  }

  .preview-count {
    color: #888;
    font-size: 0.9rem;
  }

  .run-button {
    background-color: #0078d4;
    color: white;
    border: none;
    padding: 0.6em 1.2em;
    border-radius: 6px;
    font-size: 1rem;
    cursor: pointer;
    transition: background-color 0.2s;
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  }

  .run-button:hover:not(:disabled) {
    background-color: #106ebe;
  }

  .run-button:disabled {
    background-color: #cccccc;
    cursor: not-allowed;
  }

  .error-message {
    background-color: #fde8e8;
    color: #c53030;
    padding: 1rem;
    border-radius: 4px;
    margin: 1rem 0;
    font-size: 0.9rem;
  }
</style> 