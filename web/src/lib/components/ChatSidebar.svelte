<script lang="ts">
	import {
		Sidebar,
		SidebarContent,
		SidebarHeader,
		SidebarFooter,
		SidebarMenu,
		SidebarMenuItem,
		SidebarMenuButton,
		SidebarGroup,
		SidebarGroupContent
	} from '$lib/components/ui/sidebar/index';
	import { daemon } from '$lib/daemon/store.svelte';
	import { Plus, Trash2, MessageSquare, Wifi, WifiOff, Loader } from '@lucide/svelte';

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

<Sidebar>
	<SidebarHeader class="border-b px-4 py-3">
		<div class="flex items-center justify-between">
			<div class="flex items-center gap-2">
				<span class="text-foreground text-lg font-semibold tracking-tight">emo</span>
				<!-- Connection indicator -->
				{#if daemon.connectionState === 'connected'}
					<Wifi class="text-muted-foreground h-3.5 w-3.5" />
				{:else if daemon.connectionState === 'connecting'}
					<Loader class="text-muted-foreground h-3.5 w-3.5 animate-spin" />
				{:else}
					<WifiOff class="text-destructive h-3.5 w-3.5" />
				{/if}
			</div>
			<button
				onclick={() => daemon.newSession()}
				class="hover:bg-muted text-muted-foreground hover:text-foreground flex h-7 w-7 items-center justify-center rounded-md transition-colors"
				aria-label="New chat"
				disabled={daemon.connectionState !== 'connected'}
			>
				<Plus class="h-4 w-4" />
			</button>
		</div>
	</SidebarHeader>

	<SidebarContent>
		<SidebarGroup>
			<SidebarGroupContent>
				<SidebarMenu>
					{#each daemon.sessions as session (session.id)}
						<SidebarMenuItem>
							<SidebarMenuButton
								onclick={() => daemon.selectSession(session.id)}
								isActive={daemon.activeSessionId === session.id}
								class="group/item h-auto flex-col items-start gap-0.5 px-3 py-2"
							>
								<div class="flex w-full items-center gap-2">
									<MessageSquare class="text-muted-foreground h-3.5 w-3.5 shrink-0" />
									<span class="min-w-0 flex-1 truncate text-sm font-medium">
										{session.title}
									</span>
									<button
										onclick={(e) => {
											e.stopPropagation();
											daemon.deleteSession(session.id);
										}}
										class="text-muted-foreground hover:text-destructive ml-auto hidden h-5 w-5 shrink-0 items-center justify-center rounded opacity-0 transition-opacity group-hover/item:flex group-hover/item:opacity-100"
										aria-label="Delete chat"
									>
										<Trash2 class="h-3.5 w-3.5" />
									</button>
								</div>
								<span class="text-muted-foreground pl-5.5 text-xs">
									{formatRelativeTime(session.updated_at)}
								</span>
							</SidebarMenuButton>
						</SidebarMenuItem>
					{/each}

					{#if daemon.sessions.length === 0}
						<div class="text-muted-foreground px-3 py-6 text-center text-sm">
							{#if daemon.connectionState === 'connected'}
								No conversations yet
							{:else if daemon.connectionState === 'connecting'}
								Connecting to daemon…
							{:else}
								Daemon offline
							{/if}
						</div>
					{/if}
				</SidebarMenu>
			</SidebarGroupContent>
		</SidebarGroup>
	</SidebarContent>

	<SidebarFooter />
</Sidebar>
