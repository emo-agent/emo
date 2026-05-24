<script lang="ts">
	import { page } from '$app/state';
	import ConfigPanel from '$lib/components/panels/ConfigPanel.svelte';
	import AgentsPanel from '$lib/components/panels/AgentsPanel.svelte';
	import SkillsPanel from '$lib/components/panels/SkillsPanel.svelte';
	import MCPsPanel from '$lib/components/panels/MCPsPanel.svelte';

	type Tab = 'config' | 'agents' | 'skills' | 'mcps';

	function validTab(t: string | null): t is Tab {
		return t === 'config' || t === 'agents' || t === 'skills' || t === 'mcps';
	}

	const currentTab = $derived(
		validTab(page.url.searchParams.get('tab'))
			? (page.url.searchParams.get('tab') as Tab)
			: ('config' as Tab)
	);
</script>

<div class="flex h-svh flex-col overflow-hidden">
	<main class="flex-1 overflow-y-auto">
		<div class="mx-auto max-w-2xl px-6 py-6">
			{#if currentTab === 'config'}
				<ConfigPanel />
			{:else if currentTab === 'agents'}
				<AgentsPanel />
			{:else if currentTab === 'skills'}
				<SkillsPanel />
			{:else if currentTab === 'mcps'}
				<MCPsPanel />
			{/if}
		</div>
	</main>
</div>
