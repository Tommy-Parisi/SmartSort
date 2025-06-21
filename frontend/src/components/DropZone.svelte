<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import { invoke } from '@tauri-apps/api/core';

  export let showFolderSuccess = false;

  const dispatch = createEventDispatcher<{
    files: File[];
    folder: string;
  }>();

  let isDragging = false;
  let files: File[] = [];
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
      console.error('Error name:', err?.name);
      console.error('Error message:', err?.message);
      console.error('Error stack:', err?.stack);
      console.error('Error details:', JSON.stringify(err, null, 2));
      showSuccessMessage('An error occurred while selecting folder', false);
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

  function handleDragEnter(event: DragEvent) {
    event.preventDefault();
    isDragging = true;
  }

  function handleDragLeave(event: DragEvent) {
    event.preventDefault();
    isDragging = false;
  }

  function handleDrop(event: DragEvent) {
    event.preventDefault();
    isDragging = false;

    console.log('Drop event triggered');
    console.log('DataTransfer items:', event.dataTransfer?.items);
    console.log('DataTransfer files:', event.dataTransfer?.files);

    // Check if any of the dropped items are folders
    let hasFolders = false;
    let itemCount = 0;
    
    if (event.dataTransfer?.items) {
      itemCount = event.dataTransfer.items.length;
      console.log(`Processing ${itemCount} dropped items`);
      
      for (let i = 0; i < event.dataTransfer.items.length; i++) {
        const item = event.dataTransfer.items[i];
        console.log(`Item ${i}:`, item);
        console.log(`Item kind:`, item.kind);
        console.log(`Item type:`, item.type);
        
        if (item.kind === 'file') {
          // Method 1: Try webkitGetAsEntry for folder detection
          try {
            const entry = item.webkitGetAsEntry?.();
            console.log(`Entry for item ${i}:`, entry);
            if (entry && entry.isDirectory) {
              console.log(`Item ${i} is a directory (webkitGetAsEntry)`);
              hasFolders = true;
              break;
            }
          } catch (e) {
            console.log(`webkitGetAsEntry failed for item ${i}:`, e);
          }
          
          // Method 2: Try getAsFile and check properties
          try {
            const file = item.getAsFile();
            console.log(`File for item ${i}:`, file);
            if (file) {
              console.log(`File name: ${file.name}, size: ${file.size}, type: ${file.type}`);
              // If file has no extension and size is 0, it might be a folder
              if (!file.name.includes('.') && file.size === 0) {
                console.log(`Item ${i} might be a folder (no extension, size 0)`);
                hasFolders = true;
                break;
              }
            }
          } catch (e) {
            console.log(`getAsFile failed for item ${i}:`, e);
          }
        }
      }
    }

    console.log(`Has folders: ${hasFolders}, Item count: ${itemCount}`);

    // If we detected folders or if there are no files, use folder selection
    if (hasFolders || itemCount === 0) {
      console.log('Triggering folder selection dialog');
      handleFolderSelect();
      return;
    }

    // Handle file drops
    if (event.dataTransfer?.files?.length) {
      const droppedFiles = Array.from(event.dataTransfer.files);
      console.log('Dropped files:', droppedFiles);
      dispatch('files', droppedFiles);
      showSuccessMessage(`${droppedFiles.length} file(s) accepted!`);
    } else {
      console.log('No files found in drop event, triggering folder selection');
      handleFolderSelect();
    }
  }

  function handleKeyDown(event: KeyboardEvent) {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      handleFolderSelect();
    }
  }
</script>

<div
  class="drop-zone"
  class:dragging={isDragging}
  class:success={showSuccess}
  role="button"
  tabindex="0"
  on:dragenter={handleDragEnter}
  on:dragleave={handleDragLeave}
  on:dragover|preventDefault
  on:drop={handleDrop}
  on:click={handleFolderSelect}
  on:keydown={handleKeyDown}
  aria-label="Drop files or folders here to organize, or click to select a folder"
>
  <div class="drop-zone-content">
    {#if showSuccess}
      <div class="success-message">
        <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
          <polyline points="22,4 12,14.01 9,11.01"/>
        </svg>
        <p>{successMessage}</p>
      </div>
    {:else}
      <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
      </svg>
      <p>Drop files or folders here to organize</p>
      <span class="click-hint">or click to select a folder</span>
    {/if}
  </div>
</div>

<style>
  .drop-zone {
    background-color: #f5f5f5;
    border: 2px dashed #bbb;
    border-radius: 8px;
    padding: 2rem;
    text-align: center;
    cursor: pointer;
    transition: all 0.2s ease;
    box-shadow: 0 2px 6px rgba(0, 0, 0, 0.05);
    margin: 2rem 0;
    outline: none;
  }

  .drop-zone:hover, .drop-zone.dragging {
    background-color: #eef6ff;
    border-color: #0078d4;
  }

  .drop-zone.success {
    background-color: #f0f9ff;
    border-color: #10b981;
  }

  .drop-zone:focus {
    border-color: #0078d4;
    box-shadow: 0 0 0 2px rgba(0, 120, 212, 0.2);
  }

  .drop-zone-content {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 1rem;
    color: #666;
  }

  .drop-zone-content svg {
    color: #999;
  }

  .success-message svg {
    color: #10b981;
  }

  .success-message p {
    color: #10b981;
    font-weight: 500;
    margin: 0;
  }

  .click-hint {
    font-size: 0.9rem;
    color: #888;
  }
</style> 