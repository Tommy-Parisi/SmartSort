<script lang="ts">
  export let checked: boolean = false;
  export let label: string = '';
  export let id: string = '';

  let uid = id || `toggle-${Math.random().toString(36).slice(2)}`;
</script>

<label class="toggle-row" for={uid}>
  <span class="label">{label}</span>
  <div class="track {checked ? 'on' : ''}">
    <input
      type="checkbox"
      bind:checked
      {id}
      on:change
    />
    <div class="thumb"></div>
  </div>
</label>

<style>
  .toggle-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 10px 0;
    cursor: pointer;
    gap: 16px;
  }

  .label {
    font-size: 13px;
    color: var(--text);
    flex: 1;
  }

  .track {
    position: relative;
    width: 36px;
    height: 20px;
    border-radius: 10px;
    background: var(--border-strong);
    transition: background 0.2s;
    flex-shrink: 0;
  }

  .track.on {
    background: var(--accent);
  }

  .track input {
    position: absolute;
    opacity: 0;
    width: 0;
    height: 0;
  }

  .thumb {
    position: absolute;
    top: 2px;
    left: 2px;
    width: 16px;
    height: 16px;
    border-radius: 50%;
    background: white;
    transition: transform 0.2s;
    pointer-events: none;
  }

  .track.on .thumb {
    transform: translateX(16px);
  }
</style>
