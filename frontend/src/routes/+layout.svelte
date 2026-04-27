<script lang="ts">
  import '../app.css';
  import { onMount } from 'svelte';
  import { theme } from '$lib/themeStore';

  onMount(() => {
    theme.init();
  });
</script>

<slot />
