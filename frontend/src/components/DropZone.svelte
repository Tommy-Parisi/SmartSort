<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import { open } from '@tauri-apps/api/dialog';

  const dispatch = createEventDispatcher<{
    files: File[];
    folder: string;
  }>();

  let isDragging = false;
  let files: File[] = [];

  async function handleFolderSelect() {
    try {
      const selected = await open({
        directory: true,
        multiple: false
      });
      
      if (selected) {
        dispatch('folder', selected as string);
      }
    } catch (error) {
      console.error('Error selecting folder:', error);
    }
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
    
    if (event.dataTransfer?.items) {
      const droppedFiles: File[] = [];
      for (const item of event.dataTransfer.items) {
        if (item.kind === 'file') {
          const file = item.getAsFile();
          if (file) droppedFiles.push(file);
        }
      }
      files = droppedFiles;
      dispatch('files', files);
    }
  }
</script>

<div
  class="drop-zone"
  class:dragging={isDragging}
  on:dragenter={handleDragEnter}
  on:dragleave={handleDragLeave}
  on:dragover|preventDefault
  on:drop={handleDrop}
  on:click={handleFolderSelect}
>
  <div class="drop-zone-content">
    <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
      <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
    </svg>
    <p>Drop files or folders here to organize</p>
    <span class="click-hint">or click to select a folder</span>
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
  }

  .drop-zone:hover, .drop-zone.dragging {
    background-color: #eef6ff;
    border-color: #0078d4;
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

  .click-hint {
    font-size: 0.9rem;
    color: #888;
  }
</style> 