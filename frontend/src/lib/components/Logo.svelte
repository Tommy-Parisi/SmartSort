<script lang="ts">
  export let subtitle: string = '';
</script>

<div class="logo-wrap">
  <h1 class="wordmark">Smart Sort</h1>
  {#if subtitle}
    <p class="subtitle">{subtitle}</p>
  {/if}
</div>

<style>
  .logo-wrap {
    text-align: center;
    padding: 32px 0 24px;
  }

  .wordmark {
    font-family: 'Jacquard24', serif;
    font-size: 56px;
    font-weight: normal;
    margin: 0;
    line-height: 1;
    color: var(--text);
    letter-spacing: 0.01em;
  }

  .subtitle {
    margin: 8px 0 0;
    font-size: 13px;
    color: var(--text-secondary);
  }
</style>
