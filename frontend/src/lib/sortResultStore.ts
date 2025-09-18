import { writable } from 'svelte/store';
export const sortResultStore = writable<{ folders: { name: string; files: string[] }[] } | null>(null);