<script lang="ts">
	import { daemon } from '$lib/daemon/store.svelte';
	import ChatMessage from '$lib/components/ChatMessage.svelte';
	import ChatInput from '$lib/components/ChatInput.svelte';

	let scrollEl = $state<HTMLElement | null>(null);

	$effect(() => {
		// Track messages length to trigger scroll
		const _ = daemon.messages.length;
		if (scrollEl) {
			scrollEl.scrollTop = scrollEl.scrollHeight;
		}
	});
</script>

<div class="flex h-svh flex-col">
	<!-- Top bar -->
	<header class="flex shrink-0 items-center gap-3 border-b px-4 py-3">
		<h1 class="text-foreground flex-1 truncate font-semibold">
			{daemon.activeSession?.title ?? 'emo'}
		</h1>
	</header>

	<!-- Error banner -->
	{#if daemon.error}
		<div
			class="bg-destructive/10 text-destructive border-destructive/20 shrink-0 border-b px-4 py-2 text-sm"
		>
			{daemon.error}
		</div>
	{/if}

	<!-- Messages area -->
	<div bind:this={scrollEl} class="flex-1 overflow-y-auto px-4 py-6">
		{#if daemon.messages.length === 0}
			<div class="flex h-full flex-col items-center justify-center gap-3">
				<p class="text-muted-foreground text-lg font-medium">Start a conversation</p>
				<p class="text-muted-foreground/60 text-sm">Ask emo anything…</p>
			</div>
		{:else}
			<div class="mx-auto flex max-w-3xl flex-col gap-4">
				{#each daemon.messages as message (message.id)}
					<ChatMessage {message} />
				{/each}
			</div>
		{/if}
	</div>

	<!-- Input -->
	<div class="shrink-0">
		<div class="mx-auto max-w-3xl">
			<ChatInput />
		</div>
	</div>
</div>
