<script lang="ts">
  import { onMount } from 'svelte';
  import ShellLayout from '$lib/components/ShellLayout.svelte';
  import { tauriGetHistory, tauriUndoSort, type SortSession } from '$lib/tauri';

  let sessions: SortSession[] = [];
  let loading = true;
  let undoingId: string | null = null;
  let error = '';

  const SEVEN_DAYS_MS = 7 * 24 * 60 * 60 * 1000;

  onMount(async () => {
    try {
      sessions = await tauriGetHistory();
    } catch {
      // dev
    } finally {
      loading = false;
    }
  });

  async function undoSession(session: SortSession) {
    undoingId = session.session_id;
    error = '';
    try {
      await tauriUndoSort();
    } catch (e: any) {
      error = typeof e === 'string' ? e : 'Undo failed.';
    } finally {
      undoingId = null;
    }
  }

  function isOld(session: SortSession): boolean {
    // We don't have a full timestamp, so check if "days ago" > 7
    // For now, sessions without enough info default to enabled
    return false;
  }
</script>

<ShellLayout>
  <div class="content">
    <p class="section-label">Sort history</p>

    {#if loading}
      <p class="hint">Loading…</p>
    {:else if sessions.length === 0}
      <p class="hint">No sort history yet.</p>
    {:else}
      <div class="history-list">
        {#each sessions as session, i}
          <div class="history-row" class:old={isOld(session)}>
            <div class="row-main">
              <svg class="row-icon" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7">
                <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
              </svg>
              <div class="row-info">
                <span class="row-path">{session.folder}</span>
                <span class="row-meta">
                  {session.date} · {session.files_sorted} files sorted into {session.folders_created} folders
                </span>
              </div>
            </div>
            <button
              class="btn-undo"
              disabled={isOld(session) || undoingId === session.session_id}
              on:click={() => undoSession(session)}
              title={isOld(session) ? 'Undo only available for 7 days' : 'Undo this sort'}
            >
              {undoingId === session.session_id ? 'Undoing…' : 'Undo'}
            </button>
          </div>
        {/each}
      </div>
    {/if}

    {#if error}
      <p class="error-text">{error}</p>
    {/if}

    <p class="footer-note">Undo is available for 7 days after each sort.</p>
  </div>
</ShellLayout>

<style>
  .content {
    padding: 24px;
    width: 100%;
    max-width: 620px;
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .section-label {
    margin: 0;
    font-size: 10px;
    font-weight: 600;
    color: var(--text-secondary);
    letter-spacing: 0.06em;
  }

  .hint {
    margin: 0;
    font-size: 12px;
    color: var(--text-secondary);
    padding: 4px 0;
  }

  .history-list {
    border: 0.5px solid var(--border);
    border-radius: 9px;
    overflow: hidden;
  }

  .history-row {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 10px 14px;
    border-bottom: 0.5px solid var(--border);
    transition: background 100ms;
  }

  .history-row:last-child {
    border-bottom: none;
  }

  .history-row:hover {
    background: var(--bg-secondary);
  }

  .history-row.old {
    opacity: 0.5;
  }

  .row-main {
    display: flex;
    align-items: flex-start;
    gap: 9px;
    flex: 1;
    min-width: 0;
  }

  .row-icon {
    color: var(--text-secondary);
    flex-shrink: 0;
    margin-top: 2px;
    opacity: 0.5;
  }

  .row-info {
    display: flex;
    flex-direction: column;
    gap: 2px;
    min-width: 0;
  }

  .row-path {
    font-size: 12px;
    font-weight: 500;
    color: var(--text);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .row-meta {
    font-size: 11px;
    color: var(--text-secondary);
  }

  .btn-undo {
    flex-shrink: 0;
    background: none;
    border: 0.5px solid var(--border-strong);
    border-radius: 5px;
    padding: 4px 12px;
    font-size: 11px;
    color: var(--text);
    cursor: pointer;
    transition: background 100ms;
  }

  .btn-undo:hover:not(:disabled) {
    background: var(--bg-secondary);
  }

  .btn-undo:disabled {
    opacity: 0.35;
    cursor: not-allowed;
  }

  .footer-note {
    margin: 4px 0 0;
    font-size: 11px;
    color: var(--text-secondary);
  }

  .error-text {
    margin: 0;
    font-size: 11px;
    color: var(--error);
  }
</style>
