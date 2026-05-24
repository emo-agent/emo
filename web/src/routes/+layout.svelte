<script lang="ts">
	import './layout.css';
	import favicon from '$lib/assets/favicon.svg';
	import AppSidebar from '$lib/components/AppSidebar.svelte';
	import PairingDialog from '$lib/components/PairingDialog.svelte';
	import { daemon } from '$lib/daemon/store.svelte';
	import { onMount } from 'svelte';

	let { children } = $props();

	onMount(() => {
		daemon.connect();
		return () => daemon.disconnect();
	});
</script>

<svelte:head><link rel="icon" href={favicon} /></svelte:head>
<PairingDialog />
<div class="flex h-svh overflow-hidden">
	<AppSidebar />
	<main class="flex min-h-svh flex-1 flex-col overflow-hidden">
		{@render children()}
	</main>
</div>
