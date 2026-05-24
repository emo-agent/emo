<script lang="ts">
	import { daemon } from '$lib/daemon/store.svelte';
	import * as Dialog from '$lib/components/ui/dialog';
	import { Button } from '$lib/components/ui/button';
	import { Input } from '$lib/components/ui/input';

	let pin = $state('');
	let error = $state('');
	let inputEl = $state<HTMLInputElement | null>(null);

	function handleSubmit() {
		if (!pin.trim()) {
			error = 'Please enter the 6-digit PIN.';
			return;
		}
		daemon.submitPin(pin);
		pin = '';
		error = '';
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Enter') handleSubmit();
	}
</script>

<Dialog.Root open={daemon.pairingState === 'challenge'}>
	<Dialog.Content showCloseButton={false}>
		<Dialog.Header>
			<Dialog.Title>Pair with emo daemon</Dialog.Title>
			<Dialog.Description>
				Enter the 6-digit PIN displayed in the daemon terminal.
			</Dialog.Description>
		</Dialog.Header>
		<div class="flex flex-col gap-3 pt-1">
			<Input
				bind:ref={inputEl}
				type="text"
				inputmode="numeric"
				maxlength={6}
				pattern="[0-9]*"
				placeholder="000000"
				bind:value={pin}
				onkeydown={handleKeydown}
				autofocus
				class="text-center text-lg tracking-widest"
			/>
			{#if error}
				<p class="text-sm text-destructive">{error}</p>
			{/if}
		</div>
		<Dialog.Footer>
			<Button onclick={handleSubmit} class="w-full">Pair</Button>
		</Dialog.Footer>
	</Dialog.Content>
</Dialog.Root>
