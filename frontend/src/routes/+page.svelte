<script lang="ts">
  import { open } from '@tauri-apps/plugin-dialog';
  import { open as openPath } from '@tauri-apps/plugin-shell';
  import { runSorter, previewSort, type SortOptions, type SortResult, type PreviewResult } from '../lib/backend';
  import { theme } from '../lib/themeStore';
  import { onMount } from 'svelte';
  
  let selectedFolder: string | null = null;
  let isProcessing = false;
  let error: string | null = null;
  let sortResult: SortResult | null = null;
  let loadingMessage: string | null = null;
  let showResults = false;
  let showSettings = false;

  // Initialize theme on mount
  onMount(() => {
    theme.init();
  });  let clusteringMode: 'automatic' | 'manual' = 'automatic';
  let manualClusterCount = 5;
  let outputPath: string | null = null;
  
  let sortOptions: SortOptions = {
    cluster_sensitivity: 'medium',
    folder_naming_style: 'simple',
    include_subfolders: true
  };

  // Preview functionality
  let previewResult: PreviewResult | null = null;
  let isPreviewLoading = false;
  async function handleFolderSelect() {
    try {
      const picked = await open({ directory: true, multiple: false });
      if (picked) {
        selectedFolder = picked;
        error = null;
      }
    } catch (err) {
      error = 'Failed to select folder';
      console.error('Error selecting folder:', err);
    }
  }

  async function handleRunSorter() {
    if (!selectedFolder) return;
    
    isProcessing = true;
    loadingMessage = 'Analyzing files...';
    error = null;
    
    try {
      sortResult = await runSorter(selectedFolder, sortOptions);
      showResults = true;
      outputPath = selectedFolder; // Files are organized within the same folder
      error = null;
    } catch (err) {
      console.error('Sorter error:', err);
      if (typeof err === 'string') {
        error = err;
      } else if (err instanceof Error) {
        error = err.message;
      } else {
        error = 'An error occurred while sorting files';
      }
      sortResult = null;
    } finally {
      isProcessing = false;
      loadingMessage = null;
    }
  }

  async function handleOpenInFinder() {
    if (outputPath) {
      try {
        await openPath(outputPath);
      } catch (err) {
        console.error('Failed to open in finder:', err);
        error = 'Failed to open folder in Finder. Please check if the folder exists.';
      }
    } else {
      error = 'No output folder path available.';
    }
  }

  function handleBackToSort() {
    showResults = false;
    sortResult = null;
    outputPath = null;
  }

  function toggleClusteringMode(mode: 'automatic' | 'manual') {
    clusteringMode = mode;
  }

  // Preview sort functionality
  async function handlePreviewSort() {
    if (!selectedFolder) return;
    
    isPreviewLoading = true;
    try {
      previewResult = await previewSort(selectedFolder, sortOptions);
      error = null;
    } catch (err) {
      console.error("Preview error:", err);
      error = err instanceof Error ? err.message : "Failed to preview sort";
      previewResult = null;
    } finally {
      isPreviewLoading = false;
    }
  }

  // Update preview when folder or options change
  $: if (selectedFolder && sortOptions) {
    handlePreviewSort();
  }
  // Handle drag and drop
  let isDragOver = false;

  function handleDragOver(event: DragEvent) {
    event.preventDefault();
    isDragOver = true;
  }

  function handleDragLeave(event: DragEvent) {
    event.preventDefault();
    isDragOver = false;
  }

  function handleDrop(event: DragEvent) {
    event.preventDefault();
    isDragOver = false;
    
    const items = event.dataTransfer?.items;
    if (items) {
      for (let i = 0; i < items.length; i++) {
        const item = items[i];
        if (item.kind === 'file') {
          const entry = item.webkitGetAsEntry();
          if (entry && entry.isDirectory) {
            selectedFolder = entry.fullPath;
            error = null;
            break;
          }
        }
      }
    }
  }

  function handleKeyDown(event: KeyboardEvent) {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      if (event.target === document.querySelector('.dropzone')) {
        handleFolderSelect();
      } else if (event.target === document.querySelector('.settings-header')) {
        showSettings = !showSettings;
      }
    }
  }
</script>

