<script lang="ts">
	import { daemon } from '$lib/daemon/store.svelte';
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
				daemon.sendMessage(message.text);
			}
		}}
		class="shadow-md"
	>
		<PromptInputBody>
			<PromptInputTextarea placeholder="Message emo…" />
		</PromptInputBody>
		<PromptInputToolbar>
			<div></div>
			<PromptInputSubmit status={daemon.isLoading ? 'submitted' : 'ready'} />
		</PromptInputToolbar>
	</PromptInput>
</div>
