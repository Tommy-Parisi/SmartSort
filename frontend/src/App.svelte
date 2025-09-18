<script lang="ts">
  import { onMount } from 'svelte';
  import DropZone from './components/DropZone.svelte';
  import SettingsPanel from './components/SettingsPanel.svelte';
  import { runSorter, previewSort, type SortOptions } from './lib/backend';
  import { theme } from './lib/themeStore';
  
  let previewCount = 0;
  let selectedFolder: string | null = null;
  let isProcessing = false;
  let error: string | null = null;
  let showFolderSuccess = false;
  
  let sortOptions: SortOptions = {
    cluster_sensitivity: 'medium',
    folder_naming_style: 'simple',
    include_subfolders: true
  };

  onMount(() => {
    theme.init();
  });

  // Simple callback function for folder selection
  function handleFolderSelection(path: string) {
    console.log('handleFolderSelection called with:', path);
    selectedFolder = path;
    showFolderSuccess = true;
    setTimeout(() => {
      showFolderSuccess = false;
    }, 100);
    
    // Update preview count
    previewSort(selectedFolder, sortOptions)
      .then(count => {
        previewCount = count;
        error = null;
        console.log('Preview count updated to:', previewCount);
        console.log('selectedFolder is now:', selectedFolder);
      })
      .catch(err => {
        error = err instanceof Error ? err.message : 'An error occurred';
        previewCount = 0;
        console.error('Preview error:', err);
      });
  }

  async function handleFiles(event: CustomEvent<File[]>) {
    previewCount = event.detail.length;
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
      handleFolderSelection(selectedFolder);
    }
  }

  function toggleTheme() {
    theme.toggle();
  }

  // Debug log
  console.log('App.svelte loaded, handleFolderSelection function:', handleFolderSelection);
</script>

<main>
  <header>
    <h1>Synapse Sorter</h1>
    <div class="header-controls">
      <button class="theme-toggle" on:click={toggleTheme} aria-label="Toggle theme">
        {#if $theme === 'light'}
          <!-- Moon icon for dark mode -->
          <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
          </svg>
        {:else}
          <!-- Sun icon for light mode -->
          <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="5"/>
            <path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/>
          </svg>
        {/if}
      </button>
      <button class="settings-button" aria-label="Settings">
        <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="12" r="3"/>
          <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/>
        </svg>
      </button>
    </div>
  </header>

  <div class="content">
    <DropZone 
      {showFolderSuccess}
      onFolderSelected={handleFolderSelection}
    />
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
        {:else if !selectedFolder}
          No folder selected
        {:else}
          Run Sorter
        {/if}
      </button>
    </div>

    {#if selectedFolder}
      <p>isProcessing: {isProcessing ? 'true' : 'false'}</p>
      <p>selectedFolder: {selectedFolder}</p>
    {/if}
  </div>
</main>

<style>
  /* CSS Variables for theming */
  :global(:root) {
    --bg-primary: #ffffff;
    --bg-secondary: #f8f8f8;
    --bg-tertiary: #e0e0e0;
    --text-primary: #333333;
    --text-secondary: #666666;
    --text-muted: #888888;
    --border-color: #e0e0e0;
    --accent-color: #0078d4;
    --accent-hover: #106ebe;
    --error-bg: #fde8e8;
    --error-text: #c53030;
    --shadow: rgba(0, 0, 0, 0.1);
  }

  :global([data-theme="dark"]) {
    --bg-primary: #1a1a1a;
    --bg-secondary: #2d2d2d;
    --bg-tertiary: #404040;
    --text-primary: #e5e5e5;
    --text-secondary: #b8b8b8;
    --text-muted: #888888;
    --border-color: #404040;
    --accent-color: #4a9eff;
    --accent-hover: #357abd;
    --error-bg: #4a1a1a;
    --error-text: #ff6b6b;
    --shadow: rgba(0, 0, 0, 0.3);
  }

  :global(body) {
    margin: 0;
    font-family: 'Segoe UI', 'Inter', system-ui, -apple-system, sans-serif;
    background-color: var(--bg-primary);
    color: var(--text-primary);
    transition: background-color 0.3s ease, color 0.3s ease;
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
    background-color: var(--bg-secondary);
    border-bottom: 1px solid var(--border-color);
    transition: background-color 0.3s ease, border-color 0.3s ease;
  }

  h1 {
    margin: 0;
    font-size: 1.5rem;
    font-weight: 600;
    color: var(--text-primary);
  }

  .header-controls {
    display: flex;
    gap: 0.5rem;
    align-items: center;
  }

  .theme-toggle,
  .settings-button {
    background: none;
    border: none;
    padding: 0.5rem;
    cursor: pointer;
    color: var(--text-secondary);
    border-radius: 6px;
    transition: background-color 0.2s, color 0.2s;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .theme-toggle:hover,
  .settings-button:hover {
    background-color: var(--bg-tertiary);
    color: var(--text-primary);
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
    color: var(--text-muted);
    font-size: 0.9rem;
  }

  .run-button {
    background-color: var(--accent-color);
    color: white;
    border: none;
    padding: 0.6em 1.2em;
    border-radius: 6px;
    font-size: 1rem;
    cursor: pointer;
    transition: background-color 0.2s;
    box-shadow: 0 2px 4px var(--shadow);
  }

  .run-button:hover:not(:disabled) {
    background-color: var(--accent-hover);
  }

  .run-button:disabled {
    background-color: var(--text-muted);
    cursor: not-allowed;
  }

  .error-message {
    background-color: var(--error-bg);
    color: var(--error-text);
    padding: 1rem;
    border-radius: 4px;
    margin: 1rem 0;
    font-size: 0.9rem;
  }
</style>
