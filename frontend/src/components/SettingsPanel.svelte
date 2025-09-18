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
        bind:value={options.cluster_sensitivity}
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
        bind:value={options.folder_naming_style}
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
        bind:checked={options.include_subfolders}
        on:change={handleChange}
        class="checkbox-input"
      />
      Include Subfolders
    </label>
  </div>
</div>

<style>
  .settings-panel {
    background-color: var(--bg-secondary);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    padding: 1.5rem;
    margin: 2rem 0;
    transition: background-color 0.3s ease, border-color 0.3s ease;
  }

  h2 {
    margin: 0 0 1.5rem 0;
    font-size: 1.2rem;
    font-weight: 600;
    color: var(--text-primary);
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
    color: var(--text-primary);
    font-size: 0.95rem;
    font-weight: 500;
  }

  .select-input {
    padding: 0.6rem;
    border: 1px solid var(--border-color);
    border-radius: 6px;
    background-color: var(--bg-primary);
    font-size: 0.95rem;
    color: var(--text-primary);
    cursor: pointer;
    transition: border-color 0.2s, background-color 0.3s ease;
  }

  .select-input:hover {
    border-color: var(--text-secondary);
  }

  .select-input:focus {
    outline: none;
    border-color: var(--accent-color);
    box-shadow: 0 0 0 2px color-mix(in srgb, var(--accent-color) 20%, transparent);
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
    accent-color: var(--accent-color);
  }

  /* Dark theme specific styles for select options */
  :global([data-theme="dark"]) .select-input option {
    background-color: var(--bg-secondary);
    color: var(--text-primary);
  }
</style>
