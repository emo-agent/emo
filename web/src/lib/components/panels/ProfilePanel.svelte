<script lang="ts">
	import { daemon } from '$lib/daemon/store.svelte';

	const stateColors: Record<string, string> = {
		connected: 'bg-green-500/20 text-green-600',
		connecting: 'bg-yellow-500/20 text-yellow-600',
		disconnected: 'bg-muted text-muted-foreground',
		error: 'bg-destructive/20 text-destructive'
	};
</script>

<div class="flex flex-col gap-4 p-4">
	<div>
		<p class="mb-1 text-xs font-medium text-muted-foreground">Connection</p>
		<span class="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium {stateColors[daemon.connectionState] ?? ''}">
			{daemon.connectionState}
		</span>
	</div>

	{#if daemon.error}
		<div class="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
			{daemon.error}
		</div>
	{/if}

	{#if daemon.connectionState === 'disconnected' || daemon.connectionState === 'error'}
		<button
			onclick={() => daemon.connect()}
			class="rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground hover:opacity-90"
		>
			Reconnect
		</button>
	{/if}
</div>
