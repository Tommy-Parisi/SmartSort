<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  export let sortResult: { folders: { name: string; files: string[] }[] };
  const dispatch = createEventDispatcher();
  let openFolders: Record<string, boolean> = {};

  function toggleFolder(name: string) {
    openFolders[name] = !openFolders[name];
  }
</script>

<div class="results-container">
  <div class="results-header">
    <h2>Sort Complete</h2>
    <button class="back-button" on:click={() => dispatch('back')}>← Back to Sort</button>
  </div>
  <div class="filesystem-view">
    {#each sortResult.folders as folder}
      <div class="folder-block">
        <div
          class="folder-header"
          role="button"
          tabindex="0"
          aria-expanded={openFolders[folder.name]}
          on:click={() => toggleFolder(folder.name)}
          on:keydown={(e) => e.key === 'Enter' && toggleFolder(folder.name)}
        >
          <svg class="folder-icon" xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
          </svg>
          <span class="folder-name">{folder.name}</span>
          <span class="folder-toggle">{openFolders[folder.name] ? '▼' : '▶'}</span>
        </div>
        {#if openFolders[folder.name]}
          <ul class="file-list">
            {#each folder.files as file}
              <li class="file-item">
                <svg class="file-icon" xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                  <polyline points="14,2 14,8 20,8"/>
                </svg>
                <span>{file}</span>
              </li>
            {/each}
          </ul>
        {/if}
      </div>
    {/each}
  </div>
</div>

<style>
  .results-container {
    background: #f8f9fa;
    border-radius: 12px;
    padding: 2rem;
    box-shadow: 0 2px 12px rgba(0,0,0,0.06);
    max-width: 700px;
    margin: 2rem auto;
  }
  .results-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 2rem;
  }
  .results-header h2 {
    margin: 0;
    font-size: 1.4rem;
    font-weight: 600;
  }
  .back-button {
    background: none;
    border: none;
    color: #0078d4;
    font-size: 1rem;
    cursor: pointer;
    font-weight: 500;
    padding: 0.5rem 1rem;
    border-radius: 6px;
    transition: background 0.2s;
  }
  .back-button:hover {
    background: #e6f0fa;
  }
  .filesystem-view {
    margin-top: 1rem;
  }
  .folder-block {
    background: #fff;
    border-radius: 8px;
    margin-bottom: 1.2rem;
    box-shadow: 0 1px 4px rgba(0,0,0,0.04);
    overflow: hidden;
  }
  .folder-header {
    display: flex;
    align-items: center;
    gap: 0.7rem;
    padding: 1rem 1.2rem;
    cursor: pointer;
    font-weight: 500;
    font-size: 1.1rem;
    background: #f3f6fa;
    border-bottom: 1px solid #e9ecef;
    user-select: none;
    transition: background 0.2s;
  }
  .folder-header:hover {
    background: #e6f0fa;
  }
  .folder-icon {
    color: #0078d4;
  }
  .folder-name {
    flex: 1;
  }
  .folder-toggle {
    font-size: 1.1rem;
    color: #888;
  }
  .file-list {
    list-style: none;
    margin: 0;
    padding: 0.7rem 2rem 1rem 2.5rem;
    background: #fff;
  }
  .file-item {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.3rem 0;
    font-size: 1rem;
    color: #444;
  }
  .file-icon {
    color: #888;
  }
</style>