<script lang="ts">
  import LogoMark from './LogoMark.svelte';
  import StepIndicator from './StepIndicator.svelte';

  export let step: number = 1;
</script>

<div class="flow">
  <div class="flow-header">
    <LogoMark compact />
    <StepIndicator {step} />
  </div>

  <main class="flow-main">
    <slot />
  </main>

  <footer class="flow-footer">
    <div class="footer-left">
      <slot name="footer-left" />
    </div>
    <div class="footer-center">
      <slot name="footer-center" />
    </div>
    <div class="footer-right">
      <slot name="footer-right" />
    </div>
  </footer>
</div>

<style>
  .flow {
    display: flex;
    flex-direction: column;
    height: 100vh;
    overflow: hidden;
    background: var(--bg);
  }

  .flow-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 20px;
    height: 44px;
    flex-shrink: 0;
    border-bottom: 0.5px solid var(--border);
    background: var(--bg);
  }

  .flow-main {
    flex: 1;
    overflow: hidden;
    min-height: 0;
    display: flex;
    flex-direction: column;
  }

  .flow-footer {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 10px 20px;
    border-top: 0.5px solid var(--border);
    background: var(--bg);
    flex-shrink: 0;
    gap: 12px;
    min-height: 52px;
  }

  .footer-left {
    flex-shrink: 0;
  }

  .footer-center {
    flex: 1;
    min-width: 0;
  }

  .footer-right {
    flex-shrink: 0;
    display: flex;
    gap: 8px;
    align-items: center;
  }
</style>
