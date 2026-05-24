<script lang="ts">
	import { daemon } from '$lib/daemon/store.svelte';
	import { Plus, Trash2, MessagesSquare } from '@lucide/svelte';

	function formatRelativeTime(ts: number): string {
		const now = Date.now() / 1000;
		const diff = now - ts;
		const mins = Math.floor(diff / 60);
		const hours = Math.floor(diff / 3600);
		const days = Math.floor(diff / 86400);
		if (mins < 1) return 'just now';
		if (mins < 60) return `${mins}m ago`;
		if (hours < 24) return `${hours}h ago`;
		if (days < 7) return `${days}d ago`;
		return new Date(ts * 1000).toLocaleDateString();
	}
</script>

<div class="flex h-full flex-col">
	<div class="shrink-0 border-b px-3 py-2">
		<button
			onclick={() => daemon.newSession()}
			disabled={daemon.connectionState !== 'connected'}
			class="flex w-full items-center gap-2 rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground transition-opacity hover:opacity-90 disabled:opacity-50"
		>
			<Plus class="h-4 w-4" />
			New Chat
		</button>
	</div>

	<div class="flex-1 overflow-y-auto p-2">
		{#if daemon.sessions.length === 0}
			<div class="px-3 py-6 text-center text-sm text-muted-foreground">
				{#if daemon.connectionState === 'connected'}
					No conversations yet
				{:else if daemon.connectionState === 'connecting'}
					Connecting to daemon…
				{:else}
					Daemon offline
				{/if}
			</div>
		{:else}
			{#each daemon.sessions as session (session.id)}
				<div
					class="group/item relative w-full rounded-md px-3 py-2 transition-colors hover:bg-sidebar-accent {daemon.activeSessionId ===
					session.id
						? 'bg-sidebar-accent'
						: ''}"
				>
					<button
						onclick={() => daemon.selectSession(session.id)}
						class="flex w-full items-center gap-2 text-left"
					>
						<MessagesSquare class="h-5 w-5 shrink-0 text-muted-foreground" />
						<span class="min-w-0 flex-1 truncate text-sm font-medium">
							{session.title}
						</span>
					</button>
					<div class="flex items-center justify-between">
						<span class="pl-5.5 text-xs text-muted-foreground">
							{formatRelativeTime(session.updated_at)}
						</span>
						<button
							onclick={(e) => {
								e.stopPropagation();
								daemon.deleteSession(session.id);
							}}
							class="hidden h-5 w-5 shrink-0 items-center justify-center rounded text-muted-foreground opacity-0 transition-opacity group-hover/item:flex group-hover/item:opacity-100 hover:text-destructive"
							aria-label="Delete chat"
						>
							<Trash2 class="h-3.5 w-3.5" />
						</button>
					</div>
				</div>
			{/each}
		{/if}
	</div>
</div>
