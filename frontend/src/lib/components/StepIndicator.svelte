<script lang="ts">
  export let step: number = 1;
  const steps = ['Analyzing', 'Sorting', 'Review', 'Done'];
</script>

<div class="steps">
  {#each steps as label, i}
    {#if i > 0}<span class="sep">›</span>{/if}
    <span
      class="step"
      class:done={step > i + 1}
      class:current={step === i + 1}
    >{label}</span>
  {/each}
</div>

<style>
  .steps {
    display: flex;
    align-items: center;
    gap: 5px;
  }

  .step {
    font-size: 11px;
    color: var(--text-faint);
  }

  .step.current {
    font-weight: 500;
    color: var(--text);
  }

  .step.done {
    color: var(--accent);
  }

  .sep {
    font-size: 11px;
    color: var(--text-faint);
  }
</style>
