<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  export let filesRemaining: number | undefined = undefined;
  const dispatch = createEventDispatcher<{ activate: void }>();
</script>

<div class="trial-banner">
  <span>Trial: sorts up to 100 files{filesRemaining !== undefined ? ` · ${filesRemaining} remaining` : ''}.</span>
  <button class="activate-link" on:click={() => dispatch('activate')}>Activate license →</button>
</div>

<style>
  .trial-banner {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    padding: 8px 16px;
    background: var(--bg-secondary);
    border: 0.5px solid var(--border);
    border-radius: 6px;
    font-size: 12px;
    color: var(--text-secondary);
    margin: 8px 0;
  }

  .activate-link {
    background: none;
    border: none;
    padding: 0;
    color: var(--accent);
    font-size: 12px;
    cursor: pointer;
  }

  .activate-link:hover {
    text-decoration: underline;
  }
</style>
