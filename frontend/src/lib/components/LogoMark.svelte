<script lang="ts">
  export let compact = false;
</script>

<div class="logo-mark" class:compact>
  <svg
    class="mark-icon"
    viewBox="0 0 20 20"
    fill="currentColor"
    overflow="visible"
    aria-hidden="true"
  >
    <!-- Scattered: 8 squares, offset + rotated -->
    <rect x="-0.5" y="-1" width="4" height="4" rx="0.6" opacity="0.28"
          transform="rotate(-12 1.5 1)"/>
    <rect x="5" y="-1.5" width="4" height="4" rx="0.6" opacity="0.28"
          transform="rotate(15 7 0.5)"/>
    <rect x="12" y="-0.5" width="4" height="4" rx="0.6" opacity="0.28"
          transform="rotate(-8 14 1.5)"/>
    <rect x="-1" y="5.5" width="4" height="4" rx="0.6" opacity="0.28"
          transform="rotate(10 1 7.5)"/>
    <rect x="6" y="6" width="4" height="4" rx="0.6" opacity="0.28"
          transform="rotate(-14 8 8)"/>
    <rect x="12" y="6" width="4" height="4" rx="0.6" opacity="0.28"
          transform="rotate(9 14 8)"/>
    <rect x="-1" y="12" width="4" height="4" rx="0.6" opacity="0.28"
          transform="rotate(-9 1 14)"/>
    <rect x="5.5" y="12.5" width="4" height="4" rx="0.6" opacity="0.28"
          transform="rotate(16 7.5 14.5)"/>

    <!-- Snapped: bottom-right only -->
    <rect x="11" y="11" width="4" height="4" rx="0.6"/>
  </svg>
  <span class="wordmark">Smart Sort</span>
</div>

<style>
  .logo-mark {
    display: flex;
    align-items: center;
    gap: 9px;
    color: var(--text);
  }

  .mark-icon {
    width: 32px;
    height: 32px;
    flex-shrink: 0;
  }

  .wordmark {
    font-family: 'Jacquard24', serif;
    font-size: 30px;
    font-weight: normal;
    color: var(--text);
    line-height: 1;
    white-space: nowrap;
    letter-spacing: 0.01em;
  }

  .compact .mark-icon {
    width: 22px;
    height: 22px;
  }

  .compact .wordmark {
    font-size: 26px;
  }
</style>
