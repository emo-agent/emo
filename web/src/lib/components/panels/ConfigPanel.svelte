<script lang="ts">
	import { daemon } from '$lib/daemon/store.svelte';
	import { Cpu, GitFork, Database, Sparkles, BrainCircuit, Globe, Bot, Link, KeyRound, Thermometer, Hash, RefreshCw, ScanText, Users, HardDrive } from '@lucide/svelte';

	// ── Agent LLM ──────────────────────────────────────────────────────────────
	let agentModel = $state('');
	let agentApiBase = $state('');
	let agentApiKey = $state('');
	let agentTemperature = $state(0.7);
	let agentMaxTokens = $state('');
	let agentMaxIterations = $state(20);
	let agentContextWindow = $state(40000);

	// ── Router ─────────────────────────────────────────────────────────────────
	let routerEnabled = $state(true);
	let routerDefault = $state('general');
	let routerAgents = $state('general, code, research');
	let routerTemperature = $state(0.0);
	let routerMaxTokens = $state('');

	// ── Memory ─────────────────────────────────────────────────────────────────
	let memoryDbPath = $state('~/.emo/memory.db');
	let memoryMaxFacts = $state(200);
	let memorySummarizeAfter = $state(10);

	// ── Features ───────────────────────────────────────────────────────────────
	let featRouting = $state(true);
	let featMemory = $state(true);
	let featWeb = $state(false);

	let saved = $state(false);

	$effect(() => {
		const data = daemon.configData;
		if (!data) return;

		const agent = data.agent as Record<string, unknown> | undefined;
		const llm = agent?.llm as Record<string, unknown> | undefined;
		if (llm) {
			agentModel = (llm.model as string) ?? '';
			agentApiBase = (llm.api_base as string) ?? '';
			agentApiKey = (llm.api_key as string) ?? '';
			agentTemperature = (llm.temperature as number) ?? 0.7;
			agentMaxTokens = llm.max_tokens != null ? String(llm.max_tokens) : '';
			agentMaxIterations = (llm.max_iterations as number) ?? 20;
			agentContextWindow = (llm.context_window as number) ?? 40000;
		}

		const router = data.router as Record<string, unknown> | undefined;
		if (router) {
			routerEnabled = (router.enabled as boolean) ?? true;
			routerDefault = (router.default as string) ?? 'general';
			const ragents = router.agents as string[] | undefined;
			routerAgents = ragents ? ragents.join(', ') : 'general, code, research';
			const rllm = router.llm as Record<string, unknown> | undefined;
			if (rllm) {
				routerTemperature = (rllm.temperature as number) ?? 0.0;
				routerMaxTokens = rllm.max_tokens != null ? String(rllm.max_tokens) : '';
			}
		}

		const memory = data.memory as Record<string, unknown> | undefined;
		if (memory) {
			memoryDbPath = (memory.db_path as string) ?? '~/.emo/memory.db';
			memoryMaxFacts = (memory.max_facts as number) ?? 200;
			memorySummarizeAfter = (memory.summarize_after as number) ?? 10;
		}

		const features = data.features as Record<string, unknown> | undefined;
		if (features) {
			featRouting = (features.routing as boolean) ?? true;
			featMemory = (features.memory as boolean) ?? true;
			featWeb = (features.web as boolean) ?? false;
		}
	});

	function save() {
		const agentsList = routerAgents
			.split(',')
			.map((s) => s.trim())
			.filter(Boolean);

		const patch: Record<string, unknown> = {
			agent: {
				llm: {
					model: agentModel,
					...(agentApiBase ? { api_base: agentApiBase } : {}),
					...(agentApiKey ? { api_key: agentApiKey } : {}),
					temperature: agentTemperature,
					max_iterations: agentMaxIterations,
					context_window: agentContextWindow,
					...(agentMaxTokens ? { max_tokens: Number(agentMaxTokens) } : {})
				}
			},
			router: {
				enabled: routerEnabled,
				default: routerDefault,
				agents: agentsList,
				llm: {
					temperature: routerTemperature,
					...(routerMaxTokens ? { max_tokens: Number(routerMaxTokens) } : {})
				}
			},
			memory: {
				db_path: memoryDbPath,
				max_facts: memoryMaxFacts,
				summarize_after: memorySummarizeAfter
			},
			features: {
				routing: featRouting,
				memory: featMemory,
				web: featWeb
			}
		};
		daemon.setConfig(patch);
		saved = true;
		setTimeout(() => (saved = false), 2000);
	}

	const iconClass = 'absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground pointer-events-none';
	const inputClass =
		'h-9 rounded-md border bg-background pl-9 pr-3 text-sm outline-none focus:ring-1 focus:ring-ring w-full';
	const labelClass = 'text-xs font-medium text-muted-foreground';
</script>