<main>
  <!-- Header -->
  <header class="header">
    <div class="header-content">
      <h1 class="app-title">Smart Sort</h1>
      <p class="tagline">Organize your files with one click</p>
    </div>
    <button class="theme-toggle" on:click={theme.toggle} aria-label="Toggle theme">
      {#if $theme === 'dark'}
        <!-- Sun icon for light mode -->
        <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="12" r="5"/>
          <line x1="12" y1="1" x2="12" y2="3"/>
          <line x1="12" y1="21" x2="12" y2="23"/>
          <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/>
          <line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/>
          <line x1="1" y1="12" x2="3" y2="12"/>
          <line x1="21" y1="12" x2="23" y2="12"/>
          <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/>
          <line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>
        </svg>
      {:else}
        <!-- Moon icon for dark mode -->
        <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
        </svg>
      {/if}
    </button>
  </header>

  <!-- Main Content -->
  <div class="content">
    {#if isProcessing}
      <!-- Loading State -->
      <div class="loading-overlay">
        <div class="loading-spinner"></div>
        <div class="loading-message">{loadingMessage}</div>
      </div>
    {/if}

    {#if showResults && sortResult}
      <!-- Results Section -->
      <div class="results-section">
        <div class="success-icon">
          <svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
            <polyline points="22,4 12,14.01 9,11.01"/>
          </svg>
        </div>
        <h2 class="success-title">Files sorted successfully!</h2>
        
        {#if outputPath}
          <div class="output-info">
            <p class="output-path">Output folder: {outputPath}</p>
            <button class="finder-button" on:click={handleOpenInFinder}>
              <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
              </svg>
              Open in Finder
            </button>
          </div>
        {/if}

        <button class="back-button" on:click={handleBackToSort}>
          Sort Another Folder
        </button>
      </div>
    {:else}
      <!-- Main UI -->
      <!-- Dropzone -->
      <div 
        class="dropzone {isDragOver ? 'drag-over' : ''} {selectedFolder ? 'has-selection' : ''}"
        on:click={handleFolderSelect}
        on:keydown={handleKeyDown}
        on:dragover={handleDragOver}
        on:dragleave={handleDragLeave}
        on:drop={handleDrop}
        role="button"
        tabindex="0"
        aria-label="Select or drop a folder to sort"
      >
        <div class="dropzone-content">
          <div class="folder-icon">
            <svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
              {#if selectedFolder}
                <path d="m9 13 3 3 5-5"/>
              {/if}
            </svg>
          </div>
          {#if selectedFolder}
            <h2>Folder Selected</h2>
            <p class="selected-path">{selectedFolder}</p>
            <p class="instruction">Click to select a different folder</p>
          {:else}
            <h2>Drag & Drop a folder here</h2>
            <p class="instruction">or click to select a folder</p>
          {/if}
        </div>
      </div>

      <!-- Clustering Settings -->
      <div class="settings-card">
        <button 
          class="settings-header" 
          on:click={() => showSettings = !showSettings}
          aria-expanded={showSettings}
          aria-controls="settings-content"
        >
          <h3>Clustering Settings</h3>
          <div class="toggle-icon {showSettings ? 'open' : ''}">
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <polyline points="6,9 12,15 18,9"/>
            </svg>
          </div>
        </button>
        
        {#if showSettings}
          <div class="settings-content" id="settings-content">
            <!-- Automatic/Manual Toggle -->
            <div class="setting-group">
              <fieldset>
                <legend class="setting-label">Clustering Mode</legend>
                <div class="toggle-buttons">
                  <button 
                    class="toggle-button {clusteringMode === 'automatic' ? 'active' : ''}"
                    on:click={() => toggleClusteringMode('automatic')}
                  >
                    Automatic
                  </button>
                  <button 
                    class="toggle-button {clusteringMode === 'manual' ? 'active' : ''}"
                    on:click={() => toggleClusteringMode('manual')}
                  >
                    Manual
                  </button>
                </div>
              </fieldset>
            </div>

            {#if clusteringMode === 'manual'}
              <!-- Manual Cluster Count -->
              <div class="setting-group">
                <label class="setting-label" for="cluster-count">Number of clusters</label>
                <input 
                  id="cluster-count"
                  type="number" 
                  bind:value={manualClusterCount} 
                  min="2" 
                  max="20"
                  class="number-input"
                />
              </div>
            {/if}

            <!-- Naming Style -->
            <div class="setting-group">
              <label class="setting-label" for="naming-style">Naming style</label>
              <select id="naming-style" bind:value={sortOptions.folder_naming_style} class="select-input">
                <option value="simple">Semantic</option>
                <option value="descriptive">Numbered</option>
              </select>
            </div>
          </div>
        {/if}
      </div>

      <!-- Error Message -->
      {#if error}
        <div class="error-message" role="alert">
          {error}
        </div>
      {/if}


      <!-- Preview Section -->
      {#if selectedFolder}
        <div class="preview-section">
          {#if isPreviewLoading}
            <div class="preview-loading">
              <div class="loading-spinner"></div>
              <span>Analyzing files...</span>
            </div>
          {:else if previewResult && previewResult.estimated_clusters > 0}
            <div class="preview-result">
              <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
              </svg>
              <span class="preview-text">Preview: <strong>{previewResult.estimated_clusters}</strong> {previewResult.estimated_clusters === 1 ? "folder" : "folders"} will be created from <strong>{previewResult.files_found}</strong> files</span>
            </div>
          {/if}
        </div>
      {/if}      <!-- Run Button -->
      <div class="run-section">
        <button 
          class="run-button" 
          on:click={handleRunSorter}
          disabled={!selectedFolder || isProcessing}
        >
          Run Sorter
        </button>
      </div>
    {/if}
  </div>
</main>

<style>
  @font-face {
    font-family: 'Jacquard24';
    src: url('/fonts/Jacquard_24/Jacquard24-Regular.ttf') format('truetype');
    font-weight: normal;
    font-style: normal;
  }

  @font-face {
    font-family: 'Electrolize';
    src: url('/fonts/Electrolize/Electrolize-Regular.ttf') format('truetype');
    font-weight: normal;
    font-style: normal;
  }


  :global(:root) {
    --bg-primary: #ECEDEC;
    --bg-secondary: #E8E9E8;
    --text-primary: #1f2937;
    --text-secondary: #3C3C4390;
    --text-inverse: #000000;
    --border-color: #9c9fa3;
    --shadow-light: rgba(0, 0, 0, 0.05);
    --shadow-medium: rgba(0, 0, 0, 0.1);
    --run-gradient: linear-gradient(135deg, #afafb5 0%, #6e6b6f 100%);
  }

  :global(.dark) {
    --bg-primary: #000000;
    --bg-secondary: #1c1c1c;
    --text-primary: #f9fafb;
    --text-secondary: #9ca3af;
    --text-inverse: #ffffff;
    --border-color: #374151;
    --shadow-light: rgba(255, 255, 255, 0.5);
    --shadow-medium: rgba(255, 255, 255, 0.1);
    --run-gradient: linear-gradient(135deg, #d1d5db 0%, #4e4a4a 100%);
  }

  :global(body) {
    margin: 0;
    padding: 0;
    font-family: 'Electrolize', -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', sans-serif;
    background: var(--bg-primary);
    color: var(--text-primary);
    min-height: 100vh;
    transition: background 0.3s ease, color 0.3s ease;
  }

  main {
    min-height: 100vh;
    display: flex;
    flex-direction: column;
  }

  /* Header */
  .header {
    padding: 3rem 2rem 2rem;
    text-align: center;
    color: var(--text-inverse);
    position: relative;
  }

  .header-content {
    max-width: 600px;
    margin: 0 auto;
  }

  .app-title {
    font-family: 'Jacquard24', serif;
    font-size: 5rem;
    font-weight: 700;
    margin: 0 0 0.5rem;
    letter-spacing: -0.02em;
  }

  .tagline {
    font-size: 1.2rem;
    font-weight: 400;
    margin: 0;
    opacity: 0.9;
  }

  .theme-toggle {
    position: absolute;
    top: 2rem;
    right: 2rem;
    background: rgba(255, 255, 255, 0.2);
    border: 1px solid rgba(255, 255, 255, 0.3);
    border-radius: 50%;
    width: 48px;
    height: 48px;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    transition: all 0.3s ease;
    color: var(--text-inverse);
    backdrop-filter: blur(10px);
  }

  .theme-toggle:hover {
    background: rgba(255, 255, 255, 0.3);
    transform: scale(1.1);
  }

  /* Content */
  .content {
    flex: 1;
    padding: 2rem;
    max-width: 800px;
    margin: 0 auto;
    width: 100%;
    box-sizing: border-box;
    position: relative;
  }

  /* Dropzone */
  .dropzone {
    background: var(--bg-secondary);
    border: 3px dashed var(--border-color);
    border-radius: 16px;
    padding: 3rem 2rem;
    text-align: center;
    cursor: pointer;
    transition: all 0.3s ease;
    margin-bottom: 2rem;
    box-shadow: 0 4px 6px var(--shadow-light);
  }

  .dropzone:hover,
  .dropzone.drag-over {
    border-color: #667eea;
    background: rgba(102, 126, 234, 0.02);
    transform: translateY(-2px);
    box-shadow: 0 8px 25px var(--shadow-medium);
  }

  .dropzone.has-selection {
    border-color: #10b981;
    background: rgba(16, 185, 129, 0.02);
  }

  .dropzone-content {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 1rem;
  }

  .folder-icon {
    color: #667eea;
    margin-bottom: 0.5rem;
  }

  .dropzone.has-selection .folder-icon {
    color: #10b981;
  }

  .dropzone h2 {
    font-size: 1.5rem;
    font-weight: 600;
    margin: 0;
    color: var(--text-primary);
  }

  .instruction {
    font-size: 1rem;
    color: var(--text-secondary);
    margin: 0;
  }

  .selected-path {
    font-size: 0.9rem;
    color: var(--text-primary);
    background: var(--border-color);
    padding: 0.5rem 1rem;
    border-radius: 8px;
    margin: 0.5rem 0;
    word-break: break-all;
    max-width: 100%;
  }

  /* Settings Card */
  .settings-card {
    background: var(--bg-secondary);
    border-radius: 12px;
    box-shadow: 0 4px 6px var(--shadow-light);
    margin-bottom: 2rem;
    overflow: hidden;
  }

  .settings-header {
    width: 100%;
    padding: 1.5rem;
    cursor: pointer;
    display: flex;
    justify-content: space-between;
    align-items: center;
    background: var(--bg-secondary);
    border: none;
    border-bottom: 1px solid var(--border-color);
    font-family: inherit;
  }

  .settings-header:hover {
    background: var(--border-color);
  }

  .settings-header h3 {
    font-size: 1.1rem;
    font-weight: 600;
    margin: 0;
    color: var(--text-primary);
    text-align: left;
  }

  .toggle-icon {
    transition: transform 0.2s ease;
    color: var(--text-secondary);
  }

  .toggle-icon.open {
    transform: rotate(180deg);
  }

  .settings-content {
    padding: 1.5rem;
    background: var(--bg-secondary);
  }

  .setting-group {
    margin-bottom: 1.5rem;
  }

  .setting-group:last-child {
    margin-bottom: 0;
  }

  .setting-label {
    display: block;
    font-size: 0.9rem;
    font-weight: 500;
    color: var(--text-primary);
    margin-bottom: 0.5rem;
  }

  fieldset {
    border: none;
    padding: 0;
    margin: 0;
  }

  fieldset legend {
    padding: 0;
  }

  /* Toggle Buttons */
  .toggle-buttons {
    display: flex;
    border-radius: 8px;
    overflow: hidden;
    border: 1px solid var(--border-color);
  }

  .toggle-button {
    flex: 1;
    padding: 0.75rem 1rem;
    background: var(--bg-secondary);
    border: none;
    cursor: pointer;
    font-size: 0.9rem;
    font-weight: 500;
    transition: all 0.2s ease;
    color: var(--text-secondary);
  }

  .toggle-button:not(:last-child) {
    border-right: 1px solid var(--border-color);
  }

  .toggle-button:hover {
    background: var(--border-color);
  }

  .toggle-button.active {
    background: #667eea;
    color: white;
  }

  /* Form Inputs */
  .number-input,
  .select-input {
    width: 100%;
    padding: 0.75rem;
    border: 1px solid var(--border-color);
    border-radius: 8px;
    font-size: 0.9rem;
    transition: border-color 0.2s ease;
    background: var(--bg-secondary);
    color: var(--text-primary);
  }

  .number-input:focus,
  .select-input:focus {
    outline: none;
    border-color: #667eea;
    box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
  }

  /* Run Button */
  .run-section {
    display: flex;
    justify-content: center;
    margin-top: 2rem;
  }

  /* Preview Section */
  .preview-section {
    margin-bottom: 1.5rem;
    text-align: center;
  }

  .preview-loading {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0.5rem;
    color: var(--text-secondary);
    font-size: 0.9rem;
  }

  .preview-result {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0.5rem;
    padding: 0.75rem 1.5rem;
    background: rgba(16, 185, 129, 0.1);
    border: 1px solid rgba(16, 185, 129, 0.3);
    border-radius: 8px;
    color: #10b981;
    font-size: 0.9rem;
  }

  .preview-result svg {
    color: #10b981;
  }

  .preview-text {
    color: var(--text-primary);
  }

  .preview-text strong {
    color: #10b981;
    font-weight: 600;
  }

  .loading-spinner {
    width: 16px;
    height: 16px;
    border: 2px solid var(--border-color);
    border-top: 2px solid var(--text-secondary);
    border-radius: 50%;
    animation: spin 1s linear infinite;
  }

  @keyframes spin {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
  }
  .run-button {
    background: var(--run-gradient);
    color: white;
    border: none;
    padding: 1rem 3rem;
    border-radius: 50px;
    font-family: 'Electrolize', -apple-system, BlinkMacSystemFont, sans-serif;
    font-size: 1.1rem;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.3s ease;
    box-shadow: 0 4px 15px var(--shadow-medium);
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }

  .run-button:hover:not(:disabled) {
    transform: translateY(-2px);
    box-shadow: 0 8px 25px rgba(0, 0, 0, 0.15);
  }

  .run-button:disabled {
    background: var(--run-gradient);
    cursor: not-allowed;
    transform: none;
    box-shadow: none;
  }

  /* Loading Overlay */
  .loading-overlay {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(255, 255, 255, 0.95);
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    border-radius: 16px;
    z-index: 10;
  }

  :global(.dark) .loading-overlay {
    background: rgba(45, 55, 72, 0.95);
  }

  .loading-spinner {
    width: 48px;
    height: 48px;
    border: 4px solid var(--border-color);
    border-top: 4px solid #667eea;
    border-radius: 50%;
    animation: spin 1s linear infinite;
    margin-bottom: 1rem;
  }

  @keyframes spin {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
  }

  .loading-message {
    font-size: 1.1rem;
    color: #667eea;
    font-weight: 500;
  }

  /* Results Section */
  .results-section {
    background: var(--bg-secondary);
    border-radius: 16px;
    padding: 3rem 2rem;
    text-align: center;
    box-shadow: 0 4px 6px var(--shadow-light);
  }

  .success-icon {
    color: #10b981;
    margin-bottom: 1.5rem;
  }

  .success-title {
    font-size: 1.8rem;
    font-weight: 600;
    color: var(--text-primary);
    margin: 0 0 2rem;
  }

  .output-info {
    margin: 2rem 0;
    padding: 1.5rem;
    background: var(--border-color);
    border-radius: 12px;
    border: 1px solid var(--border-color);
  }

  .output-path {
    font-size: 0.9rem;
    color: var(--text-secondary);
    margin: 0 0 1rem;
    word-break: break-all;
  }

  .finder-button {
    background: #10b981;
    color: white;
    border: none;
    padding: 0.75rem 1.5rem;
    border-radius: 8px;
    font-size: 0.9rem;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.2s ease;
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
  }

  .finder-button:hover {
    background: #059669;
    transform: translateY(-1px);
  }

  .back-button {
    background: transparent;
    color: #667eea;
    border: 2px solid #667eea;
    padding: 0.75rem 2rem;
    border-radius: 8px;
    font-size: 1rem;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.2s ease;
    margin-top: 1rem;
  }

  .back-button:hover {
    background: #667eea;
    color: white;
  }

  /* Error Message */
  .error-message {
    background: #fef2f2;
    color: #dc2626;
    padding: 1rem 1.5rem;
    border-radius: 8px;
    margin-bottom: 2rem;
    border: 1px solid #fecaca;
    font-size: 0.9rem;
  }

  :global(.dark) .error-message {
    background: #2d1b1b;
    color: #f87171;
    border-color: #4a1b1b;
  }

  /* Responsive */
  @media (max-width: 768px) {
    .header {
      padding: 2rem 1rem 1rem;
    }

    .app-title {
      font-size: 3.5rem;
    }

    .tagline {
      font-size: 1.1rem;
    }

    .content {
      padding: 1rem;
    }

    .dropzone {
      padding: 2rem 1rem;
    }

    .run-button {
      padding: 1rem 2rem;
      font-size: 1rem;
    }

    .theme-toggle {
      top: 1rem;
      right: 1rem;
      width: 40px;
      height: 40px;
    }
  }
</style>
