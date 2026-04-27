<script lang="ts">
  import { onMount, onDestroy, createEventDispatcher } from 'svelte';
  import {
    onFileAssigned,
    onFolderDiscovered,
    onSortComplete,
    type FileAssignedEvent,
    type FolderDiscoveredEvent,
  } from '../tauri';
  import type { UnlistenFn } from '@tauri-apps/api/event';


  const dispatch = createEventDispatcher();

  // ── Coordinate space ───────────────────────────────────────────────────────
  const W = 480, H = 220;
  const stackX = 50,       stackY = 36;
  const inspectX = W/2,    inspectY = 36;
  const trayX = W - 50,    trayY = 36;
  const ACT2_INSPECT_Y = 70; // lower inspect position for phase 2

  // Pigeonhole grid
  const SCOLS = 5, MAX_SLOTS = 10;
  const slotW = 86, slotH = 30, slotGapX = 4, slotGapY = 4;

  function slotPos(idx: number, count: number = MAX_SLOTS) {
    const cols = Math.min(count, SCOLS);
    const rows = Math.ceil(count / cols);
    const gw   = cols * slotW + (cols - 1) * slotGapX;
    const x0   = (W - gw) / 2;
    const y0   = H - (rows * slotH + (rows - 1) * slotGapY) - 8;
    return {
      x: x0 + (idx % cols) * (slotW + slotGapX),
      y: y0 + Math.floor(idx / cols) * (slotH + slotGapY),
    };
  }

  // ── Palette ────────────────────────────────────────────────────────────────
  const SLOT_HUES = [20, 145, 220, 280, 40, 330, 162, 270, 45, 180];

  function typeHue(ext: string): number {
    const m: Record<string, number> = {
      pdf: 20,
      doc: 220, docx: 220, txt: 220, md: 220,
      py: 145, js: 145, ts: 145, jsx: 145, tsx: 145, css: 145, html: 145, sh: 145,
      csv: 40, xls: 40, xlsx: 40,
      ppt: 330, pptx: 330,
      jpg: 280, jpeg: 280, png: 280, gif: 280, webp: 280, heic: 280,
      mp4: 270, mov: 270,
      mp3: 45, wav: 45,
      json: 180, yaml: 180, toml: 180,
    };
    return m[ext?.toLowerCase()] ?? 200;
  }

  function srand(seed: number) {
    let s = seed;
    return () => { s = (s * 1664525 + 1013904223) & 0xffffffff; return (s >>> 0) / 0xffffffff; };
  }

  // ── Types ──────────────────────────────────────────────────────────────────
  interface StreamCard { id: number; name: string; ext: string; hue: number; born: number; }
  interface PoolCard   { i: number; ext: string; hue: number; slot: number; tilt: number; offX: number; offY: number; flyDelay: number; }
  interface Slot       { name: string; hue: number; capacity: number; named: boolean; }

  // ── Constants ──────────────────────────────────────────────────────────────
  const CARD_LIFETIME = 1100;
  const THINKING_MS   = 2500; // Minimum thinking time
  const POOL_N        = 22;
  const LINE_WIDTHS   = [18, 14, 12];

  const THOUGHTS = [
    "Analyzing semantic patterns…",
    "Comparing document vectors…",
    "Grouping similar concepts…",
    "Optimizing folder hierarchy…",
    "Cross-referencing embeddings…",
    "Refining category boundaries…",
    "Finalizing folder names…"
  ];

  // ── Reactive state ─────────────────────────────────────────────────────────
  let act: 1 | 2 | 3 = 1;
  let act2StartedTs = 0;
  let act3Progress = 0;
  let act3StartTs  = 0;
  let now = 0;

  let eventQueue: FileAssignedEvent[] = [];
  let nextDrainTs  = 0;
  let lastEventTs  = 0;
  let filesTotal = 0;
  let sortDone      = false;
  let completeFired = false;

  let streamCards: StreamCard[] = [];
  let nextCardId    = 0;
  let filesSeenCount = 0;
  let lastStage = '';
  let backendStage = ''; // updated immediately on receive, not drain-throttled
  let pool: PoolCard[] = [];

  let displaySlots: Slot[] = Array.from({ length: MAX_SLOTS }, (_, i) => ({
    name: '· · ·', hue: SLOT_HUES[i], capacity: 5, named: false,
  }));
  let namedSlotCount = 0;

  let fills: number[]    = Array(MAX_SLOTS).fill(0);
  let inspectName = '';
  let inspectExt  = '';

  // ── Pool ───────────────────────────────────────────────────────────────────
  function initPool() {
    const r   = srand(83);
    const exts = ['pdf','docx','py','jpg','csv','ts','pptx','heic','txt','xlsx','mp3','png'];
    pool = Array.from({ length: POOL_N }, (_, i) => {
      const ext = exts[i % exts.length];
      return { i, ext, hue: typeHue(ext), slot: i % MAX_SLOTS,
        tilt: (r() - 0.5) * 14, offX: (r() - 0.5) * 6, offY: (r() - 0.5) * 4,
        flyDelay: i / POOL_N };
    });
  }

  function assignPoolToSlots() {
    const named = displaySlots.map((s, i) => s.named ? i : -1).filter(i => i >= 0);
    if (!named.length) return;
    const totalCap = named.reduce((s, i) => s + displaySlots[i].capacity, 0);
    let pi = 0;
    named.forEach((si, ii) => {
      const share = ii < named.length - 1
        ? Math.round((displaySlots[si].capacity / totalCap) * POOL_N)
        : POOL_N - pi;
      for (let j = 0; j < share && pi < POOL_N; j++, pi++) {
        pool[pi].slot     = si;
        pool[pi].flyDelay = pi / POOL_N;
      }
    });
    pool = [...pool];
  }

  // ── Position helpers ───────────────────────────────────────────────────────
  function act2FlipPos(ts: number): { x: number; y: number; tilt: number; p: number; idx: number } {
    const elapsed = ts - act2StartedTs;
    const FLIP_MS = 1400;
    const idx  = Math.floor(elapsed / FLIP_MS) % POOL_N;
    const p    = (elapsed % FLIP_MS) / FLIP_MS;
    const card = pool[idx];
    const ss   = (t: number) => t * t * (3 - 2 * t);
    let x: number, y: number, tilt: number;
    if (p < 0.3) {
      const e = ss(p / 0.3);
      x = trayX + (inspectX - trayX) * e;
      y = trayY + (ACT2_INSPECT_Y - trayY) * e - Math.sin(e * Math.PI) * 8;
      tilt = (card?.tilt ?? 0) * (1 - e);
    } else if (p < 0.7) {
      x = inspectX; y = ACT2_INSPECT_Y; tilt = 0;
    } else {
      const e = ss((p - 0.7) / 0.3);
      x = inspectX + (trayX - inspectX) * e;
      y = ACT2_INSPECT_Y + (trayY - ACT2_INSPECT_Y) * e - Math.sin(e * Math.PI) * 6;
      tilt = -(card?.tilt ?? 0) * e * 0.3;
    }
    return { x, y, tilt, p, idx };
  }

  function act1Pos(progress: number) {
    if (progress < 0.45) {
      const t = progress / 0.45, e = 1 - Math.pow(1 - t, 2);
      return { x: stackX + (inspectX - stackX) * e, y: stackY + (inspectY - stackY) * e - Math.sin(t * Math.PI) * 6, tilt: (1-e)*8 };
    }
    if (progress < 0.65) return { x: inspectX, y: inspectY, tilt: 0 };
    const t = (progress - 0.65) / 0.35, e = t * t;
    return { x: inspectX + (trayX - inspectX) * e, y: inspectY + (trayY - inspectY) * e - Math.sin(t * Math.PI) * 6, tilt: e * -6 };
  }

  function act3Fly(card: PoolCard): { x: number; y: number; tilt: number; opacity: number } | null | 'done' {
    const local = Math.max(0, (act3Progress - card.flyDelay * 0.7) / 0.3);
    if (local <= 0) return null;
    if (local >= 1) return 'done';
    const e  = local * local * (3 - 2 * local);
    const sp = slotPos(card.slot, namedSlotCount);
    return {
      x:       (trayX + card.offX) + (sp.x + slotW/2 - trayX - card.offX) * e,
      y:       (trayY + card.offY) + (sp.y + slotH/2 - trayY - card.offY) * e - Math.sin(local * Math.PI) * 14,
      tilt:    card.tilt * (1 - e),
      opacity: 1 - Math.max(0, (local - 0.85) / 0.15),
    };
  }

  // ── Event processing ───────────────────────────────────────────────────────
  function processEvent(e: FileAssignedEvent, ts: number) {
    lastEventTs = ts;
    filesTotal  = e.files_total;
    lastStage      = e.stage;

    if (filesSeenCount < POOL_N) {
      const ext = e.filename?.split('.').pop()?.toLowerCase() ?? 'txt';
      pool[filesSeenCount].ext = ext;
      pool[filesSeenCount].hue = typeHue(ext);
    }
    filesSeenCount++;

    const ext  = e.filename?.split('.').pop()?.toLowerCase() ?? 'txt';
    const name = e.filename?.replace(/\.[^.]+$/, '') ?? '';

    if (e.stage === 'extracting' || e.stage === 'embedding') {
      streamCards = [...streamCards, { id: nextCardId++, name, ext, hue: typeHue(ext), born: ts }];
    }
  }

  // ── RAF loop ───────────────────────────────────────────────────────────────
  let raf: number;

  function frame(ts: number) {
    now = ts;

    if (eventQueue.length > 0 && ts >= nextDrainTs) {
      processEvent(eventQueue.shift()!, ts);
      
      // Dynamic drain rate based on backlog
      let baseDelay = 450;
      if (eventQueue.length > 15) baseDelay = 150;
      else if (eventQueue.length > 5) baseDelay = 250;
      else if (eventQueue.length <= 2) baseDelay = 800;

      const jitter = (Math.random() - 0.5) * baseDelay * 0.5;
      nextDrainTs = ts + baseDelay + jitter;
    }

    streamCards = streamCards.filter(c => ts - c.born < CARD_LIFETIME);

    // Act 1 -> 2 transition logic: use backendStage (not drain-throttled lastStage)
    const explicitThinkingTrigger = backendStage === 'clustering' || backendStage === 'naming' || backendStage === 'placing';
    const silenceFallbackTrigger = lastEventTs > 0 && ts - lastEventTs > 15000;
    
    if (act === 1 && streamCards.length === 0) {
      if (explicitThinkingTrigger || silenceFallbackTrigger || sortDone) {
        if (!act2StartedTs) {
          act2StartedTs = ts; 
        } else if (ts - act2StartedTs > 400) {
          act = 2;
          act2StartedTs = ts; 
        }
      }
    }

    // Act 2 -> 3 transition logic: Thinking duration elapsed and Placing stage reached
    if (act === 2 && ts - act2StartedTs >= THINKING_MS && (backendStage === 'placing' || sortDone)) {
      act = 3;
      act3StartTs = ts;
      assignPoolToSlots();
    }

    if (act === 3) {
      // Pure time-based: events are often fully drained before act 3 fires,
      // so event-based progress would jump immediately to 1 and skip the animation.
      act3Progress = Math.min(1, (ts - act3StartTs) / 3500);
    }

    const ic = streamCards.find(c => { const p = (ts - c.born) / CARD_LIFETIME; return p > 0.45 && p < 0.65; })
            ?? streamCards[streamCards.length - 1];
    inspectName = ic?.name ?? '';
    inspectExt  = ic?.ext  ?? '';

    fills = displaySlots.map((_, si) => {
      if (act < 3) return 0;
      return pool.filter(c => c.slot === si && (act3Progress - c.flyDelay * 0.7) / 0.3 >= 1).length;
    });

    if (sortDone && !completeFired) {
      if (filesTotal === 0 || (act === 3 && act3Progress >= 1)) {
        completeFired = true;
        dispatch('complete');
      }
    }

    raf = requestAnimationFrame(frame);
  }

  // ── Lifecycle ──────────────────────────────────────────────────────────────
  let unlisteners: UnlistenFn[] = [];

  onMount(async () => {
    initPool();
    raf = requestAnimationFrame(frame);

    unlisteners.push(await onFileAssigned(e => {
      // Capture filesTotal immediately (not via drain)
      if (!filesTotal && e.files_total) filesTotal = e.files_total;

      // On stage advance, flush stale events so animation isn't stuck replaying a backlog
      if (e.stage !== backendStage) {
        if (e.stage === 'clustering' || e.stage === 'naming') {
          // extracting/embedding events are no longer relevant — drop them
          eventQueue = eventQueue.filter(ev => ev.stage !== 'extracting' && ev.stage !== 'embedding');
        } else if (e.stage === 'placing') {
          // backend is already placing — skip all remaining queued events
          eventQueue = [];
        }
        backendStage = e.stage;
      }

      // Only queue visual events (stream cards are only spawned for these)
      if (e.stage === 'extracting' || e.stage === 'embedding') {
        eventQueue.push(e);
      }
    }));

    unlisteners.push(await onFolderDiscovered((e: FolderDiscoveredEvent) => {
      const si = namedSlotCount;
      if (si >= displaySlots.length) {
        displaySlots = [...displaySlots, { name: '· · ·', hue: SLOT_HUES[si % SLOT_HUES.length], capacity: 5, named: false }];
      }
      displaySlots[si] = {
        name:     e.folder_name.length > 14 ? e.folder_name.slice(0, 13) + '…' : e.folder_name,
        hue:      SLOT_HUES[si % SLOT_HUES.length],
        capacity: e.estimated_capacity || 5,
        named:    true,
      };
      namedSlotCount++;
      displaySlots = [...displaySlots];
    }));

    unlisteners.push(await onSortComplete(() => {
      eventQueue = [];   // drop any remaining backlog — sort is done
      sortDone = true;
      setTimeout(() => { if (!completeFired) { completeFired = true; dispatch('complete'); } }, 12000);
    }));
  });

  onDestroy(() => { cancelAnimationFrame(raf); for (const fn of unlisteners) fn(); });
