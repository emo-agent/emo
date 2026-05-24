<script lang="ts">
	import type { StoredMessage } from '$lib/daemon/protocol';
	import {
		Message,
		MessageContent,
		MessageResponse
	} from '$lib/components/ai-elements/message/index';

	interface Props {
		message: StoredMessage;
	}

	let { message }: Props = $props();

	function formatTime(ts: number): string {
		return new Date(ts * 1000).toLocaleTimeString(undefined, {
			hour: '2-digit',
			minute: '2-digit'
		});
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
		{formatTime(message.created_at)}
	</span>
</Message>