<div class="max-w-2xl mx-auto py-8 px-6 flex flex-col gap-8">

	<!-- Agent LLM -->
	<div class="rounded-xl border bg-card p-6 flex flex-col gap-5">
		<div class="flex items-start gap-3 mb-2">
			<div class="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
				<Cpu class="h-4 w-4" />
			</div>
			<div>
				<h3 class="text-sm font-semibold text-foreground">Agent LLM</h3>
				<p class="text-xs text-muted-foreground mt-0.5">Configure the default language model for all agents</p>
			</div>
		</div>

		<div class="flex flex-col gap-4">
			<div class="flex flex-col gap-1.5">
				<label class={labelClass} for="cfg-model">Model</label>
				<div class="relative">
					<Bot class={iconClass} />
					<input id="cfg-model" type="text" bind:value={agentModel} placeholder="openai/gpt-4o" class={inputClass} />
				</div>
			</div>
			<div class="flex flex-col gap-1.5">
				<label class={labelClass} for="cfg-api-base">API Base</label>
				<div class="relative">
					<Link class={iconClass} />
					<input id="cfg-api-base" type="text" bind:value={agentApiBase} placeholder="https://openrouter.ai/api/v1" class={inputClass} />
				</div>
			</div>
			<div class="flex flex-col gap-1.5">
				<label class={labelClass} for="cfg-api-key">API Key</label>
				<div class="relative">
					<KeyRound class={iconClass} />
					<input id="cfg-api-key" type="password" bind:value={agentApiKey} placeholder="sk-…" class={inputClass} />
				</div>
			</div>
			<div class="grid grid-cols-2 gap-4">
				<div class="flex flex-col gap-1.5">
					<label class={labelClass} for="cfg-temp">Temperature</label>
					<div class="relative">
						<Thermometer class={iconClass} />
						<input id="cfg-temp" type="number" min="0" max="2" step="0.05" bind:value={agentTemperature} class={inputClass} />
					</div>
				</div>
				<div class="flex flex-col gap-1.5">
					<label class={labelClass} for="cfg-maxtok">Max Tokens</label>
					<div class="relative">
						<Hash class={iconClass} />
						<input id="cfg-maxtok" type="number" bind:value={agentMaxTokens} placeholder="(none)" class={inputClass} />
					</div>
				</div>
			</div>
			<div class="grid grid-cols-2 gap-4">
				<div class="flex flex-col gap-1.5">
					<label class={labelClass} for="cfg-maxiter">Max Iterations</label>
					<div class="relative">
						<RefreshCw class={iconClass} />
						<input id="cfg-maxiter" type="number" bind:value={agentMaxIterations} class={inputClass} />
					</div>
				</div>
				<div class="flex flex-col gap-1.5">
					<label class={labelClass} for="cfg-ctx">Context Window</label>
					<div class="relative">
						<ScanText class={iconClass} />
						<input id="cfg-ctx" type="number" bind:value={agentContextWindow} class={inputClass} />
					</div>
				</div>
			</div>
		</div>
	</div>

	<!-- Router -->
	<div class="rounded-xl border bg-card p-6 flex flex-col gap-5">
		<div class="flex items-start gap-3 mb-2">
			<div class="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
				<GitFork class="h-4 w-4" />
			</div>
			<div>
				<h3 class="text-sm font-semibold text-foreground">Router</h3>
				<p class="text-xs text-muted-foreground mt-0.5">Route messages to specialist agents automatically</p>
			</div>
		</div>

		<div class="flex flex-col gap-4">
			<div class="flex items-center justify-between rounded-lg border bg-background px-4 py-3">
				<div class="flex items-center gap-3">
					<GitFork class="h-4 w-4 text-muted-foreground" />
					<div>
						<p class="text-sm font-medium">Enabled</p>
						<p class="text-xs text-muted-foreground">Route messages to specialist agents</p>
					</div>
				</div>
				<input type="checkbox" bind:checked={routerEnabled} class="h-4 w-4 rounded border cursor-pointer accent-primary" />
			</div>

			<div class="grid grid-cols-2 gap-4">
				<div class="flex flex-col gap-1.5">
					<label class={labelClass} for="cfg-rdefault">Default Agent</label>
					<div class="relative">
						<Bot class={iconClass} />
						<input id="cfg-rdefault" type="text" bind:value={routerDefault} placeholder="general" class={inputClass} />
					</div>
				</div>
				<div class="flex flex-col gap-1.5">
					<label class={labelClass} for="cfg-ragents">Agents (comma-separated)</label>
					<div class="relative">
						<Users class={iconClass} />
						<input id="cfg-ragents" type="text" bind:value={routerAgents} placeholder="general, code, research" class={inputClass} />
					</div>
				</div>
			</div>

			<div class="rounded-lg border bg-muted/30 px-4 py-3">
				<p class="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-3">Router LLM</p>
				<div class="grid grid-cols-2 gap-4">
					<div class="flex flex-col gap-1.5">
						<label class={labelClass} for="cfg-rtemp">Temperature</label>
						<div class="relative">
							<Thermometer class={iconClass} />
							<input id="cfg-rtemp" type="number" min="0" max="2" step="0.05" bind:value={routerTemperature} class={inputClass} />
						</div>
					</div>
					<div class="flex flex-col gap-1.5">
						<label class={labelClass} for="cfg-rmaxtok">Max Tokens</label>
						<div class="relative">
							<Hash class={iconClass} />
							<input id="cfg-rmaxtok" type="number" bind:value={routerMaxTokens} placeholder="(none)" class={inputClass} />
						</div>
					</div>
				</div>
			</div>
		</div>
	</div>

	<!-- Memory -->
	<div class="rounded-xl border bg-card p-6 flex flex-col gap-5">
		<div class="flex items-start gap-3 mb-2">
			<div class="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
				<Database class="h-4 w-4" />
			</div>
			<div>
				<h3 class="text-sm font-semibold text-foreground">Memory</h3>
				<p class="text-xs text-muted-foreground mt-0.5">Persistent memory storage configuration</p>
			</div>
		</div>

		<div class="flex flex-col gap-4">
			<div class="flex flex-col gap-1.5">
				<label class={labelClass} for="cfg-dbpath">DB Path</label>
				<div class="relative">
					<HardDrive class={iconClass} />
					<input id="cfg-dbpath" type="text" bind:value={memoryDbPath} placeholder="~/.emo/memory.db" class={inputClass} />
				</div>
			</div>
			<div class="grid grid-cols-2 gap-4">
				<div class="flex flex-col gap-1.5">
					<label class={labelClass} for="cfg-maxfacts">Max Facts</label>
					<div class="relative">
						<Hash class={iconClass} />
						<input id="cfg-maxfacts" type="number" bind:value={memoryMaxFacts} class={inputClass} />
					</div>
				</div>
				<div class="flex flex-col gap-1.5">
					<label class={labelClass} for="cfg-sumafter">Summarize After</label>
					<div class="relative">
						<Hash class={iconClass} />
						<input id="cfg-sumafter" type="number" bind:value={memorySummarizeAfter} class={inputClass} />
					</div>
				</div>
			</div>
		</div>
	</div>

	<!-- Features -->
	<div class="rounded-xl border bg-card p-6 flex flex-col gap-5">
		<div class="flex items-start gap-3 mb-2">
			<div class="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
				<Sparkles class="h-4 w-4" />
			</div>
			<div>
				<h3 class="text-sm font-semibold text-foreground">Features</h3>
				<p class="text-xs text-muted-foreground mt-0.5">Enable or disable optional capabilities</p>
			</div>
		</div>

		<div class="flex flex-col gap-3">
			<div class="flex items-center justify-between rounded-lg border bg-background px-4 py-3">
				<div class="flex items-center gap-3">
					<GitFork class="h-4 w-4 text-muted-foreground" />
					<div>
						<p class="text-sm font-medium">Routing</p>
						<p class="text-xs text-muted-foreground">Route messages to specialist agents</p>
					</div>
				</div>
				<input type="checkbox" bind:checked={featRouting} class="h-4 w-4 rounded border cursor-pointer accent-primary" />
			</div>

			<div class="flex items-center justify-between rounded-lg border bg-background px-4 py-3">
				<div class="flex items-center gap-3">
					<BrainCircuit class="h-4 w-4 text-muted-foreground" />
					<div>
						<p class="text-sm font-medium">Memory</p>
						<p class="text-xs text-muted-foreground">Persist facts across sessions</p>
					</div>
				</div>
				<input type="checkbox" bind:checked={featMemory} class="h-4 w-4 rounded border cursor-pointer accent-primary" />
			</div>

			<div class="flex items-center justify-between rounded-lg border bg-background px-4 py-3">
				<div class="flex items-center gap-3">
					<Globe class="h-4 w-4 text-muted-foreground" />
					<div>
						<p class="text-sm font-medium">Web</p>
						<p class="text-xs text-muted-foreground">Enable web search tool</p>
					</div>
				</div>
				<input type="checkbox" bind:checked={featWeb} class="h-4 w-4 rounded border cursor-pointer accent-primary" />
			</div>
		</div>
	</div>

	<!-- Save -->
	<div class="flex items-center gap-3 pt-2">
		<button
			onclick={save}
			class="rounded-md bg-primary px-6 py-2 text-sm font-medium text-primary-foreground hover:opacity-90 transition-opacity"
		>
			{saved ? '✓ Saved' : 'Save changes'}
		</button>
		{#if saved}<p class="text-xs text-muted-foreground">Changes saved</p>{/if}
	</div>
</div>
