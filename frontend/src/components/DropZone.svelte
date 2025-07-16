<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import { invoke } from '@tauri-apps/api/core';

  console.log('FileSelector component loaded');

  export let showFolderSuccess = false;

  const dispatch = createEventDispatcher<{
    files: File[];
    folder: string;
  }>();

  let showSuccess = false;
  let successMessage = '';
  let successTimeout: number | null = null;

  async function handleFolderSelect() {
    try {
      console.log('Attempting to select folder...');
      const response = await invoke<string>('select_folder');
      console.log('Raw response from invoke:', response);
      console.log('Response type:', typeof response);
      console.log('Response length:', response?.length);
      
      if (!response) {
        throw new Error('No response received from folder selection');
      }
      
      console.log('Folder selected successfully:', response);
      dispatch('folder', response);
      showSuccessMessage('Folder selected successfully!', true);
    } catch (err) {
      console.error('Error selecting folder:', err);
      console.error('Error type:', typeof err);

      if (err instanceof Error) {
        console.error('Error name:', err.name);
        console.error('Error message:', err.message);
        console.error('Error stack:', err.stack);
      }

      showSuccessMessage('An error occurred while selecting folder', false);
    }
  }

  async function handleFileSelect() {
    try {
      console.log('Attempting to select files...');
      const filePaths = await invoke<string[]>('select_files');
      console.log('Files selected:', filePaths);
      
      if (!filePaths || filePaths.length === 0) {
        throw new Error('No files selected');
      }
      
      // Convert file paths to File objects (mock for now)
      const files = filePaths.map(path => {
        const fileName = path.split('/').pop() || path.split('\\').pop() || 'unknown';
        return new File([''], fileName, { type: 'application/octet-stream' });
      });
      
      console.log('Files processed:', files);
      dispatch('files', files);
      showSuccessMessage(`${files.length} file(s) selected!`, false);
    } catch (err) {
      console.error('Error selecting files:', err);
      showSuccessMessage('An error occurred while selecting files', false);
    }
  }

  function showSuccessMessage(message: string, persistent: boolean = false) {
    if (successTimeout) {
      clearTimeout(successTimeout);
      successTimeout = null;
    }
    
    successMessage = message;
    showSuccess = true;
    
    if (!persistent) {
      successTimeout = setTimeout(() => {
        showSuccess = false;
      }, 3000);
    }
  }

  // Watch for external success state
  $: if (showFolderSuccess) {
    showSuccessMessage('Folder selected successfully!', true);
  }
</script>

<div class="file-selector">
  {#if showSuccess}
    <div class="success-message">
      <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
        <polyline points="22,4 12,14.01 9,11.01"/>
      </svg>
      <p>{successMessage}</p>
    </div>
  {/if}

  <div class="selector-content">
    <div class="header">
      <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
      </svg>
      <h2>Select Files or Folder</h2>
      <p>Choose what you'd like to organize</p>
    </div>

    <div class="action-buttons">
      <button class="action-button folder-button" on:click={handleFolderSelect}>
        <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
        </svg>
        Select Folder
      </button>
      
      <button class="action-button file-button" on:click={handleFileSelect}>
        <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/>
          <polyline points="14,2 14,8 20,8"/>
        </svg>
        Select Files
      </button>
    </div>
  </div>
</div>

<style>
  .file-selector {
    background-color: #f8f9fa;
    border: 2px solid #e9ecef;
    border-radius: 12px;
    padding: 2rem;
    text-align: center;
    margin: 2rem 0;
    transition: all 0.2s ease;
  }

  .file-selector:hover {
    border-color: #0078d4;
    box-shadow: 0 4px 12px rgba(0, 120, 212, 0.1);
  }

  .success-message {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0.5rem;
    background-color: #f0f9ff;
    color: #10b981;
    padding: 1rem;
    border-radius: 8px;
    margin-bottom: 1.5rem;
    border: 1px solid #10b981;
  }

  .success-message svg {
    color: #10b981;
  }

  .success-message p {
    color: #10b981;
    font-weight: 500;
    margin: 0;
  }

  .selector-content {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 1.5rem;
  }

  .header {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.5rem;
  }

  .header svg {
    color: #6c757d;
  }

  .header h2 {
    margin: 0;
    font-size: 1.5rem;
    font-weight: 600;
    color: #333;
  }

  .header p {
    margin: 0;
    color: #6c757d;
    font-size: 0.95rem;
  }

  .action-buttons {
    display: flex;
    gap: 1rem;
    justify-content: center;
    flex-wrap: wrap;
  }

  .action-button {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 1rem 2rem;
    border: none;
    border-radius: 8px;
    font-size: 1rem;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.2s ease;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
    min-width: 160px;
  }

  .folder-button {
    background-color: #0078d4;
    color: white;
  }

  .folder-button:hover {
    background-color: #106ebe;
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(0, 120, 212, 0.2);
  }

  .file-button {
    background-color: #ffffff;
    color: #333;
    border: 2px solid #dee2e6;
  }

  .file-button:hover {
    background-color: #f8f9fa;
    border-color: #0078d4;
    color: #0078d4;
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  }
</style> 