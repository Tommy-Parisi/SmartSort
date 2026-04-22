<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import {
    onFileAssigned,
    onFolderDiscovered,
    onSortComplete,
    type FileAssignedEvent,
    type FolderDiscoveredEvent,
  } from '../tauri';
  import type { UnlistenFn } from '@tauri-apps/api/event';

  export let folderName: string = '';
  export let phase: 'processing' | 'sorting' = 'processing';

  // ── Interfaces ────────────────────────────────────────────────────────────

  interface VisualFolder {
    id: number;
    name: string;
    x: number;
    y: number;
    count: number;    // files actually placed (increments when a particle lands)
    capacity: number; // predicted cluster size — fill ratio denominator only, never displayed
    opacity: number;  // 0 → 1 fade-in
  }

  interface Particle {
    id: number;
    x: number; y: number;
    startX: number; startY: number;
    targetX: number; targetY: number;
    folderId: number;
    progress: number; // 0 → 1
    duration: number; // frames
    done: boolean;
    fill: string;
    border: string;
  }

  // ── Constants ─────────────────────────────────────────────────────────────

  const CANVAS_H = 220;
  const FOLDER_W = 32;
  const FOLDER_H = 28;
  const SOURCE_Y = 22;     // vertical center of source folder icon
  const DEST_Y = CANVAS_H - FOLDER_H - 16; // vertical center of destination folders
  const MAX_PARTICLES = 80;

  const EXT_COLORS: Record<string, [string, string]> = {
    pdf:  ['#FAECE7', '#993C1D'],
    docx: ['#E6F1FB', '#185FA5'],
    doc:  ['#E6F1FB', '#185FA5'],
    py:   ['#EAF3DE', '#3B6D11'],
    js:   ['#EAF3DE', '#3B6D11'],
    ts:   ['#EAF3DE', '#3B6D11'],
    jsx:  ['#EAF3DE', '#3B6D11'],
    tsx:  ['#EAF3DE', '#3B6D11'],
    csv:  ['#FAEEDA', '#854F0B'],
    xlsx: ['#FAEEDA', '#854F0B'],
    xls:  ['#FAEEDA', '#854F0B'],
    pptx: ['#FBEAF0', '#993556'],
    ppt:  ['#FBEAF0', '#993556'],
    jpg:  ['#EEEDFE', '#534AB7'],
    jpeg: ['#EEEDFE', '#534AB7'],
    png:  ['#EEEDFE', '#534AB7'],
    heic: ['#EEEDFE', '#534AB7'],
    webp: ['#EEEDFE', '#534AB7'],
    gif:  ['#EEEDFE', '#534AB7'],
    mp4:  ['#F5E8FE', '#6B3DA8'],
    mov:  ['#F5E8FE', '#6B3DA8'],
    mp3:  ['#FEF3E8', '#A05000'],
    wav:  ['#FEF3E8', '#A05000'],
  };
  const DEFAULT_EXT: [string, string] = ['rgba(0,0,0,0.08)', 'rgba(0,0,0,0.25)'];

  // ── State ─────────────────────────────────────────────────────────────────

  let canvas: HTMLCanvasElement;
  let raf: number;
  let nextId = 0;
  let tick = 0;
  let visualFolders: VisualFolder[] = [];
  let particles: Particle[] = [];
  let particleQueue: FileAssignedEvent[] = [];
  let draining = false;
  let hasRealFolders = false;
  let unlisteners: UnlistenFn[] = [];

  const PLACEHOLDER_COUNT = 3;

  // ── Color helpers ─────────────────────────────────────────────────────────

  function parseColor(c: string): [number, number, number, number] {
    if (c.startsWith('#')) {
      return [
        parseInt(c.slice(1, 3), 16),
        parseInt(c.slice(3, 5), 16),
        parseInt(c.slice(5, 7), 16),
        1,
      ];
    }
    const m = c.match(/rgba?\(([^)]+)\)/);
    if (m) {
      const p = m[1].split(',').map(s => parseFloat(s.trim()));
      return [p[0], p[1], p[2], p[3] ?? 1];
    }
    return [0, 0, 0, 1];
  }

  function lerpColor(a: string, b: string, t: number): string {
    const [ar, ag, ab, aa] = parseColor(a);
    const [br, bg, bb, ba] = parseColor(b);
    const r  = Math.round(ar + (br - ar) * t);
    const g  = Math.round(ag + (bg - ag) * t);
    const bl = Math.round(ab + (bb - ab) * t);
    const al = aa + (ba - aa) * t;
    return `rgba(${r},${g},${bl},${al})`;
  }

  function getExtColors(filename: string): [string, string] {
    const ext = filename.split('.').pop()?.toLowerCase() ?? '';
    return EXT_COLORS[ext] ?? DEFAULT_EXT;
  }

  // ── Layout ────────────────────────────────────────────────────────────────

  function canvasWidth(): number {
    return canvas?.parentElement?.clientWidth ?? 400;
  }

  function relayout() {
    const w = canvasWidth();
    const n = visualFolders.length;
    if (n === 0) return;
    const padding = 48;
    visualFolders = visualFolders.map((f, i) => ({
      ...f,
      x: padding + (n === 1 ? 0.5 : i / (n - 1)) * (w - padding * 2),
      y: DEST_Y,
    }));
  }

  // ── Drawing ───────────────────────────────────────────────────────────────

  function drawSourceFolder(ctx: CanvasRenderingContext2D, x: number, y: number) {
    const w = 44, h = 32;
    ctx.strokeStyle = 'rgba(0,0,0,0.5)';
    ctx.lineWidth = 1;
    ctx.fillStyle = 'rgba(0,0,0,0.06)';

    // body
    ctx.beginPath();
    ctx.roundRect(x - w / 2, y - h / 2 + 5, w, h, 3);
    ctx.fill();
    ctx.stroke();

    // tab
    ctx.beginPath();
    ctx.roundRect(x - w / 2, y - h / 2, w * 0.45, 7, [3, 3, 0, 0]);
    ctx.fill();
    ctx.stroke();

    // label below
    ctx.fillStyle = 'rgba(0,0,0,0.6)';
    ctx.font = '9px system-ui';
    ctx.textAlign = 'center';
    const label = folderName.length > 16 ? folderName.slice(0, 15) + '…' : folderName;
    ctx.fillText(label, x, y + h / 2 + 14);
  }

  function drawDestFolder(ctx: CanvasRenderingContext2D, f: VisualFolder) {
    ctx.globalAlpha = f.opacity;
    const fx = f.x - FOLDER_W / 2;
    const fy = f.y - FOLDER_H / 2;

    // green fill: height proportional to count / capacity (never uses capacity as label)
    const fillRatio = Math.min(f.count / Math.max(f.capacity, 1), 1);
    if (fillRatio > 0) {
      ctx.fillStyle = 'rgba(29,158,117,0.18)';
      const fh = fillRatio * (FOLDER_H - 4);
      ctx.fillRect(fx + 1, fy + FOLDER_H - fh - 2, FOLDER_W - 2, fh);
    }

    // folder outline
    ctx.strokeStyle = 'rgba(0,0,0,0.6)';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(fx + 2, fy + 6);
    ctx.lineTo(fx + FOLDER_W * 0.4, fy + 6);
    ctx.lineTo(fx + FOLDER_W * 0.4 + 4, fy + 2);
    ctx.lineTo(fx + FOLDER_W - 2, fy + 2);
    ctx.lineTo(fx + FOLDER_W - 2, fy + FOLDER_H - 2);
    ctx.lineTo(fx + 2, fy + FOLDER_H - 2);
    ctx.closePath();
    ctx.stroke();

    // placed file count — always f.count, never capacity
    ctx.fillStyle = 'rgba(0,0,0,0.7)';
    ctx.font = 'bold 9px system-ui';
    ctx.textAlign = 'center';
    ctx.fillText(String(f.count), f.x, f.y + 5);

    // folder name label
    ctx.fillStyle = 'rgba(0,0,0,0.55)';
    ctx.font = '10px system-ui';
    ctx.fillText(f.name, f.x, f.y + FOLDER_H / 2 + 14);

    ctx.globalAlpha = 1;
  }

  function drawParticleSq(ctx: CanvasRenderingContext2D, x: number, y: number, progress: number, fill: string, border: string, alpha = 1) {
    const size = 6;
    // lerp type color → green in the last 25% of travel
    const land = Math.max(0, (progress - 0.75) / 0.25);
    const cf = land > 0 ? lerpColor(fill,   '#1D9E75', land) : fill;
    const cb = land > 0 ? lerpColor(border, '#0F6E56', land) : border;
    ctx.globalAlpha = alpha;
    ctx.fillStyle = cf;
    ctx.strokeStyle = cb;
    ctx.lineWidth = 1;
    ctx.fillRect(x - size / 2, y - size / 2, size, size);
    ctx.strokeRect(x - size / 2, y - size / 2, size, size);
    ctx.globalAlpha = 1;
  }

  function drawPulse(ctx: CanvasRenderingContext2D, x: number, y: number, t: number) {
    const rings = 2;
    for (let i = 0; i < rings; i++) {
      const offset = (t * 0.02 + i * 0.5) % 1;
      const r = 24 + offset * 20;
      const alpha = (1 - offset) * 0.15;
      ctx.beginPath();
      ctx.arc(x, y, r, 0, Math.PI * 2);
      ctx.strokeStyle = `rgba(0,0,0,${alpha})`;
      ctx.lineWidth = 1.5;
      ctx.stroke();
    }
  }

  // ── Particle spawning ─────────────────────────────────────────────────────

  function addPlaceholders() {
    visualFolders = Array.from({ length: PLACEHOLDER_COUNT }, (_, i) => ({
      id: -(i + 1),
      name: '…',
      x: canvasWidth() / 2,
      y: DEST_Y,
      count: 0,
      capacity: 20,
      opacity: 0,
    }));
    relayout();
  }

  function spawnParticle(e: FileAssignedEvent) {
    const w = canvasWidth();
    const [fill, border] = getExtColors(e.filename ?? '');

    if (e.cluster_id === -1) {
      // Pre-clustering: fly toward a random placeholder folder then fade out
      const placeholders = visualFolders.filter(f => f.id < 0);
      const target = placeholders.length > 0
        ? placeholders[Math.floor(Math.random() * placeholders.length)]
        : { x: w * 0.15 + Math.random() * w * 0.7, y: DEST_Y };
      particles.push({
        id: nextId++,
        x: w / 2, y: SOURCE_Y,
        startX: w / 2, startY: SOURCE_Y,
        targetX: target.x, targetY: target.y,
        folderId: -1,
        progress: 0,
        duration: 50 + Math.random() * 20,
        done: false,
        fill,
        border,
      });
      return;
    }

    const folder = visualFolders.find(f => f.id === e.cluster_id);
    if (!folder) return; // folder-discovered hasn't fired yet — drop

    particles.push({
      id: nextId++,
      x: w / 2, y: SOURCE_Y,
      startX: w / 2, startY: SOURCE_Y,
      targetX: folder.x, targetY: folder.y,
      folderId: e.cluster_id,
      progress: 0,
      duration: draining ? 10 : 40 + Math.random() * 30,
      done: false,
      fill,
      border,
    });
  }

  function handleFileAssigned(e: FileAssignedEvent) {
    // Seed placeholder folders the moment the first file event arrives
    if (!hasRealFolders && visualFolders.length === 0) {
      addPlaceholders();
    }
    if (particles.length < MAX_PARTICLES) {
      spawnParticle(e);
    } else {
      particleQueue.push(e);
    }
  }

  // ── Animation loop ────────────────────────────────────────────────────────

  function frame() {
    if (!canvas) return;
    tick++;
    const dpr = window.devicePixelRatio || 1;
    const ctx = canvas.getContext('2d')!;
    const W = canvas.width / dpr;

    ctx.save();
    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, W, CANVAS_H);

    // pulsing ring around source folder during extraction phase
    if (phase === 'processing') {
      drawPulse(ctx, W / 2, SOURCE_Y, tick);
    }

    // source folder icon
    drawSourceFolder(ctx, W / 2, SOURCE_Y);

    // destination folders (fade in as they're discovered)
    for (const f of visualFolders) {
      if (f.opacity < 1) f.opacity = Math.min(1, f.opacity + 0.05);
      drawDestFolder(ctx, f);
    }

    // advance particles
    const alive: Particle[] = [];
    for (const p of particles) {
      if (p.done) continue;
      p.progress += 1 / p.duration;
      if (p.progress >= 1) {
        p.progress = 1;
        p.done = true;
        // increment the destination folder's placed count (not for drifting pre-cluster particles)
        if (p.folderId !== -1) {
          const dest = visualFolders.find(f => f.id === p.folderId);
          if (dest) dest.count++;
        }
      }
      const t = p.progress;
      const cx = p.startX + (p.targetX - p.startX) * t;
      const cy = p.startY + (p.targetY - p.startY) * t + Math.sin(t * Math.PI) * -30;
      p.x = cx;
      p.y = cy;
      // processing-phase particles dissolve at 60% of arc; sorting particles are opaque
      const alpha = p.folderId === -1 ? Math.max(0, 1 - t / 0.6) : 1;
      drawParticleSq(ctx, cx, cy, t, p.fill, p.border, alpha);
      if (!p.done) alive.push(p);
    }
    particles = alive;

    // drain queue into free particle slots
    while (particles.length < MAX_PARTICLES && particleQueue.length > 0) {
      spawnParticle(particleQueue.shift()!);
    }

    ctx.restore();
  }

  function loop() {
    frame();
    raf = requestAnimationFrame(loop);
  }

  // ── Resize ────────────────────────────────────────────────────────────────

  function resize() {
    if (!canvas) return;
    const dpr = window.devicePixelRatio || 1;
    const w = canvasWidth();
    canvas.width = w * dpr;
    canvas.height = CANVAS_H * dpr;
    canvas.style.width = `${w}px`;
    canvas.style.height = `${CANVAS_H}px`;
    relayout();
  }

  // ── Lifecycle ─────────────────────────────────────────────────────────────

  onMount(async () => {
    resize();
    window.addEventListener('resize', resize);
    loop();

    unlisteners.push(await onFolderDiscovered((e: FolderDiscoveredEvent) => {
      if (!hasRealFolders) {
        hasRealFolders = true;
        visualFolders = []; // clear placeholders
      }
      visualFolders = [
        ...visualFolders,
        {
          id: e.cluster_id,
          name: e.folder_name.slice(0, 14),
          x: canvasWidth() / 2,
          y: DEST_Y,
          count: 0,
          capacity: e.estimated_capacity || 20,
          opacity: 0,
        },
      ];
      relayout();
    }));

    unlisteners.push(await onFileAssigned((e: FileAssignedEvent) => {
      handleFileAssigned(e);
    }));

    unlisteners.push(await onSortComplete(() => {
      draining = true;
      // Fast-forward all in-flight particles
      for (const p of particles) p.duration = 10;
      // Spawn remaining queued particles immediately (they get duration=10)
      while (particleQueue.length > 0 && particles.length < MAX_PARTICLES) {
        spawnParticle(particleQueue.shift()!);
      }
      particleQueue = [];
    }));
  });

  onDestroy(() => {
    cancelAnimationFrame(raf);
    window.removeEventListener('resize', resize);
    for (const fn of unlisteners) fn();
  });
</script>

<div class="canvas-wrap">
  <canvas bind:this={canvas}></canvas>
</div>

<style>
  .canvas-wrap {
    width: 100%;
    height: 220px;
    overflow: hidden;
  }

  canvas {
    display: block;
  }
</style>
