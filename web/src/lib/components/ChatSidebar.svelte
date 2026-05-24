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
	import { chat } from '$lib/stores/chat.svelte';
	import { Plus, Trash2, MessageSquare } from '@lucide/svelte';

	function formatRelativeTime(date: Date): string {
		const now = new Date();
		const diffMs = now.getTime() - date.getTime();
		const diffMins = Math.floor(diffMs / 60000);
		const diffHours = Math.floor(diffMs / 3600000);
		const diffDays = Math.floor(diffMs / 86400000);

		if (diffMins < 1) return 'just now';
		if (diffMins < 60) return `${diffMins}m ago`;
		if (diffHours < 24) return `${diffHours}h ago`;
		if (diffDays < 7) return `${diffDays}d ago`;
		return date.toLocaleDateString();
	}
</script>

<Sidebar>
	<SidebarHeader class="border-b px-4 py-3">
		<div class="flex items-center justify-between">
			<span class="text-foreground text-lg font-semibold tracking-tight">emo</span>
			<button
				onclick={() => chat.newSession()}
				class="hover:bg-muted text-muted-foreground hover:text-foreground flex h-7 w-7 items-center justify-center rounded-md transition-colors"
				aria-label="New chat"
			>
				<Plus class="h-4 w-4" />
			</button>
		</div>
	</SidebarHeader>

	<SidebarContent>
		<SidebarGroup>
			<SidebarGroupContent>
				<SidebarMenu>
					{#each chat.sessions as session (session.id)}
						<SidebarMenuItem>
							<SidebarMenuButton
								onclick={() => chat.selectSession(session.id)}
								isActive={chat.activeSessionId === session.id}
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
											chat.deleteSession(session.id);
										}}
										class="text-muted-foreground hover:text-destructive ml-auto hidden h-5 w-5 shrink-0 items-center justify-center rounded opacity-0 transition-opacity group-hover/item:flex group-hover/item:opacity-100"
										aria-label="Delete chat"
									>
										<Trash2 class="h-3.5 w-3.5" />
									</button>
								</div>
								<span class="text-muted-foreground pl-5.5 text-xs">
									{formatRelativeTime(session.updatedAt)}
								</span>
							</SidebarMenuButton>
						</SidebarMenuItem>
					{/each}

					{#if chat.sessions.length === 0}
						<div class="text-muted-foreground px-3 py-6 text-center text-sm">
							No conversations yet
						</div>
					{/if}
				</SidebarMenu>
			</SidebarGroupContent>
		</SidebarGroup>
	</SidebarContent>

	<SidebarFooter />
</Sidebar>
