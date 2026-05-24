<script lang="ts">
	import { chat } from '$lib/stores/chat.svelte';
	import {
		PromptInput,
		PromptInputBody,
		PromptInputTextarea,
		PromptInputToolbar,
		PromptInputSubmit
	} from '$lib/components/ai-elements/prompt-input/index';
	import type { Message } from '$lib/components/ai-elements/prompt-input/index';
</script>

<div class="border-t px-4 py-3">
	<PromptInput
		onSubmit={(message: Message) => {
			if (message.text.trim()) {
				chat.sendMessage(message.text);
			}
		}}
		class="shadow-md"
	>
		<PromptInputBody>
			<PromptInputTextarea
				placeholder="Message emo…"
			/>
		</PromptInputBody>
		<PromptInputToolbar>
			<div></div>
			<PromptInputSubmit
				status={chat.isLoading ? 'submitted' : 'ready'}
			/>
		</PromptInputToolbar>
	</PromptInput>
</div>
