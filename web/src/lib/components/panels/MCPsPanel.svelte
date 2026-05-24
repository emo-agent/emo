<script lang="ts">
	import { daemon } from '$lib/daemon/store.svelte';
	import type { MCPEntry } from '$lib/daemon/protocol';
	import {
		Terminal,
		Globe,
		Server,
		ChevronLeft,
		Trash2,
		Plus,
		X,
		Tag,
		ChevronRight,
		Type
	} from '@lucide/svelte';

	let selectedMCP = $state<string | null>(null);
	let isNew = $state(false);
	let newName = $state('');
	let mcpType = $state<'local' | 'remote'>('local');
	// Local fields
	let mcpCommand = $state('');
	let mcpArgs = $state<string[]>([]);
	let mcpEnv = $state<{ key: string; value: string }[]>([]);
	// Remote fields
	let mcpUrl = $state('');
	let saveMsg = $state('');

	function selectMCP(mcp: MCPEntry) {
		selectedMCP = mcp.name;
		isNew = false;
		mcpType = (mcp.type as 'local' | 'remote') ?? 'local';
		mcpCommand = (mcp.command as string) ?? '';
		const rawArgs = mcp.args as string[] | undefined;
		mcpArgs = rawArgs ? [...rawArgs] : [];
		const rawEnv = mcp.env as Record<string, string> | undefined;
		mcpEnv = rawEnv ? Object.entries(rawEnv).map(([key, value]) => ({ key, value })) : [];
		mcpUrl = (mcp.url as string) ?? '';
	}

	function startNew() {
		isNew = true;
		selectedMCP = null;
		newName = '';
		mcpType = 'local';
		mcpCommand = '';
		mcpArgs = [];
		mcpEnv = [];
		mcpUrl = '';
	}

	function addArg() {
		mcpArgs = [...mcpArgs, ''];
	}

	function removeArg(i: number) {
		mcpArgs = mcpArgs.filter((_, idx) => idx !== i);
	}

	function updateArg(i: number, val: string) {
		mcpArgs = mcpArgs.map((a, idx) => (idx === i ? val : a));
	}

	function addEnv() {
		mcpEnv = [...mcpEnv, { key: '', value: '' }];
	}

	function removeEnv(i: number) {
		mcpEnv = mcpEnv.filter((_, idx) => idx !== i);
	}

	function updateEnvKey(i: number, val: string) {
		mcpEnv = mcpEnv.map((e, idx) => (idx === i ? { ...e, key: val } : e));
	}

	function updateEnvValue(i: number, val: string) {
		mcpEnv = mcpEnv.map((e, idx) => (idx === i ? { ...e, value: val } : e));
	}

	function save() {
		const name = isNew ? newName.trim() : selectedMCP;
		if (!name) return;
		const config: Record<string, unknown> = { type: mcpType };
		if (mcpType === 'local') {
			config.command = mcpCommand;
			if (mcpArgs.length > 0) config.args = mcpArgs.filter(Boolean);
			if (mcpEnv.length > 0) {
				const env: Record<string, string> = {};
				for (const { key, value } of mcpEnv) {
					if (key) env[key] = value;
				}
				if (Object.keys(env).length > 0) config.env = env;
			}
		} else {
			config.url = mcpUrl;
		}
		daemon.saveMCP(name, config);
		saveMsg = '✓ Saved';
		if (isNew) {
			isNew = false;
			selectedMCP = name;
			daemon.fetchMCPs();
		}
		setTimeout(() => (saveMsg = ''), 2000);
	}

	function deleteMCP(name: string) {
		if (!confirm(`Delete MCP "${name}"?`)) return;
		daemon.deleteMCP(name);
		selectedMCP = null;
	}

	const iconClass =
		'absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground pointer-events-none';
	const inputClass =
		'h-9 rounded-md border bg-background pl-9 pr-3 text-sm outline-none focus:ring-1 focus:ring-ring w-full';
	const labelClass = 'text-xs font-medium text-muted-foreground';
</script>

