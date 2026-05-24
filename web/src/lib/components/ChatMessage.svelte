<script lang="ts">
	import type { ChatMessage } from '$lib/stores/chat.svelte';
	import {
		Message,
		MessageContent,
		MessageResponse
	} from '$lib/components/ai-elements/message/index';

	interface Props {
		message: ChatMessage;
	}

	let { message }: Props = $props();

	function formatTime(date: Date): string {
		return date.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' });
	}
</script>

<Message from={message.role === 'user' ? 'user' : 'assistant'}>
	<MessageContent>
		{#if message.role === 'assistant'}
			<MessageResponse content={message.content} />
		{:else}
			{message.content}
		{/if}
	</MessageContent>
	<span class="text-muted-foreground px-1 text-xs">
		{formatTime(message.createdAt)}
	</span>
</Message>
