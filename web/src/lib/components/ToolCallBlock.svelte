<script lang="ts">
	import type { ToolCall } from '$lib/daemon/protocol';
	import { Wrench, ChevronDown, ChevronUp } from '@lucide/svelte';

	interface Props {
		toolCall: ToolCall;
	}

	let { toolCall }: Props = $props();
	let expanded = $state(false);

	const preview = $derived(
		toolCall.preview.length > 60 ? toolCall.preview.slice(0, 60) + '…' : toolCall.preview
	);
</script>

<div class="rounded-md border border-border bg-muted/50 text-xs">
	<!-- Header row (always visible) -->
	<button
		type="button"
		class="flex w-full items-center gap-2 px-3 py-2 text-left"
		onclick={() => (expanded = !expanded)}
	>
		<Wrench size={14} class="shrink-0 text-muted-foreground" />
		<span class="font-medium text-foreground">{toolCall.name}</span>
		<span class="flex-1 truncate text-muted-foreground">{preview}</span>
		{#if expanded}
			<ChevronUp size={14} class="shrink-0 text-muted-foreground" />
		{:else}
			<ChevronDown size={14} class="shrink-0 text-muted-foreground" />
		{/if}
	</button>

	<!-- Expanded content -->
	{#if expanded}
		<div class="space-y-2 border-t border-border px-3 py-2">
			<p class="text-muted-foreground">{toolCall.preview}</p>

			{#if toolCall.input}
				<div>
					<p class="mb-1 text-[10px] font-medium tracking-wide text-foreground/70 uppercase">
						Input
					</p>
					<pre
						class="overflow-x-auto rounded bg-background/60 p-2 font-mono text-[11px] break-all whitespace-pre-wrap">{JSON.stringify(
							toolCall.input,
							null,
							2
						)}</pre>
				</div>
			{/if}

			{#if toolCall.output}
				<div>
					<p class="mb-1 text-[10px] font-medium tracking-wide text-foreground/70 uppercase">
						Output
					</p>
					<pre
						class="overflow-x-auto rounded bg-background/60 p-2 font-mono text-[11px] break-all whitespace-pre-wrap">{toolCall.output}</pre>
				</div>
			{/if}
		</div>
	{/if}
</div>
