<script lang="ts">
	import { daemon } from '$lib/daemon/store.svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import {
		Plus,
		ChevronDown,
		ChevronRight,
		Trash2,
		MessagesSquare,
		Settings,
		Bot,
		BookOpen,
		Plug,
		Sun,
		Moon,
		User
	} from '@lucide/svelte';

	// ── Theme ──────────────────────────────────────────────────────────────────
	let dark = $state(false);

	$effect(() => {
		const stored = localStorage.getItem('theme');
		dark =
			stored === 'dark' || (!stored && window.matchMedia('(prefers-color-scheme: dark)').matches);
		document.documentElement.classList.toggle('dark', dark);
	});

	function toggleTheme() {
		dark = !dark;
		document.documentElement.classList.toggle('dark', dark);
		localStorage.setItem('theme', dark ? 'dark' : 'light');
	}

	// ── Sessions ───────────────────────────────────────────────────────────────
	let sessionsOpen = $state(true);

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

	// ── Nav ────────────────────────────────────────────────────────────────────
	type NavItem = { tab: string; label: string; icon: typeof Settings };
	const navItems: NavItem[] = [
		{ tab: 'config', label: 'Config', icon: Settings },
		{ tab: 'agents', label: 'Agents', icon: Bot },
		{ tab: 'skills', label: 'Skills', icon: BookOpen },
		{ tab: 'mcps', label: 'MCPs', icon: Plug }
	];

	function isActive(tab: string) {
		return page.url.pathname === '/settings' && page.url.searchParams.get('tab') === tab;
	}
</script>

<div class="flex h-svh w-56 shrink-0 flex-col border-r border-sidebar-border bg-sidebar">
	<!-- Header -->
	<div class="flex shrink-0 items-center justify-between border-b px-3 py-2.5">
		<div class="flex items-center gap-2">
			<img src="/logo.png" alt="emo" class="h-6 w-6 select-none" />
			<span class="text-sm font-semibold">emo</span>
		</div>
		<!-- Connection dot -->
		{#if daemon.connectionState === 'connected'}
			<span class="h-2 w-2 rounded-full bg-green-500" title="Connected"></span>
		{:else if daemon.connectionState === 'connecting'}
			<span class="h-2 w-2 animate-pulse rounded-full bg-yellow-400" title="Connecting…"></span>
		{:else}
			<span class="h-2 w-2 rounded-full bg-destructive" title="Disconnected"></span>
		{/if}
	</div>

	<!-- Sessions — scrollable, fills space -->
	<div class="flex min-h-0 flex-1 flex-col overflow-y-auto">
		<!-- Sessions header -->
		<div class="flex items-center justify-between px-3 py-2">
			<button
				onclick={() => (sessionsOpen = !sessionsOpen)}
				class="flex flex-1 items-center gap-1.5 text-xs font-semibold tracking-wider text-muted-foreground uppercase hover:text-foreground"
			>
				{#if sessionsOpen}
					<ChevronDown class="h-3.5 w-3.5 shrink-0" />
				{:else}
					<ChevronRight class="h-3.5 w-3.5 shrink-0" />
				{/if}
				Sessions
			</button>
			<button
				onclick={() => daemon.newSession()}
				disabled={daemon.connectionState !== 'connected'}
				class="flex h-5 w-5 items-center justify-center rounded text-muted-foreground hover:bg-sidebar-accent hover:text-foreground disabled:opacity-40"
				aria-label="New session"
			>
				<Plus class="h-3.5 w-3.5" />
			</button>
		</div>

		<!-- Session list -->
		{#if sessionsOpen}
			<div class="flex flex-col px-1 pb-1">
				{#if daemon.sessions.length === 0}
					<p class="px-3 py-4 text-center text-xs text-muted-foreground">
						{#if daemon.connectionState === 'connected'}
							No conversations yet
						{:else if daemon.connectionState === 'connecting'}
							Connecting…
						{:else}
							Daemon offline
						{/if}
					</p>
				{:else}
					{#each daemon.sessions as session (session.id)}
						<div
							class="group/item relative rounded-md transition-colors hover:bg-sidebar-accent {daemon.activeSessionId ===
							session.id
								? 'bg-sidebar-accent'
								: ''}"
						>
							<button
								onclick={() => {
									daemon.selectSession(session.id);
									if (page.url.pathname !== '/') goto('/');
								}}
								class="flex w-full items-center gap-2 px-3 py-2 text-left"
							>
								<MessagesSquare class="h-5 w-5 shrink-0 text-muted-foreground" />
								<div class="min-w-0 flex-1">
									<p class="truncate text-sm font-medium">{session.title}</p>
									<p class="text-xs text-muted-foreground">
										{formatRelativeTime(session.updated_at)}
									</p>
								</div>
							</button>
							<button
								onclick={(e) => {
									e.stopPropagation();
									daemon.deleteSession(session.id);
								}}
								class="absolute top-1/2 right-2 hidden h-5 w-5 -translate-y-1/2 items-center justify-center rounded text-muted-foreground group-hover/item:flex hover:text-destructive"
								aria-label="Delete session"
							>
								<Trash2 class="h-3.5 w-3.5" />
							</button>
						</div>
					{/each}
				{/if}
			</div>
		{/if}
	</div>

	<!-- Bottom nav: settings + profile + theme -->
	<div class="flex shrink-0 flex-col gap-0.5 border-t p-2">
		{#each navItems as item}
			{@const Icon = item.icon}
			<a
				href="/settings?tab={item.tab}"
				class="flex items-center gap-2.5 rounded-md px-3 py-2 text-sm transition-colors {isActive(
					item.tab
				)
					? 'bg-sidebar-accent font-medium text-foreground'
					: 'text-muted-foreground hover:bg-sidebar-accent/60 hover:text-foreground'}"
			>
				<Icon class="h-4 w-4 shrink-0" />
				{item.label}
			</a>
		{/each}

		<!-- Divider -->
		<div class="my-1 border-t"></div>

		<!-- Profile row -->
		<div class="flex items-center gap-2.5 rounded-md px-3 py-2 text-sm text-muted-foreground">
			<div class="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-muted">
				<User class="h-3 w-3" />
			</div>
			<span class="flex-1 truncate text-xs">
				{daemon.connectionState === 'connected'
					? 'Connected'
					: daemon.connectionState === 'connecting'
						? 'Connecting…'
						: 'Offline'}
			</span>
		</div>

		<!-- Theme toggle -->
		<button
			onclick={toggleTheme}
			class="flex items-center gap-2.5 rounded-md px-3 py-2 text-sm text-muted-foreground transition-colors hover:bg-sidebar-accent/60 hover:text-foreground"
		>
			{#if dark}
				<Sun class="h-4 w-4 shrink-0" />
				<span class="text-sm">Light mode</span>
			{:else}
				<Moon class="h-4 w-4 shrink-0" />
				<span class="text-sm">Dark mode</span>
			{/if}
		</button>
	</div>
</div>
