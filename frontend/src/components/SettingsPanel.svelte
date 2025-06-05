<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import type { SortOptions } from '../lib/backend';

  export let options: SortOptions;
  const dispatch = createEventDispatcher<{
    change: SortOptions;
  }>();

  function handleChange() {
    dispatch('change', options);
  }

  const sensitivityOptions = [
    { value: 'low', label: 'Low (Fewer Clusters)' },
    { value: 'medium', label: 'Medium' },
    { value: 'high', label: 'High (More Clusters)' }
  ];

  const namingStyleOptions = [
    { value: 'simple', label: 'Simple (e.g., "Documents")' },
    { value: 'descriptive', label: 'Descriptive (e.g., "Work Documents")' },
    { value: 'detailed', label: 'Detailed (e.g., "Work Documents 2024")' }
  ];
</script>

<div class="settings-panel">
  <h2>Sorting Options</h2>
  
  <div class="settings-group">
    <label for="sensitivity">
      Cluster Sensitivity
      <select
        id="sensitivity"
        bind:value={options.clusterSensitivity}
        on:change={handleChange}
        class="select-input"
      >
        {#each sensitivityOptions as option}
          <option value={option.value}>{option.label}</option>
        {/each}
      </select>
    </label>

    <label for="naming">
      Folder Naming Style
      <select
        id="naming"
        bind:value={options.folderNamingStyle}
        on:change={handleChange}
        class="select-input"
      >
        {#each namingStyleOptions as option}
          <option value={option.value}>{option.label}</option>
        {/each}
      </select>
    </label>

    <label class="checkbox-label">
      <input
        type="checkbox"
        bind:checked={options.includeSubfolders}
        on:change={handleChange}
        class="checkbox-input"
      />
      Include Subfolders
    </label>
  </div>
</div>

<style>
  .settings-panel {
    background-color: #ffffff;
    border: 1px solid #e0e0e0;
    border-radius: 8px;
    padding: 1.5rem;
    margin: 2rem 0;
  }

  h2 {
    margin: 0 0 1.5rem 0;
    font-size: 1.2rem;
    font-weight: 600;
    color: #333;
  }

  .settings-group {
    display: flex;
    flex-direction: column;
    gap: 1.5rem;
  }

  label {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    color: #444;
    font-size: 0.95rem;
  }

  .select-input {
    padding: 0.6rem;
    border: 1px solid #ccc;
    border-radius: 4px;
    background-color: #fff;
    font-size: 0.95rem;
    color: #333;
    cursor: pointer;
    transition: border-color 0.2s;
  }

  .select-input:hover {
    border-color: #999;
  }

  .select-input:focus {
    outline: none;
    border-color: #0078d4;
    box-shadow: 0 0 0 2px rgba(0, 120, 212, 0.1);
  }

  .checkbox-label {
    flex-direction: row;
    align-items: center;
    cursor: pointer;
  }

  .checkbox-input {
    margin-right: 0.5rem;
    width: 1.2rem;
    height: 1.2rem;
    cursor: pointer;
  }
</style> 