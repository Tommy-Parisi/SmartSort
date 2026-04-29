<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { goto } from '$app/navigation';
  import { open } from '@tauri-apps/plugin-dialog';
  import ShellLayout from '$lib/components/ShellLayout.svelte';
  import { sortStore } from '$lib/stores/sort';
  import {
    tauriGetDaemonStatus,
    tauriStartDaemon,
    tauriStopDaemon,
    onDaemonFilePlaced,
    type DaemonFilePlacedEvent,
  } from '$lib/tauri';
  import type { UnlistenFn } from '@tauri-apps/api/event';

  let store = $sortStore;
  $: store = $sortStore;

  let watchedFolders: string[] = [];
  let recentActivity: Array<{ filename: string; folder_name: string; timestamp: number }> = [];
  let unlistener: UnlistenFn | undefined;

  function timeAgo(ts: number): string {
    const diff = Math.floor((Date.now() - ts * 1000) / 1000);
    if (diff < 60) return `${diff}s ago`;
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
    return `${Math.floor(diff / 3600)}h ago`;
  }

  let interval: ReturnType<typeof setInterval>;

  onMount(async () => {
    try {
      const status = await tauriGetDaemonStatus();
      watchedFolders = status.watchedFolders;
      recentActivity = status.recentActivity.slice(-20).reverse();
    } catch {
      if (store.selectedFolder) watchedFolders = [store.selectedFolder];
    }

    unlistener = await onDaemonFilePlaced((e: DaemonFilePlacedEvent) => {
      recentActivity = [e, ...recentActivity].slice(0, 20);
      sortStore.update(s => ({
        ...s,
        recentActivity: [
          { filename: e.filename, folder_name: e.folder_name, timestamp: e.timestamp },
          ...s.recentActivity,
        ].slice(0, 20),
      }));
    });

    interval = setInterval(() => {
      recentActivity = [...recentActivity];
    }, 30000);
  });

  onDestroy(() => {
    if (unlistener) unlistener();
    clearInterval(interval);
  });

  async function addFolder() {
    try {
      const picked = await open({ directory: true, multiple: false });
      if (picked && typeof picked === 'string') {
        const next = [...watchedFolders, picked];
        await tauriStartDaemon(next);
        watchedFolders = next;
      }
    } catch (e) {
      console.error(e);
    }
  }

  async function removeFolder(path: string) {
    const next = watchedFolders.filter(f => f !== path);
    watchedFolders = next;
    try {
      if (next.length > 0) {
        await tauriStartDaemon(next);
      } else {
        await tauriStopDaemon();
      }
    } catch (e) {
      console.error(e);
    }
  }

  $: totalToday = recentActivity.filter(a => {
    const d = new Date(a.timestamp * 1000);
    const now = new Date();
    return d.getDate() === now.getDate() && d.getMonth() === now.getMonth();
  }).length;

  $: isWatching = watchedFolders.length > 0;
</script>

<ShellLayout>
  <div class="content">

    <!-- Status header -->
    <div class="status-header">
      <div class="status-dot" class:active={isWatching}></div>
      <span class="status-text">
        {#if isWatching}
          Watching {watchedFolders.length} {watchedFolders.length === 1 ? 'folder' : 'folders'} · {totalToday} files sorted today
        {:else}
          Not watching — add a folder to start
        {/if}
      </span>
    </div>

    <!-- Watched folders -->
    <section class="section">
      <p class="section-label">Watched folders</p>
      <div class="watched-list">
        {#each watchedFolders as folder}
          <div class="watched-row">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7">
              <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
            </svg>
            <span class="folder-path">{folder}</span>
            <button class="btn-remove" on:click={() => removeFolder(folder)}>Remove</button>
          </div>
        {/each}
        <button class="btn-add" on:click={addFolder}>+ Add folder</button>
      </div>
    </section>

    <!-- Recent activity -->
    <section class="section">
      <p class="section-label">Recent activity</p>
      {#if recentActivity.length === 0}
        <p class="empty">No files sorted yet.</p>
      {:else}
        <div class="activity-list">
          {#each recentActivity as item}
            <div class="activity-row">
              <span class="activity-filename">{item.filename}</span>
              <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="5" y1="12" x2="19" y2="12"/><polyline points="12,5 19,12 12,19"/>
              </svg>
              <span class="activity-folder">{item.folder_name}</span>
              <span class="activity-time">{timeAgo(item.timestamp)}</span>
            </div>
          {/each}
        </div>
      {/if}
    </section>

  </div>
</ShellLayout>

<style>
  .content {
    padding: 24px;
    width: 100%;
    max-width: 600px;
    display: flex;
    flex-direction: column;
    gap: 20px;
  }

  .status-header {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .status-dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: var(--border-strong);
    flex-shrink: 0;
  }

  .status-dot.active {
    background: var(--accent);
  }

  .status-text {
    font-size: 12px;
    color: var(--text-secondary);
  }

  .section {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .section-label {
    margin: 0;
    font-size: 10px;
    font-weight: 600;
    color: var(--text-secondary);
    letter-spacing: 0.06em;
  }

  .watched-list {
    border: 0.5px solid var(--border);
    border-radius: 9px;
    overflow: hidden;
  }

  .watched-row {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 10px 12px;
    border-bottom: 0.5px solid var(--border);
  }

  .folder-path {
    flex: 1;
    font-size: 12px;
    font-family: monospace;
    color: var(--text);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .btn-remove {
    background: none;
    border: 0.5px solid var(--border-strong);
    border-radius: 4px;
    padding: 3px 10px;
    font-size: 11px;
    cursor: pointer;
    color: var(--text-secondary);
    flex-shrink: 0;
  }

  .btn-remove:hover {
    color: var(--error);
    border-color: var(--error);
  }

  .btn-add {
    background: none;
    border: none;
    padding: 10px 12px;
    font-size: 12px;
    color: var(--accent);
    cursor: pointer;
    text-align: left;
    width: 100%;
    font-family: inherit;
  }

  .btn-add:hover {
    background: var(--accent-bg);
  }

  .activity-list {
    border: 0.5px solid var(--border);
    border-radius: 9px;
    overflow: hidden;
    max-height: 280px;
    overflow-y: auto;
  }

  .activity-row {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 8px 12px;
    border-bottom: 0.5px solid var(--border);
    font-size: 12px;
  }

  .activity-row:last-child {
    border-bottom: none;
  }

  .activity-filename {
    color: var(--text);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    max-width: 140px;
  }

  .activity-folder {
    color: var(--accent);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    flex: 1;
  }

  .activity-time {
    color: var(--text-secondary);
    flex-shrink: 0;
    font-size: 11px;
  }

  .empty {
    margin: 0;
    font-size: 12px;
    color: var(--text-secondary);
    padding: 4px 0;
  }
</style>
