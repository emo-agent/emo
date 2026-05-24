<script lang="ts">
	import './layout.css';
	import favicon from '$lib/assets/favicon.svg';
	import { SidebarProvider } from '$lib/components/ui/sidebar/index';
	import ChatSidebar from '$lib/components/ChatSidebar.svelte';

	let { children } = $props();
</script>

<svelte:head><link rel="icon" href={favicon} /></svelte:head>
<SidebarProvider>
	<ChatSidebar />
	<main class="flex min-h-svh flex-1 flex-col overflow-hidden">
		{@render children()}
	</main>
</SidebarProvider>
