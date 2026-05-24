<script lang="ts">
	import type { StoredMessage } from '$lib/daemon/protocol';
	import { MessageResponse } from '$lib/components/ai-elements/message/index';
	import AgentActionBlock from '$lib/components/AgentActionBlock.svelte';
	import ToolCallBlock from '$lib/components/ToolCallBlock.svelte';
	import MessageStats from '$lib/components/MessageStats.svelte';
	import { User, Bot, Copy, Check, ChevronDown, ChevronUp, Terminal } from '@lucide/svelte';

	interface Props {
		message: StoredMessage;
	}

	let { message }: Props = $props();

	const isUser = $derived(message.role === 'user');
	const isAssistant = $derived(message.role === 'assistant');
	const isSystem = $derived(message.role === 'system');

	// Intermediary actions
	const hasActions = $derived(
		(message.agent_actions?.length ?? 0) > 0 || (message.tool_calls?.length ?? 0) > 0
	);
	const totalActions = $derived(
		(message.agent_actions?.length ?? 0) + (message.tool_calls?.length ?? 0)
	);
	let actionsExpanded = $state(false);

	// Copy button state
	let copied = $state(false);
	async function copyContent() {
		await navigator.clipboard.writeText(message.content);
		copied = true;
		setTimeout(() => {
			copied = false;
		}, 1500);
	}

	// Streaming indicator: content is empty string
	const isStreaming = $derived(isAssistant && message.content === '');

	function formatTime(ts: number): string {
		return new Date(ts * 1000).toLocaleTimeString(undefined, {
			hour: '2-digit',
			minute: '2-digit'
		});
	}
</script>

<div class="flex w-full gap-3 {isUser ? 'flex-row-reverse' : 'flex-row'} items-start">
	{#if isSystem}
		<!-- System / command output -->
		<div class="flex w-fit max-w-[95%] items-start gap-2.5">
			<div class="mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-md bg-muted text-muted-foreground/70">
				<Terminal size={13} />
			</div>
			<div class="min-w-0 flex-1 rounded-lg bg-muted/40 px-3.5 py-2.5 text-sm text-muted-foreground
				[&_p]:my-1 [&_p:first-child]:mt-0 [&_p:last-child]:mb-0
				[&_table]:w-full [&_table]:text-xs [&_th]:text-left [&_th]:font-medium [&_th]:py-1 [&_td]:py-0.5
				[&_ul]:my-1 [&_ul]:pl-4 [&_li]:my-0.5
				[&_code]:rounded [&_code]:bg-muted [&_code]:px-1 [&_code]:py-0.5 [&_code]:text-xs [&_code]:font-mono [&_code]:text-foreground">
				<MessageResponse content={message.content} />
			</div>
		</div>
	{:else}
	<!-- Avatar -->
	<div
		class="mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-full
		{isUser ? 'bg-primary/10' : 'bg-muted'}"
	>
		{#if isUser}
			<User size={18} class="text-primary" />
		{:else}
			<Bot size={18} class="text-muted-foreground" />
		{/if}
	</div>

	<!-- Content column -->
	<div class="flex min-w-0 max-w-[95%] flex-col gap-1 {isUser ? 'items-end' : 'items-start'}">
		<!-- Intermediary actions (assistant only) -->
		{#if isAssistant && hasActions}
			<div class="w-fit max-w-full">
				<button
					type="button"
					class="mb-1 flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
					onclick={() => (actionsExpanded = !actionsExpanded)}
				>
					{#if actionsExpanded}
						<ChevronUp size={12} />
					{:else}
						<ChevronDown size={12} />
					{/if}
					<span>{totalActions} {totalActions === 1 ? 'action' : 'actions'}</span>
				</button>
				{#if actionsExpanded}
					<div class="flex flex-col gap-1.5">
						{#each message.agent_actions ?? [] as action (action.id)}
							<AgentActionBlock {action} />
						{/each}
						{#each message.tool_calls ?? [] as toolCall (toolCall.id)}
							<ToolCallBlock {toolCall} />
						{/each}
					</div>
				{/if}
			</div>
		{/if}

		<!-- Message bubble / content -->
		{#if isUser}
			<div class="w-fit rounded-2xl bg-muted px-4 py-2.5 text-sm">
				{message.content}
			</div>
		{:else}
		<div class="w-fit text-sm">
			{#if isStreaming}
					<!-- Pulsing streaming indicator -->
					<div class="flex items-center gap-1 py-1">
						<span class="size-1.5 animate-bounce rounded-full bg-muted-foreground/60 [animation-delay:0ms]"></span>
						<span class="size-1.5 animate-bounce rounded-full bg-muted-foreground/60 [animation-delay:150ms]"></span>
						<span class="size-1.5 animate-bounce rounded-full bg-muted-foreground/60 [animation-delay:300ms]"></span>
					</div>
				{:else}
					<MessageResponse content={message.content} />
				{/if}
			</div>
		{/if}

		<!-- Footer row (assistant only) -->
		{#if isAssistant}
			<div class="flex w-fit items-center justify-between gap-4 pt-0.5">
				<!-- Timestamp -->
				<span class="text-xs text-muted-foreground">
					{formatTime(message.created_at)}
				</span>
				<!-- Action buttons -->
				<div class="flex items-center gap-1">
					{#if message.stats}
						<MessageStats stats={message.stats} />
					{/if}
					<button
						type="button"
						class="inline-flex items-center justify-center rounded p-1 text-muted-foreground transition-colors hover:text-foreground"
						onclick={copyContent}
						aria-label="Copy message"
					>
						{#if copied}
							<Check size={14} />
						{:else}
							<Copy size={14} />
						{/if}
					</button>
				</div>
			</div>
		{:else}
			<!-- Timestamp for user messages -->
			<span class="text-xs text-muted-foreground">
				{formatTime(message.created_at)}
			</span>
		{/if}
	</div>
	{/if}
</div>
