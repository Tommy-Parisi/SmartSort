<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { goto, beforeNavigate } from '$app/navigation';
  import SortFlowLayout from '$lib/components/SortFlowLayout.svelte';
  import MailroomCanvas from '$lib/components/MailroomCanvas.svelte';
  import { sortStore } from '$lib/stores/sort';
  import {
    onFileAssigned,
    onFolderDiscovered,
    onSortComplete,
    onSortError,
    tauriStartSort,
    tauriActivateLicense,
    type FileAssignedEvent,
    type FolderDiscoveredEvent,
    type SortCompleteEvent,
    type SortErrorEvent,
  } from '$lib/tauri';
  import type { UnlistenFn } from '@tauri-apps/api/event';

  let store = $sortStore;
  $: store = $sortStore;

  const STAGE_LABELS: Record<string, string> = {
    extracting: 'Extracting content…',
    embedding:  'Generating embeddings…',
    clustering: 'Organizing into folders…',
    naming:     'Naming folders…',
    placing:    'Placing files…',
  };

  let currentStage   = 'extracting';
  let foldersFound   = 0;
  let estETA         = '–';

  let sortRunning = false;
  let maxProgressPct = 0;

  let errorMessage   = '';
  let showTrialModal = false;
  let licenseKey     = '';
  let activateError  = '';
  let activating     = false;

  beforeNavigate(({ cancel }) => {
    if (sortRunning) {
      if (!confirm('Your sort is in progress. Going back will cancel it — files may be partially moved. Are you sure?')) {
        cancel();
      }
    }
  });

  let sortStartTs = 0;

  $: progressPct = store.filesTotal > 0
    ? Math.round((store.filesProcessed / store.filesTotal) * 100)
    : 0;

  $: if (progressPct > maxProgressPct) {
    maxProgressPct = progressPct;
  }

  $: foldersFound    = store.foldersDiscovered.length;
  $: displayTotal    = store.filesTotal > 0 ? Math.round(store.filesTotal / 100) : 0;
  $: displayProgress = displayTotal > 0 ? Math.min(Math.round(store.filesProcessed / 100), displayTotal) : 0;

  // Step 1 = Analyzing (extracting/embedding), Step 2 = Sorting (clustering/naming/placing)
  $: flowStep = (currentStage === 'extracting' || currentStage === 'embedding') ? 1 : 2;

  $: folderName = store.selectedFolder?.split('/').pop() ?? '';

  let unlisteners: UnlistenFn[] = [];

  onMount(async () => {
    if (!store.selectedFolder) {
      goto('/');
      return;
    }

    unlisteners.push(await onFolderDiscovered((e: FolderDiscoveredEvent) => {
      sortStore.update(s => ({
        ...s,
        foldersDiscovered: [...s.foldersDiscovered, {
          cluster_id:         e.cluster_id,
          folder_name:        e.folder_name,
          estimated_capacity: e.estimated_capacity,
        }],
      }));
    }));

    unlisteners.push(await onFileAssigned((e: FileAssignedEvent) => {
      currentStage = e.stage;
      sortStore.update(s => ({
        ...s,
        filesProcessed: Math.max(s.filesProcessed, e.files_processed),
        filesTotal:     Math.max(s.filesTotal, e.files_total),
      }));

      const now = Date.now();
      if (!sortStartTs) sortStartTs = now;
      if (e.stage === 'extracting' || e.stage === 'embedding') {
        const frac = e.files_processed / e.files_total;
        if (frac > 0.04) {
          const elapsedMs = now - sortStartTs;
          const remainingMs = (elapsedMs / frac) - elapsedMs;
          const secs = remainingMs / 1000;
          estETA = secs < 10  ? '<10s'
            : secs < 60       ? `~${Math.round(secs / 5) * 5}s`
            : `~${Math.ceil(secs / 60)}m`;
        }
      } else if (e.stage === 'placing') {
        estETA = 'finishing…';
      } else {
        estETA = '–';
      }
    }));

    unlisteners.push(await onSortComplete((e: SortCompleteEvent) => {
      sortRunning = false;
      maxProgressPct = 100;
      sortStore.update(s => ({
        ...s,
        folderTree:     e.folder_tree,
        filesSorted:    e.files_sorted,
        foldersCreated: e.folders_created,
        filesUnsorted:  e.files_unsorted,
        stage:          s.previewMode ? 'preview' : 'done',
      }));
    }));

    unlisteners.push(await onSortError((e: SortErrorEvent) => {
      sortRunning = false;
      if (e.code === 'trial_limit') {
        showTrialModal = true;
      } else {
        errorMessage = e.message || 'Something went wrong.';
      }
    }));

    sortRunning = true;
    tauriStartSort(store.selectedFolder, store.watchMode, store.previewMode)
      .catch(e => console.error('start_sort failed:', e));
  });

  onDestroy(() => {
    for (const fn of unlisteners) fn();
  });

  async function activateLicense() {
    if (!licenseKey.trim()) return;
    activating    = true;
    activateError = '';
    try {
      await tauriActivateLicense(licenseKey.trim());
      showTrialModal = false;
      licenseKey     = '';
      if (store.selectedFolder) {
        tauriStartSort(store.selectedFolder, store.watchMode, store.previewMode)
          .catch(e => console.error('restart start_sort failed:', e));
      }
    } catch {
      activateError = 'Invalid license key. Check your email from Gumroad.';
    } finally {
      activating = false;
    }
  }

  function cancel() {
    sortRunning = false;
    goto('/');
  }
