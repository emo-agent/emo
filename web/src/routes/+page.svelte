<script lang="ts">
	import { daemon } from '$lib/daemon/store.svelte';
	import ChatMessage from '$lib/components/ChatMessage.svelte';
	import ChatInput from '$lib/components/ChatInput.svelte';

	let scrollEl = $state<HTMLElement | null>(null);

	// Scroll to bottom when new messages arrive or content streams in
	$effect(() => {
		// track both message count and the content of the last message (streaming tokens)
		void daemon.messages.length;
		const lastMsg = daemon.messages[daemon.messages.length - 1];
		void (lastMsg?.content?.length ?? 0);
		if (scrollEl) {
			scrollEl.scrollTop = scrollEl.scrollHeight;
		}
	});
</script>

<div class="flex h-svh flex-col">
	<!-- Top bar -->
	<header class="flex shrink-0 items-center gap-3 border-b px-4 py-3">
		<div class="flex items-center gap-2">
			<img src="/logo.png" alt="emo" class="h-6 w-6 select-none" />
			<h1 class="truncate font-semibold text-foreground">
				{daemon.activeSession?.title ?? 'emo'}
			</h1>
		</div>
	</header>

	<!-- Error banner -->
	{#if daemon.error}
		<div
			class="shrink-0 border-b border-destructive/20 bg-destructive/10 px-4 py-2 text-sm text-destructive"
		>
			{daemon.error}
		</div>
	{/if}

	<!-- Messages / Welcome -->
	<div bind:this={scrollEl} class="flex-1 overflow-y-auto px-4 py-6">
		{#if daemon.messages.length === 0}
			<div
				class="mx-auto flex h-full max-w-2xl flex-col items-center justify-center gap-6 text-center"
			>
				<!-- Greeting -->
				<div class="space-y-2">
					<div class="flex flex-col items-center">
						<img src="/logo.png" class="h-15 w-15" alt="Emo Logo" />
					</div>

					<h2 class="text-xl font-medium tracking-tight text-foreground sm:text-3xl">
						How can I help you today?
					</h2>
					<p class="text-sm text-muted-foreground"></p>
				</div>
				<ChatInput />
			</div>
		{:else}
			<div class="mx-auto flex max-w-3xl flex-col gap-4">
				{#each daemon.messages as message (message.id)}
					<ChatMessage {message} />
				{/each}
			</div>
		{/if}
	</div>

	{#if daemon.messages.length !== 0}
		<!-- Input -->
		<div class="shrink-0">
			<div class="mx-auto max-w-2xl">
				<ChatInput />
			</div>
		</div>
	{/if}
</div>
