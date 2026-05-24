<script lang="ts">
	import { X } from '@lucide/svelte';
	import { badgeVariants } from '$lib/components/ui/badge/index.js';
	import { cn } from '$lib/utils.js';

	let {
		values = $bindable<string[]>([]),
		suggestions = [] as string[],
		placeholder = 'Add…',
		singleValue = false,
		id = ''
	}: {
		values: string[];
		suggestions: string[];
		placeholder?: string;
		singleValue?: boolean;
		id?: string;
	} = $props();

	let inputValue = $state('');
	let focused = $state(false);
	let inputEl = $state<HTMLInputElement | null>(null);

	const available = $derived(
		suggestions.filter(
			(s) =>
				!values.includes(s) &&
				(inputValue === '' || s.toLowerCase().includes(inputValue.toLowerCase()))
		)
	);

	const showInput = $derived(!singleValue || values.length === 0);

	function addValue(val: string) {
		if (!val || values.includes(val)) return;
		values = singleValue ? [val] : [...values, val];
		inputValue = '';
		// keep focus on input so dropdown stays open
		inputEl?.focus();
	}

	function removeValue(val: string) {
		values = values.filter((v) => v !== val);
		inputEl?.focus();
	}

	function onKeydown(e: KeyboardEvent) {
		if (e.key === 'Backspace' && inputValue === '' && values.length > 0) {
			values = values.slice(0, -1);
		} else if (e.key === 'Enter' && inputValue.trim()) {
			e.preventDefault();
			addValue(inputValue.trim());
		} else if (e.key === 'Escape') {
			inputEl?.blur();
		}
	}
</script>

<div class="flex flex-col gap-0.5">
	<!-- Selected chips + text input -->
	<!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
	<div
		role="group"
		class="flex min-h-9 flex-wrap items-center gap-1.5 rounded-md border border-input bg-background px-2.5 py-1 cursor-text"
		onkeydown={() => {}}
		onclick={() => inputEl?.focus()}
	>
		{#each values as value (value)}
			<span class={cn(badgeVariants({ variant: 'secondary' }), 'gap-1.5 pr-1 h-6')}>
				{value}
				<button
					type="button"
					onmousedown={(e) => { e.preventDefault(); removeValue(value); }}
					aria-label="Remove {value}"
					class="flex items-center justify-center w-3.5 h-3.5 rounded-full bg-muted-foreground/20 text-muted-foreground hover:bg-destructive hover:text-white transition-colors cursor-pointer"
				>
					<X size={8} strokeWidth={2.5} />
				</button>
			</span>
		{/each}

		{#if showInput}
			<input
				{id}
				bind:this={inputEl}
				bind:value={inputValue}
				placeholder={values.length === 0 ? placeholder : ''}
				class="flex-1 min-w-16 bg-transparent text-sm outline-none ring-0 border-0 shadow-none placeholder:text-muted-foreground py-0 focus:outline-none focus:ring-0 focus:border-0"
				onkeydown={onKeydown}
				onfocus={() => (focused = true)}
				onblur={() => (focused = false)}
				autocomplete="off"
				spellcheck="false"
			/>
		{/if}
	</div>

	<!-- Dropdown: visible while input is focused and there are options -->
	{#if focused && available.length > 0}
		<div class="rounded-md border bg-popover py-0.5 shadow-sm">
			{#each available as suggestion (suggestion)}
				<button
					type="button"
					onmousedown={(e) => { e.preventDefault(); addValue(suggestion); }}
					class="w-full px-2.5 py-1 text-left text-xs text-muted-foreground cursor-pointer hover:bg-accent hover:text-accent-foreground transition-colors"
				>
					{suggestion}
				</button>
			{/each}
		</div>
	{/if}
</div>
