<script lang="ts">
  import SortResults from '../../components/SortResults.svelte';
  import { sortResultStore } from '../../lib/sortResultStore';
  import { onMount } from 'svelte';

  let sortResult: { folders: { name: string; files: string[] }[] } | null = null;

  onMount(() => {
    const unsubscribe = sortResultStore.subscribe(val => {
      sortResult = val;
    });
    return unsubscribe;
  });

  function handleBack() {
    window.location.href = '/';
  }
</script>

{#if sortResult && sortResult.folders}
    <SortResults sortResult={sortResult} on:back={handleBack} />
{:else}
    <p>No results to display.</p>
{/if}
