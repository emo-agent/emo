<script lang="ts">
	import { daemon } from '$lib/daemon/store.svelte';
	import ChipInput from '$lib/components/ChipInput.svelte';
	import { Cpu, FileText, Wrench, Users, BookOpen, ChevronLeft, Trash2, Bot, Link, KeyRound, Thermometer, Hash, RefreshCw, ScanText } from '@lucide/svelte';

	const AVAILABLE_TOOLS = ['shell', 'file_read', 'file_write', 'web_fetch'] as const;

	let selectedAgent = $state<string | null>(null);
	let isNew = $state(false);
	let saveMsg = $state('');

	// Form fields
	let agentName = $state<string[]>([]);
	// LLM overrides (empty = inherit)
	let llmModel = $state('');
	let llmApiBase = $state('');
	let llmApiKey = $state('');
	let llmTemperature = $state('');
	let llmMaxTokens = $state('');
	let llmMaxIterations = $state('');
	let llmContextWindow = $state('');
	// Prompt
	let prompt = $state('');
	// Tools
	let selectedTools = $state<string[]>([]);
	// Subagents / skills
	let subagentChips = $state<string[]>([]);
	let skillChips = $state<string[]>([]);

	$effect(() => {
		const ac = daemon.activeAgentConfig;
		if (!ac) return;
		const c = ac.config;

		const llm = c.llm as Record<string, unknown> | undefined;
		llmModel = (llm?.model as string) ?? '';
		llmApiBase = (llm?.api_base as string) ?? '';
		llmApiKey = (llm?.api_key as string) ?? '';
		llmTemperature = llm?.temperature != null ? String(llm.temperature) : '';
		llmMaxTokens = llm?.max_tokens != null ? String(llm.max_tokens) : '';
		llmMaxIterations = llm?.max_iterations != null ? String(llm.max_iterations) : '';
		llmContextWindow = llm?.context_window != null ? String(llm.context_window) : '';

		prompt = (c.prompt as string) ?? (c.system as string) ?? '';

		const rawTools = c.tools as string[] | null | undefined;
		if (rawTools === null || rawTools === undefined) {
			selectedTools = [...AVAILABLE_TOOLS];
		} else {
			selectedTools = rawTools;
		}

		const sa = c.subagents as string[] | undefined;
		subagentChips = sa ? [...sa] : [];

		const sk = c.skills as string[] | undefined;
		skillChips = sk ? [...sk] : [];
	});

	function selectAgent(name: string) {
		selectedAgent = name;
		isNew = false;
		agentName = [name];
		daemon.fetchAgent(name);
	}

	function startNew() {
		isNew = true;
		selectedAgent = null;
		agentName = [];
		llmModel = '';
		llmApiBase = '';
		llmApiKey = '';
		llmTemperature = '';
		llmMaxTokens = '';
		llmMaxIterations = '';
		llmContextWindow = '';
		prompt = '';
		selectedTools = [];
		subagentChips = [];
		skillChips = [];
	}

	function buildConfig(): Record<string, unknown> {
		const llm: Record<string, unknown> = {};
		if (llmModel) llm.model = llmModel;
		if (llmApiBase) llm.api_base = llmApiBase;
		if (llmApiKey) llm.api_key = llmApiKey;
		if (llmTemperature !== '') llm.temperature = Number(llmTemperature);
		if (llmMaxTokens !== '') llm.max_tokens = Number(llmMaxTokens);
		if (llmMaxIterations !== '') llm.max_iterations = Number(llmMaxIterations);
		if (llmContextWindow !== '') llm.context_window = Number(llmContextWindow);

		let tools: string[] | null;
		if (selectedTools.length === AVAILABLE_TOOLS.length) {
			tools = null;
		} else if (selectedTools.length === 0) {
			tools = [];
		} else {
			tools = selectedTools;
		}

		const config: Record<string, unknown> = {};
		if (Object.keys(llm).length > 0) config.llm = llm;
		if (prompt) config.prompt = prompt;
		config.tools = tools;
		if (subagentChips.length > 0) config.subagents = subagentChips;
		if (skillChips.length > 0) config.skills = skillChips;
		return config;
	}

	function save() {
		const name = isNew ? agentName[0]?.trim() : selectedAgent;
		if (!name) return;
		const config = buildConfig();
		daemon.saveAgent(name, config);
		saveMsg = '✓ Saved';
		if (isNew) {
			isNew = false;
			selectedAgent = name;
			daemon.fetchAgents();
		}
		setTimeout(() => (saveMsg = ''), 2000);
	}

	function deleteAgent(name: string) {
		if (!confirm(`Delete agent "${name}"?`)) return;
		daemon.deleteAgent(name);
		selectedAgent = null;
	}

	const iconClass = 'absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground pointer-events-none';
	const inputClass =
		'h-9 rounded-md border bg-background pl-9 pr-3 text-sm outline-none focus:ring-1 focus:ring-ring w-full';
	const labelClass = 'text-xs font-medium text-muted-foreground';

	const subagentSuggestions = $derived(
		daemon.agents.map((a) => a.name).filter((n) => n !== selectedAgent)
	);