{#if isNew || selectedMCP}
	<!-- Detail view -->
	<div class="mx-auto flex max-w-2xl flex-col gap-8 px-6 py-8">
		<!-- Breadcrumb + name -->
		<div>
			<button
				onclick={() => {
					selectedMCP = null;
					isNew = false;
				}}
				class="mb-2 flex items-center gap-1.5 text-xs text-muted-foreground transition-colors hover:text-foreground"
			>
				<ChevronLeft class="h-3.5 w-3.5" /> All MCPs
			</button>
			{#if isNew}
				<div class="flex flex-col gap-1.5">
					<label class={labelClass} for="mcp-name">Name</label>
					<div class="relative">
						<Tag class={iconClass} />
						<input
							id="mcp-name"
							type="text"
							bind:value={newName}
							placeholder="my-mcp"
							class={inputClass}
						/>
					</div>
				</div>
			{:else}
				<h2 class="text-lg font-semibold">{selectedMCP}</h2>
			{/if}
		</div>

		<!-- Type selector -->
		<div class="flex flex-col gap-3">
			<p class={labelClass}>Type</p>
			<div class="grid grid-cols-2 gap-3">
				<button
					onclick={() => (mcpType = 'local')}
					class="rounded-xl border-2 p-4 text-left transition-colors {mcpType === 'local'
						? 'border-primary bg-primary/5'
						: 'border-border hover:border-muted-foreground/40'}"
				>
					<Terminal class="mb-2 h-5 w-5 text-primary" />
					<p class="text-sm font-semibold">Local</p>
					<p class="text-xs text-muted-foreground">Run a local process</p>
				</button>
				<button
					onclick={() => (mcpType = 'remote')}
					class="rounded-xl border-2 p-4 text-left transition-colors {mcpType === 'remote'
						? 'border-primary bg-primary/5'
						: 'border-border hover:border-muted-foreground/40'}"
				>
					<Globe class="mb-2 h-5 w-5 text-primary" />
					<p class="text-sm font-semibold">Remote</p>
					<p class="text-xs text-muted-foreground">Connect to a remote server</p>
				</button>
			</div>
		</div>

		{#if mcpType === 'local'}
			<!-- Local config card -->
			<div class="flex flex-col gap-5 rounded-xl border bg-card p-6">
				<div class="mb-2 flex items-start gap-3">
					<div
						class="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary"
					>
						<Server class="h-4 w-4" />
					</div>
					<div>
						<h3 class="text-sm font-semibold text-foreground">Local Server</h3>
						<p class="mt-0.5 text-xs text-muted-foreground">Configure the local process to run</p>
					</div>
				</div>

				<div class="flex flex-col gap-4">
					<div class="flex flex-col gap-1.5">
						<label class={labelClass} for="mcp-cmd">Command</label>
						<div class="relative">
							<Terminal class={iconClass} />
							<input
								id="mcp-cmd"
								type="text"
								bind:value={mcpCommand}
								placeholder="npx -y @modelcontextprotocol/server-filesystem"
								class={inputClass}
							/>
						</div>
					</div>

					<!-- Args -->
					<div class="flex flex-col gap-2">
						<div class="flex items-center justify-between">
							<p class={labelClass}>Arguments</p>
							<button
								onclick={addArg}
								class="flex items-center gap-1 text-xs text-primary hover:underline"
							>
								<Plus class="h-3 w-3" /> Add arg
							</button>
						</div>
						{#if mcpArgs.length > 0}
							<div class="flex flex-col gap-2">
								{#each mcpArgs as arg, i (i)}
									<div class="flex gap-2">
										<div class="relative flex-1">
											<ChevronRight class={iconClass} />
											<input
												type="text"
												value={arg}
												oninput={(e) => updateArg(i, (e.currentTarget as HTMLInputElement).value)}
												placeholder="arg value"
												class="h-9 w-full rounded-md border bg-background pr-3 pl-9 text-sm outline-none focus:ring-1 focus:ring-ring"
											/>
										</div>
										<button
											onclick={() => removeArg(i)}
											class="flex h-9 w-9 items-center justify-center rounded-md border text-muted-foreground transition-colors hover:border-destructive/50 hover:text-destructive"
										>
											<X class="h-3.5 w-3.5" />
										</button>
									</div>
								{/each}
							</div>
						{:else}
							<p class="text-xs text-muted-foreground italic">No arguments added</p>
						{/if}
					</div>

					<!-- Env vars -->
					<div class="flex flex-col gap-2">
						<div class="flex items-center justify-between">
							<p class={labelClass}>Environment Variables</p>
							<button
								onclick={addEnv}
								class="flex items-center gap-1 text-xs text-primary hover:underline"
							>
								<Plus class="h-3 w-3" /> Add env var
							</button>
						</div>
						{#if mcpEnv.length > 0}
							<div class="flex flex-col gap-2">
								{#each mcpEnv as envItem, i (i)}
									<div class="flex gap-2">
										<div class="relative w-1/3">
											<Tag class={iconClass} />
											<input
												type="text"
												value={envItem.key}
												oninput={(e) =>
													updateEnvKey(i, (e.currentTarget as HTMLInputElement).value)}
												placeholder="KEY"
												class="h-9 w-full rounded-md border bg-background pr-3 pl-9 font-mono text-sm outline-none focus:ring-1 focus:ring-ring"
											/>
										</div>
										<div class="relative flex-1">
											<Type class={iconClass} />
											<input
												type="text"
												value={envItem.value}
												oninput={(e) =>
													updateEnvValue(i, (e.currentTarget as HTMLInputElement).value)}
												placeholder="value"
												class="h-9 w-full rounded-md border bg-background pr-3 pl-9 text-sm outline-none focus:ring-1 focus:ring-ring"
											/>
										</div>
										<button
											onclick={() => removeEnv(i)}
											class="flex h-9 w-9 items-center justify-center rounded-md border text-muted-foreground transition-colors hover:border-destructive/50 hover:text-destructive"
										>
											<X class="h-3.5 w-3.5" />
										</button>
									</div>
								{/each}
							</div>
						{:else}
							<p class="text-xs text-muted-foreground italic">No environment variables added</p>
						{/if}
					</div>
				</div>
			</div>
		{:else}
			<!-- Remote config card -->
			<div class="flex flex-col gap-5 rounded-xl border bg-card p-6">
				<div class="mb-2 flex items-start gap-3">
					<div
						class="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary"
					>
						<Globe class="h-4 w-4" />
					</div>
					<div>
						<h3 class="text-sm font-semibold text-foreground">Remote Server</h3>
						<p class="mt-0.5 text-xs text-muted-foreground">URL of the remote MCP server</p>
					</div>
				</div>
				<div class="flex flex-col gap-1.5">
					<label class={labelClass} for="mcp-url">URL</label>
					<div class="relative">
						<Globe class={iconClass} />
						<input
							id="mcp-url"
							type="url"
							bind:value={mcpUrl}
							placeholder="https://..."
							class={inputClass}
						/>
					</div>
				</div>
			</div>
		{/if}

		<!-- Actions -->
		<div class="flex items-center gap-3 pt-2 pb-4">
			<button
				onclick={save}
				class="rounded-md bg-primary px-6 py-2 text-sm font-medium text-primary-foreground transition-opacity hover:opacity-90"
			>
				{saveMsg || 'Save changes'}
			</button>
			{#if saveMsg}<p class="text-xs text-muted-foreground">{saveMsg}</p>{/if}
			{#if selectedMCP}
				<button
					onclick={() => selectedMCP && deleteMCP(selectedMCP)}
					class="ml-auto flex items-center gap-1.5 rounded-md border border-destructive/50 px-4 py-2 text-sm font-medium text-destructive transition-colors hover:bg-destructive/10"
				>
					<Trash2 class="h-3.5 w-3.5" /> Delete
				</button>
			{/if}
		</div>
	</div>
{:else}
	<!-- List view -->
	<div class="mx-auto flex max-w-2xl flex-col gap-6 px-6 py-8">
		<div class="flex items-center justify-between">
			<div>
				<h2 class="text-lg font-semibold">MCP Servers</h2>
				<p class="mt-0.5 text-sm text-muted-foreground">
					Manage your Model Context Protocol servers
				</p>
			</div>
			<button
				onclick={startNew}
				class="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-opacity hover:opacity-90"
			>
				+ New MCP
			</button>
		</div>

		<div class="flex flex-col gap-2">
			{#each daemon.mcps as mcp (mcp.name)}
				{@const type = (mcp.type as string) ?? 'local'}
				{@const cmd = mcp.command as string | undefined}
				<div
					class="flex items-center gap-3 rounded-xl border bg-card px-4 py-3 transition-colors hover:bg-accent/30"
				>
					<div
						class="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-muted text-xs font-bold text-muted-foreground"
					>
						{mcp.name[0].toUpperCase()}
					</div>
					<div class="min-w-0 flex-1">
						<p class="truncate text-sm font-semibold">{mcp.name}</p>
						<p class="mt-0.5 truncate text-xs text-muted-foreground">
							{type}{cmd ? ` · ${cmd}` : ''}
						</p>
					</div>
					<span
						class="shrink-0 rounded-full bg-muted px-2.5 py-0.5 text-xs font-medium text-muted-foreground"
					>
						{type}
					</span>
					<button
						onclick={() => selectMCP(mcp)}
						class="shrink-0 rounded-md border px-3 py-1.5 text-xs font-medium transition-colors hover:bg-accent"
					>
						Edit
					</button>
				</div>
			{/each}
			{#if daemon.mcps.length === 0}
				<p class="py-8 text-center text-sm text-muted-foreground">No MCPs configured</p>
			{/if}
		</div>
	</div>
{/if}
