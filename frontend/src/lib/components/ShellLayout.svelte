<script lang="ts">
  import { page } from '$app/stores';
  import { onMount } from 'svelte';
  import LogoMark from './LogoMark.svelte';
  import { theme } from '$lib/themeStore';

  onMount(() => {
    theme.init();
  });
</script>

<div class="shell">
  <aside class="sidebar">
    <div class="sb-logo">
      <LogoMark />
    </div>

    <nav class="sb-nav">
      <a href="/" class:active={$page.url.pathname === '/'}>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7">
          <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
        </svg>
        Sort
      </a>

      <a href="/history" class:active={$page.url.pathname === '/history'}>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7">
          <circle cx="12" cy="12" r="10"/>
          <polyline points="12 6 12 12 16 14"/>
        </svg>
        History
      </a>

      <a href="/watch" class:active={$page.url.pathname === '/watch'}>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7">
          <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>
        </svg>
        Watch mode
      </a>
    </nav>

    <div class="sb-bottom">
      <div class="bottom-row">
        <a href="/settings" class:active={$page.url.pathname === '/settings'} class="settings-link">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7">
            <circle cx="12" cy="12" r="3"/>
            <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>
          </svg>
          Settings
        </a>

        <button
          class="theme-btn"
          on:click={theme.toggle}
          title={$theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
          aria-label="Toggle dark mode"
        >
          {#if $theme === 'dark'}
            <!-- Sun -->
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7">
              <circle cx="12" cy="12" r="5"/>
              <line x1="12" y1="1" x2="12" y2="3"/>
              <line x1="12" y1="21" x2="12" y2="23"/>
              <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/>
              <line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/>
              <line x1="1" y1="12" x2="3" y2="12"/>
              <line x1="21" y1="12" x2="23" y2="12"/>
              <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/>
              <line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>
            </svg>
          {:else}
            <!-- Moon -->
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7">
              <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
            </svg>
          {/if}
        </button>
      </div>
    </div>
  </aside>

  <main class="shell-main">
    <slot />
  </main>
</div>

<style>
  .shell {
    display: flex;
    height: 100vh;
    overflow: hidden;
  }

  .sidebar {
    width: 220px;
  flex-shrink: 0;
    background: var(--bg-secondary);
    border-right: 0.5px solid var(--border);
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }

  .sb-logo {
    padding: 18px 14px 14px;
    border-bottom: 0.5px solid var(--border);
  }

  .sb-nav {
    flex: 1;
    padding: 8px 8px 0;
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .sb-nav a,
  .sb-bottom a {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 6px 10px;
    border-radius: 6px;
    font-size: 12px;
    color: var(--text-secondary);
    text-decoration: none;
    transition: background 100ms, color 100ms;
    border: 0.5px solid transparent;
  }

  .sb-nav a svg,
  .sb-bottom a svg {
    flex-shrink: 0;
    opacity: 0.5;
    transition: opacity 100ms;
  }

  .sb-nav a:hover,
  .sb-bottom a:hover {
    background: var(--hover-bg);
    color: var(--text);
  }

  .sb-nav a:hover svg,
  .sb-bottom a:hover svg {
    opacity: 0.75;
  }

  .sb-nav a.active,
  .sb-bottom a.active {
    background: var(--bg);
    color: var(--text);
    font-weight: 600;
    border-color: var(--border-strong);
  }

  .sb-nav a.active svg,
  .sb-bottom a.active svg {
    opacity: 1;
  }

  .sb-bottom {
    padding: 8px;
    border-top: 0.5px solid var(--border);
  }

  .bottom-row {
    display: flex;
    align-items: center;
    gap: 4px;
  }

  .settings-link {
    flex: 1;
  }

  .theme-btn {
    flex-shrink: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    width: 30px;
    height: 30px;
    border-radius: 6px;
    background: none;
    border: 0.5px solid transparent;
    color: var(--text-secondary);
    cursor: pointer;
    transition: background 100ms, color 100ms;
    padding: 0;
  }

  .theme-btn:hover {
    background: var(--hover-bg);
    color: var(--text);
  }

  .shell-main {
    flex: 1;
    background: var(--bg);
    overflow-y: auto;
    min-width: 0;
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 0 24px;
  }
</style>