</script>

{#if isNew || selectedAgent}
	<!-- Detail / edit view -->
	<div class="max-w-2xl mx-auto py-8 px-6 flex flex-col gap-8">
		<!-- Breadcrumb + name -->
		<div>
			<button
				onclick={() => { selectedAgent = null; isNew = false; }}
				class="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground mb-2 transition-colors"
			>
				<ChevronLeft class="h-3.5 w-3.5" /> All Agents
			</button>
			{#if isNew}
				<div class="flex flex-col gap-1.5">
					<label class={labelClass} for="ag-name">Agent Name</label>
					<ChipInput
						id="ag-name"
						bind:values={agentName}
						suggestions={daemon.agents.map((a) => a.name)}
						placeholder="my-agent"
						singleValue={true}
					/>
				</div>
			{:else}
				<h2 class="text-lg font-semibold">{selectedAgent}</h2>
			{/if}
		</div>

		<!-- LLM Overrides card -->
		<div class="rounded-xl border bg-card p-6 flex flex-col gap-5">
			<div class="flex items-start gap-3 mb-2">
				<div class="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
					<Cpu class="h-4 w-4" />
				</div>
				<div>
					<h3 class="text-sm font-semibold text-foreground">LLM Overrides</h3>
					<p class="text-xs text-muted-foreground mt-0.5">Leave blank to inherit from the global agent config</p>
				</div>
			</div>

			<div class="flex flex-col gap-4">
				<div class="flex flex-col gap-1.5">
					<label class={labelClass} for="ag-llm-model">Model</label>
					<div class="relative">
						<Bot class={iconClass} />
						<input id="ag-llm-model" type="text" bind:value={llmModel} placeholder="inherits from agent.llm.model" class={inputClass} />
					</div>
				</div>
				<div class="flex flex-col gap-1.5">
					<label class={labelClass} for="ag-llm-base">API Base</label>
					<div class="relative">
						<Link class={iconClass} />
						<input id="ag-llm-base" type="text" bind:value={llmApiBase} placeholder="optional" class={inputClass} />
					</div>
				</div>
				<div class="flex flex-col gap-1.5">
					<label class={labelClass} for="ag-llm-key">API Key</label>
					<div class="relative">
						<KeyRound class={iconClass} />
						<input id="ag-llm-key" type="password" bind:value={llmApiKey} placeholder="optional" class={inputClass} />
					</div>
				</div>
				<div class="grid grid-cols-2 gap-4">
					<div class="flex flex-col gap-1.5">
						<label class={labelClass} for="ag-llm-temp">Temperature</label>
						<div class="relative">
							<Thermometer class={iconClass} />
							<input id="ag-llm-temp" type="number" min="0" max="2" step="0.05" bind:value={llmTemperature} placeholder="inherit" class={inputClass} />
						</div>
					</div>
					<div class="flex flex-col gap-1.5">
						<label class={labelClass} for="ag-llm-maxtok">Max Tokens</label>
						<div class="relative">
							<Hash class={iconClass} />
							<input id="ag-llm-maxtok" type="number" bind:value={llmMaxTokens} placeholder="inherit" class={inputClass} />
						</div>
					</div>
				</div>
				<div class="grid grid-cols-2 gap-4">
					<div class="flex flex-col gap-1.5">
						<label class={labelClass} for="ag-llm-maxiter">Max Iterations</label>
						<div class="relative">
							<RefreshCw class={iconClass} />
							<input id="ag-llm-maxiter" type="number" bind:value={llmMaxIterations} placeholder="inherit" class={inputClass} />
						</div>
					</div>
					<div class="flex flex-col gap-1.5">
						<label class={labelClass} for="ag-llm-ctx">Context Window</label>
						<div class="relative">
							<ScanText class={iconClass} />
							<input id="ag-llm-ctx" type="number" bind:value={llmContextWindow} placeholder="inherit" class={inputClass} />
						</div>
					</div>
				</div>
			</div>
		</div>

		<!-- Prompt card -->
		<div class="rounded-xl border bg-card p-6 flex flex-col gap-5">
			<div class="flex items-start gap-3 mb-2">
				<div class="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
					<FileText class="h-4 w-4" />
				</div>
				<div>
					<h3 class="text-sm font-semibold text-foreground">Prompt</h3>
					<p class="text-xs text-muted-foreground mt-0.5">System prompt for this agent</p>
				</div>
			</div>
			<textarea
				id="ag-prompt"
				bind:value={prompt}
				rows={8}
				class="w-full rounded-md border bg-background px-3 py-2 font-mono text-xs outline-none focus:ring-1 focus:ring-ring resize-y"
			></textarea>
		</div>

		<!-- Tools card -->
		<div class="rounded-xl border bg-card p-6 flex flex-col gap-5">
			<div class="flex items-start gap-3 mb-2">
				<div class="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
					<Wrench class="h-4 w-4" />
				</div>
				<div>
					<h3 class="text-sm font-semibold text-foreground">Tools</h3>
					<p class="text-xs text-muted-foreground mt-0.5">Select all = all tools (null); select none = no tools</p>
				</div>
			</div>
			<ChipInput
				bind:values={selectedTools}
				suggestions={[...AVAILABLE_TOOLS]}
				placeholder="Add tool…"
			/>
		</div>

		<!-- Subagents & Skills card -->
		<div class="rounded-xl border bg-card p-6 flex flex-col gap-5">
			<div class="flex items-start gap-3 mb-2">
				<div class="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
					<Users class="h-4 w-4" />
				</div>
				<div>
					<h3 class="text-sm font-semibold text-foreground">Subagents &amp; Skills</h3>
					<p class="text-xs text-muted-foreground mt-0.5">Agents and skills this agent can delegate to</p>
				</div>
			</div>

			<div class="flex flex-col gap-4">
				<div class="flex flex-col gap-1.5">
					<div class="flex items-center gap-2 mb-0.5">
						<Users class="h-3.5 w-3.5 text-muted-foreground" />
						<label class={labelClass} for="ag-subagents">Subagents</label>
					</div>
					<ChipInput
						id="ag-subagents"
						bind:values={subagentChips}
						suggestions={subagentSuggestions}
						placeholder="Add subagent…"
					/>
				</div>
				<div class="flex flex-col gap-1.5">
					<div class="flex items-center gap-2 mb-0.5">
						<BookOpen class="h-3.5 w-3.5 text-muted-foreground" />
						<label class={labelClass} for="ag-skills">Skills</label>
					</div>
					<ChipInput
						id="ag-skills"
						bind:values={skillChips}
						suggestions={daemon.skills.map((s) => s.name)}
						placeholder="Add skill…"
					/>
				</div>
			</div>
		</div>

		<!-- Actions -->
		<div class="flex items-center gap-3 pt-2 pb-4">
			<button
				onclick={save}
				class="rounded-md bg-primary px-6 py-2 text-sm font-medium text-primary-foreground hover:opacity-90 transition-opacity"
			>
				{saveMsg || 'Save changes'}
			</button>
			{#if saveMsg}<p class="text-xs text-muted-foreground">{saveMsg}</p>{/if}
			{#if selectedAgent}
				{@const agent = daemon.agents.find((a) => a.name === selectedAgent)}
				{#if agent?.source === 'user'}
					<button
						onclick={() => selectedAgent && deleteAgent(selectedAgent)}
						class="ml-auto flex items-center gap-1.5 rounded-md border border-destructive/50 px-4 py-2 text-sm font-medium text-destructive hover:bg-destructive/10 transition-colors"
					>
						<Trash2 class="h-3.5 w-3.5" /> Delete
					</button>
				{/if}
			{/if}
		</div>
	</div>
{:else}
	<!-- List view -->
	<div class="max-w-2xl mx-auto py-8 px-6 flex flex-col gap-6">
		<div class="flex items-center justify-between">
			<div>
				<h2 class="text-lg font-semibold">Agents</h2>
				<p class="text-sm text-muted-foreground mt-0.5">Manage your AI agents</p>
			</div>
			<button
				onclick={startNew}
				class="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90 transition-opacity"
			>
				+ New Agent
			</button>
		</div>

		<div class="flex flex-col gap-2">
			{#each daemon.agents as agent (agent.name)}
				{@const tools = agent.config.tools as string[] | null | undefined}
				<div class="flex items-center gap-3 rounded-xl border bg-card px-4 py-3 hover:bg-accent/30 transition-colors">
					<div class="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-muted text-muted-foreground text-xs font-bold">
						{agent.name[0].toUpperCase()}
					</div>
					<div class="flex-1 min-w-0">
						<p class="text-sm font-semibold truncate">{agent.name}</p>
						<p class="text-xs text-muted-foreground mt-0.5">
							{tools === null || tools === undefined ? 'all tools' : tools.length === 0 ? 'no tools' : `${tools.length} tool${tools.length !== 1 ? 's' : ''}`}
						</p>
					</div>
					<span class="rounded-full px-2.5 py-0.5 text-xs font-medium shrink-0 {agent.source === 'user' ? 'bg-primary/15 text-primary' : 'bg-muted text-muted-foreground'}">
						{agent.source}
					</span>
					<button
						onclick={() => selectAgent(agent.name)}
						class="rounded-md border px-3 py-1.5 text-xs font-medium hover:bg-accent shrink-0 transition-colors"
					>
						Edit
					</button>
				</div>
			{/each}
			{#if daemon.agents.length === 0}
				<p class="text-sm text-muted-foreground py-8 text-center">No agents found</p>
			{/if}
		</div>
	</div>
{/if}