</script>

<div class="wrap" style="height: {act === 3 ? '320px' : '240px'}">
  <svg viewBox="0 0 {W} {H}" width="100%" height="100%">

    <!-- Phase label -->
    <text x="20" y="14" font-size="7" font-family="ui-monospace, Menlo, monospace"
      fill="var(--text-secondary)" letter-spacing="0.1em">
      {act === 1 ? 'INSPECTING' : act === 2 ? 'CONSIDERING' : 'FILING'}
    </text>

    <!-- Inbox folder icon -->
    <g transform="translate({stackX} {stackY})" opacity={act === 1 ? 1 : 0.3}>
      <path d="M -22 -14 L -8 -14 L -4 -18 L 10 -18 L 10 -14 L 22 -14 L 22 14 L -22 14 Z"
        fill="var(--bg)" stroke="var(--text-faint)" stroke-width="0.6" />
      <line x1="-22" y1="-8" x2="22" y2="-8" stroke="var(--border)" stroke-width="0.6" />
    </g>

    <!-- Read tray -->
    <g transform="translate({trayX} {trayY})">
      <rect x="-26" y="-16" width="52" height="32" rx="2"
        fill="var(--hover-bg)" stroke="var(--border)" stroke-width="0.6" />
      <text x="0" y="-22" text-anchor="middle" font-size="7"
        font-family="ui-monospace, Menlo, monospace"
        fill="var(--text-secondary)" letter-spacing="0.06em">READ</text>
    </g>

    <!-- ── ACT 1 ─────────────────────────────────────────────────────────── -->
    {#if act === 1}
      {#each streamCards as card (card.id)}
        {@const progress = Math.min(1, (now - card.born) / CARD_LIFETIME)}
        {@const pos      = act1Pos(progress)}
        {@const stamped  = progress > 0.55}
        <g transform="translate({pos.x} {pos.y}) rotate({pos.tilt})">
          <rect x="-15" y="-11" width="30" height="22" rx="2"
            fill={stamped ? `oklch(0.97 0.03 ${card.hue})` : 'var(--bg)'}
            stroke={stamped ? `oklch(0.55 0.16 ${card.hue})` : 'var(--border-strong)'}
            stroke-width="0.7" />
          {#each [-6, -3, 0] as ly, li}
            <line x1="-11" y1={ly} x2={-11 + LINE_WIDTHS[li]} y2={ly}
              stroke="var(--text-secondary)" stroke-opacity="0.3" stroke-width="0.4" />
          {/each}
          <text x="12" y="8" text-anchor="end" font-size="5.5"
            font-family="ui-monospace, Menlo, monospace"
            fill="oklch(0.4 0.20 {card.hue})">.{card.ext}</text>
        </g>
      {/each}

      {#if inspectName}
        <text x={W/2} y="80" text-anchor="middle" font-size="9"
          font-family="ui-monospace, Menlo, monospace" fill="var(--text-secondary)">
          <tspan fill="var(--text-faint)">inspecting · </tspan
          ><tspan fill="var(--text)">{inspectName}.{inspectExt}</tspan>
        </text>
      {/if}
    {/if}

    <!-- ── ACT 2 ─────────────────────────────────────────────────────────── -->
    {#if act === 2}
      {@const thoughtIdx = Math.floor(now / 3000) % THOUGHTS.length}
      {@const fp       = act2FlipPos(now)}
      {@const flipCard = pool[fp.idx]}
      {@const atCenter = fp.p >= 0.3 && fp.p < 0.7}

      <!-- Decorative card stack sitting in tray -->
      {#each [3, 2, 1] as d}
        <rect x={trayX - 14 + d * 0.5} y={trayY - 11 - d * 0.8}
          width="29" height="21" rx="2"
          fill="var(--bg)" stroke="var(--border)" stroke-width="0.5" />
      {/each}

      <!-- Flipping card — travels tray → inspect → tray -->
      {#if flipCard}
        <g transform="translate({fp.x} {fp.y}) rotate({fp.tilt})">
          <rect x="-15" y="-11" width="30" height="22" rx="2"
            fill={atCenter ? `oklch(0.97 0.03 ${flipCard.hue})` : 'var(--bg)'}
            stroke={atCenter ? `oklch(0.55 0.16 ${flipCard.hue})` : 'var(--border-strong)'}
            stroke-width="0.7" />
          {#each [-6, -3, 0] as ly, li}
            <line x1="-11" y1={ly} x2={-11 + LINE_WIDTHS[li]} y2={ly}
              stroke="var(--text-secondary)" stroke-opacity="0.3" stroke-width="0.4" />
          {/each}
          {#if atCenter}
            <text x="12" y="8" text-anchor="end" font-size="5.5"
              font-family="ui-monospace, Menlo, monospace"
              fill="oklch(0.4 0.20 {flipCard.hue})">.{flipCard.ext}</text>
          {/if}
        </g>
      {/if}

      <!-- Magnifying glass — scans the card while at inspect position -->
      {#if atCenter}
        {@const osc = Math.sin(now / 480) * 5}
        <g transform="translate({inspectX + 20 + osc * 0.4} {ACT2_INSPECT_Y - 16 + osc})" opacity="0.7">
          <circle r="10" fill="none" stroke="var(--text-secondary)" stroke-width="1.5" />
          <line x1="7" y1="7" x2="15" y2="15" stroke="var(--text-secondary)" stroke-width="2" stroke-linecap="round" />
        </g>
      {/if}

      <text x={W / 2} y="118" text-anchor="middle" font-size="11"
        font-family='"Jacquard 24", serif' fill="var(--text)">
        {THOUGHTS[thoughtIdx]}
      </text>
      {#if namedSlotCount > 0}
        <text x={W / 2} y="135" text-anchor="middle" font-size="8.5"
          font-family="ui-monospace, Menlo, monospace" fill="var(--text-secondary)">
          {namedSlotCount} folder{namedSlotCount !== 1 ? 's' : ''} identified
        </text>
      {:else}
        {#each [0, 1, 2] as i}
          {@const ph = ((now / 800) + i * 0.33) % 1}
          {@const op = 0.25 + (1 - Math.abs(ph - 0.5) * 2) * 0.6}
          <circle cx={W / 2 - 8 + i * 8} cy="132" r="1.6" fill="var(--text)" opacity={op} />
        {/each}
      {/if}
    {/if}

    <!-- ── ACT 3 ─────────────────────────────────────────────────────────── -->
    {#if act === 3}
      {#each pool as card}
        {@const fly = act3Fly(card)}
        {#if fly === null}
          <g transform="translate({trayX + card.offX} {trayY + card.offY}) rotate({card.tilt})">
            <rect x="-15" y="-11" width="30" height="22" rx="2"
              fill="oklch(0.97 0.03 {card.hue})"
              stroke="oklch(0.55 0.16 {card.hue})" stroke-width="0.7" />
            {#each [-6, -3, 0] as ly, li}
              <line x1="-11" y1={ly} x2={-11 + LINE_WIDTHS[li]} y2={ly}
                stroke="var(--text-secondary)" stroke-opacity="0.3" stroke-width="0.4" />
            {/each}
            <text x="12" y="8" text-anchor="end" font-size="5.5"
              font-family="ui-monospace, Menlo, monospace"
              fill="oklch(0.4 0.20 {card.hue})">.{card.ext}</text>
          </g>
        {:else if fly !== 'done'}
          <g transform="translate({fly.x} {fly.y}) rotate({fly.tilt})" opacity={fly.opacity}>
            <rect x="-15" y="-11" width="30" height="22" rx="2"
              fill="oklch(0.97 0.03 {card.hue})"
              stroke="oklch(0.55 0.16 {card.hue})" stroke-width="0.7" />
            {#each [-6, -3, 0] as ly, li}
              <line x1="-11" y1={ly} x2={-11 + LINE_WIDTHS[li]} y2={ly}
                stroke="var(--text-secondary)" stroke-opacity="0.3" stroke-width="0.4" />
            {/each}
            <text x="12" y="8" text-anchor="end" font-size="5.5"
              font-family="ui-monospace, Menlo, monospace"
              fill="oklch(0.4 0.20 {card.hue})">.{card.ext}</text>
          </g>
        {/if}
      {/each}
    {/if}

    <!-- ── Pigeonholes (act 3 only, sized to actual cluster count) ─────── -->
    {#if act === 3}
      {#each displaySlots.slice(0, namedSlotCount) as slot, si}
        {@const sp = slotPos(si, namedSlotCount)}
        <rect x={sp.x} y={sp.y} width={slotW} height={slotH}
          fill="oklch(0.97 0.04 {slot.hue})"
          stroke="oklch(0.6 0.13 {slot.hue})"
          stroke-width="0.6" />
        <rect x={sp.x + 1} y={sp.y + 1} width={slotW - 2} height="2.5" fill="var(--text)" fill-opacity="0.08" />
        {#each Array.from({ length: Math.min(4, Math.ceil(fills[si] / 2)) }) as _, fi}
          <rect x={sp.x + 4} y={sp.y + slotH - 4 - fi * 1.6} width={slotW - 8} height="2.5"
            fill="var(--bg)" stroke="oklch(0.55 0.18 {slot.hue})" stroke-width="0.4" />
        {/each}
        <text x={sp.x + 5} y={sp.y + 11} font-size="7.5"
          font-family='"Jacquard 24", serif' font-weight="600"
          fill="oklch(0.32 0.18 {slot.hue})">
          {slot.name}
        </text>
        {#if fills[si] > 0}
          <text x={sp.x + slotW - 5} y={sp.y + slotH - 4} text-anchor="end"
            font-size="9" font-family='"Jacquard 24", serif' font-weight="600"
            fill="oklch(0.4 0.18 {slot.hue})">{fills[si]}</text>
        {/if}
      {/each}
    {/if}

  </svg>
</div>

<style>
  .wrap { width: 100%; overflow: hidden; transition: height 0.4s ease; }
  svg { display: block; }
</style>
