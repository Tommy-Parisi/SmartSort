<script lang="ts">
  export let value: number | string;
  export let label: string;
</script>

<div class="stat-card">
  <span class="value">{value}</span>
  <span class="label">{label}</span>
</div>

<style>
  .stat-card {
    flex: 1;
    border: 0.5px solid var(--border);
    border-radius: 6px;
    padding: 16px 12px;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 4px;
  }

  .value {
    font-size: 28px;
    font-weight: 600;
    color: var(--text);
    line-height: 1;
  }

  .label {
    font-size: 11px;
    color: var(--text-secondary);
    text-align: center;
  }
</style>