</script>

<SortFlowLayout step={flowStep}>
  <div class="content-area">
    {#if errorMessage}
      <div class="error-state">
        <p class="error-text">{errorMessage}</p>
      </div>
    {:else}
      <p class="phase-label">
        {foldersFound > 0 ? 'Sorting your files' : 'Processing your files'}
      </p>

      <MailroomCanvas on:complete={() => goto(store.previewMode ? '/preview' : '/done')} />

      <div class="progress-track">
        <div class="progress-fill" style="width: {maxProgressPct}%"></div>
      </div>

      <p class="stage-label">{STAGE_LABELS[currentStage] ?? 'Processing…'}</p>

      <div class="counters">
        {#if foldersFound > 0}
          <span>{foldersFound} folders found</span>
          <span class="dot">·</span>
        {/if}
        {#if displayTotal > 0}
          <span>
            {displayProgress} of {displayTotal}
            {currentStage === 'placing' ? 'files placed' : 'files processed'}
          </span>
          <span class="dot">·</span>
        {/if}
        <span>{estETA}</span>
      </div>
    {/if}
  </div>

  <svelte:fragment slot="footer-left">
    {#if errorMessage}
      <button class="btn-ghost" on:click={() => goto('/')}>Go back</button>
    {:else}
      <button class="btn-ghost" on:click={cancel}>Cancel</button>
    {/if}
  </svelte:fragment>
</SortFlowLayout>

<!-- Trial limit modal -->
{#if showTrialModal}
  <div class="modal-backdrop">
    <div class="modal">
      <p class="modal-title">You've hit the trial limit</p>
      <p class="modal-sub">
        Smart Sort trial sorts up to 100 files. Your folder has more.
        Unlock unlimited sorting with a license key.
      </p>

      <div class="price-row">
        <span class="price">$49</span>
        <span class="price-label">one-time · unlimited files · all future updates</span>
      </div>

      <a
        href="https://smartsort.gumroad.com/l/license"
        class="btn-buy"
        target="_blank"
        rel="noopener noreferrer"
      >
        Get a license key →
      </a>

      <div class="activate-row">
        <input
          class="key-input"
          type="text"
          placeholder="Have a key? Paste it here"
          bind:value={licenseKey}
          on:keydown={e => e.key === 'Enter' && activateLicense()}
        />
        <button
          class="btn-activate"
          disabled={activating || !licenseKey.trim()}
          on:click={activateLicense}
        >
          {activating ? '…' : 'Activate'}
        </button>
      </div>

      {#if activateError}
        <p class="activate-error">{activateError}</p>
      {/if}

      <button class="btn-back" on:click={() => goto('/')}>Go back</button>
    </div>
  </div>
{/if}

<style>
  .content-area {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 24px;
    gap: 12px;
    overflow-y: auto;
  }

  .phase-label {
    margin: 0;
    font-size: 12px;
    font-weight: 500;
    color: var(--text-secondary);
    text-align: center;
  }

  .progress-track {
    width: 100%;
    max-width: 420px;
    height: 2px;
    background: var(--hover-bg);
    border-radius: 1px;
    overflow: hidden;
  }

  .progress-fill {
    height: 100%;
    background: var(--text);
    border-radius: 1px;
    transition: width 0.3s ease;
  }

  .stage-label {
    margin: 0;
    font-size: 12px;
    color: var(--text-secondary);
    text-align: center;
  }

  .counters {
    display: flex;
    justify-content: center;
    gap: 8px;
    font-size: 12px;
    color: var(--text-secondary);
  }

  .dot {
    opacity: 0.4;
  }

  .btn-ghost {
    background: none;
    border: 0.5px solid var(--border-strong);
    border-radius: 6px;
    padding: 8px 20px;
    font-size: 12px;
    cursor: pointer;
    color: var(--text);
  }

  .btn-ghost:hover {
    background: var(--bg-secondary);
  }

  .error-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 16px;
    padding: 32px 0;
  }

  .error-text {
    margin: 0;
    font-size: 12px;
    color: var(--error);
    text-align: center;
    line-height: 1.5;
  }

  /* Trial modal */
  .modal-backdrop {
    position: fixed;
    inset: 0;
    min-height: 100vh;
    background: rgba(0,0,0,0.4);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 200;
  }

  .modal {
    background: var(--bg);
    border: 0.5px solid var(--border-strong);
    border-radius: 12px;
    padding: 28px;
    max-width: 360px;
    width: 90%;
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .modal-title {
    margin: 0;
    font-size: 16px;
    font-weight: 500;
    color: var(--text);
  }

  .modal-sub {
    margin: 0;
    font-size: 12px;
    color: var(--text-secondary);
    line-height: 1.6;
  }

  .price-row {
    display: flex;
    align-items: baseline;
    gap: 10px;
  }

  .price {
    font-size: 28px;
    font-weight: 500;
    color: var(--text);
    line-height: 1;
  }

  .price-label {
    font-size: 11px;
    color: var(--text-secondary);
  }

  .btn-buy {
    display: block;
    width: 100%;
    padding: 11px;
    background: var(--text);
    color: var(--bg);
    border: none;
    border-radius: 6px;
    font-size: 13px;
    font-weight: 500;
    text-align: center;
    text-decoration: none;
    cursor: pointer;
    box-sizing: border-box;
  }

  .btn-buy:hover {
    opacity: 0.85;
  }

  .activate-row {
    display: flex;
    gap: 8px;
    width: 100%;
  }

  .key-input {
    flex: 1;
    border: 0.5px solid var(--border-strong);
    border-radius: 6px;
    padding: 8px 10px;
    font-size: 12px;
    font-family: monospace;
    background: var(--bg);
    color: var(--text);
    outline: none;
    min-width: 0;
  }

  .key-input:focus {
    border-color: var(--accent);
  }

  .btn-activate {
    background: none;
    border: 0.5px solid var(--border-strong);
    border-radius: 6px;
    padding: 8px 14px;
    font-size: 12px;
    cursor: pointer;
    color: var(--text);
    white-space: nowrap;
    flex-shrink: 0;
  }

  .btn-activate:disabled {
    opacity: 0.35;
    cursor: not-allowed;
  }

  .btn-activate:hover:not(:disabled) {
    background: var(--bg-secondary);
  }

  .activate-error {
    margin: 0;
    font-size: 11px;
    color: var(--error);
  }

  .btn-back {
    background: none;
    border: none;
    padding: 0;
    font-size: 12px;
    color: var(--text-secondary);
    cursor: pointer;
    text-align: center;
    align-self: center;
    font-family: inherit;
  }

  .btn-back:hover {
    color: var(--text);
  }
</style>
