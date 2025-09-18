import { writable } from 'svelte/store';
const browser = typeof window !== 'undefined';
export type Theme = 'light' | 'dark';

// Initialize theme from localStorage or default to light
function createThemeStore() {
  const defaultTheme: Theme = 'light';
  
  // Get initial theme from localStorage if available
  const initialTheme: Theme = browser 
    ? (localStorage.getItem('theme') as Theme) || defaultTheme
    : defaultTheme;

  const { subscribe, set, update } = writable<Theme>(initialTheme);

  return {
    subscribe,
    set: (theme: Theme) => {
      if (browser) {
        localStorage.setItem('theme', theme);
        // Update document class for CSS theme switching
        if (theme === 'dark') {
          document.documentElement.classList.add('dark');
        } else {
          document.documentElement.classList.remove('dark');
        }
      }
      set(theme);
    },
    toggle: () => update((theme: Theme) => {
      const newTheme = theme === 'light' ? 'dark' : 'light';
      if (browser) {
        localStorage.setItem('theme', newTheme);
        if (newTheme === 'dark') {
          document.documentElement.classList.add('dark');
        } else {
          document.documentElement.classList.remove('dark');
        }
      }
      return newTheme;
    }),
    init: () => {
      // Initialize document class on first load
      if (browser) {
        const currentTheme = localStorage.getItem('theme') as Theme || defaultTheme;
        if (currentTheme === 'dark') {
          document.documentElement.classList.add('dark');
        } else {
          document.documentElement.classList.remove('dark');
        }
        set(currentTheme);
      }
    }
  };
}

export const theme = createThemeStore();
