<script lang="ts">
	import { daemon } from '$lib/daemon/store.svelte';
	import { Plus, ArrowUp, Mic } from '@lucide/svelte';

	const COMMANDS = [
		'/help',
		'/new',
		'/model',
		'/agent',
		'/auto',
		'/memory',
		'/remember',
		'/forget',
		'/skills',
		'/agents',
		'/status',
		'/exit'
	];

	type CompletionType = '@' | '/';

	let draft = $state('');
	let textareaEl = $state<HTMLTextAreaElement | null>(null);

	let showAutocomplete = $state(false);
	let autocompleteItems = $state<string[]>([]);
	let selectedIndex = $state(0);
	let completionType = $state<CompletionType>('@');

	// Position of the dropdown (fixed, computed from textarea rect)
	let dropdownTop = $state(0);
	let dropdownLeft = $state(0);
	let dropdownWidth = $state(0);

	// ── Helpers ───────────────────────────────────────────────────────────────

	function resize() {
		if (!textareaEl) return;
		textareaEl.style.height = '48px';
		textareaEl.style.height = `${Math.min(textareaEl.scrollHeight, 180)}px`;
	}

	function getCursorPosition(): number {
		return textareaEl?.selectionStart ?? draft.length;
	}

	function getWordAtCursor(): { word: string; start: number } | null {
		const text = draft.slice(0, getCursorPosition());
		const cursor = text.length;
		let start = cursor;

		for (let i = cursor - 1; i >= 0; i--) {
			const char = text[i];
			if (char === ' ' || char === '\n') break;
			start = i;
		}

		return { word: text.slice(start, cursor), start };
	}

	function updateDropdownRect() {
		if (!textareaEl) return;
		const rect = textareaEl.getBoundingClientRect();
		// Place dropdown just above the input bar
		dropdownTop = rect.top - 8;
		dropdownLeft = rect.left;
		dropdownWidth = rect.width;
	}

	// ── Autocomplete logic ────────────────────────────────────────────────────

	function updateAutocomplete() {
		const wordInfo = getWordAtCursor();
		if (!wordInfo) {
			hideAutocomplete();
			return;
		}

		const { word } = wordInfo;

		if (word.startsWith('@')) {
			completionType = '@';
			const partial = word.slice(1).toLowerCase();
			const agents =
				daemon.agents.length > 0
					? daemon.agents.map((a) => a.name)
					: ['general', 'code', 'research'];
			autocompleteItems = partial
				? agents.filter((a) => a.toLowerCase().startsWith(partial))
				: agents;
			selectedIndex = 0;
			if (autocompleteItems.length > 0) {
				updateDropdownRect();
				showAutocomplete = true;
			} else {
				showAutocomplete = false;
			}
		} else if (word.startsWith('/')) {
			completionType = '/';
			const partial = word.slice(1).toLowerCase();
			autocompleteItems = COMMANDS.filter((c) => c.slice(1).toLowerCase().startsWith(partial));
			selectedIndex = 0;
			if (autocompleteItems.length > 0) {
				updateDropdownRect();
				showAutocomplete = true;
			} else {
				showAutocomplete = false;
			}
		} else {
			hideAutocomplete();
		}
	}

	function hideAutocomplete() {
		showAutocomplete = false;
		autocompleteItems = [];
		selectedIndex = 0;
	}

	function insertCompletion(value: string) {
		if (!textareaEl) return;

		const cursor = getCursorPosition();
		const textBefore = draft.slice(0, cursor);
		const textAfter = draft.slice(cursor);

		let wordStart = cursor;
		for (let i = cursor - 1; i >= 0; i--) {
			if (textBefore[i] === ' ' || textBefore[i] === '\n') break;
			wordStart = i;
		}

		const completion = completionType === '@' ? `@${value} ` : `${value} `;
		draft = textBefore.slice(0, wordStart) + completion + textAfter;

		hideAutocomplete();

		setTimeout(() => {
			if (textareaEl) {
				const newPos = wordStart + completion.length;
				textareaEl.setSelectionRange(newPos, newPos);
				textareaEl.focus();
			}
		}, 0);
	}

	// ── Command handler ───────────────────────────────────────────────────────

	/** Returns true if the text was a /command and was handled locally. */
	function handleCommand(text: string): boolean {
		if (!text.startsWith('/')) return false;

		const parts = text.trim().split(/\s+/);
		const name = parts[0].toLowerCase();

		// Ensure there's an active session to post into; create one if needed
		function ensureSession() {
			if (!daemon.activeSessionId) daemon.newSession();
		}

		switch (name) {
			case '/help': {
				ensureSession();
				daemon.postSystemMessage(
					`**Available commands**

| Command | Description |
|---|---|
| \`/help\` | Show this help |
| \`/new\` | Start a new session |
| \`/model [name]\` | Show or switch model |
| \`/agent [name]\` | Force a specific agent |
| \`/auto\` | Return to automatic agent routing |
| \`/agents\` | List available agents |
| \`/skills\` | List loaded skills |
| \`/status\` | Show session stats |`
				);
				return true;
			}

			case '/new': {
				daemon.newSession();
				return true;
			}

			case '/model': {
				ensureSession();
				if (parts.length < 2) {
					const model = (daemon.configData?.agent as Record<string, unknown> | undefined)?.llm as
						| Record<string, unknown>
						| undefined;
					const name = model?.model ?? 'unknown';
					daemon.postSystemMessage(`Current model: \`${name}\``);
				} else {
					daemon.postSystemMessage(
						`⚠️ Model switching via UI is not yet supported. Edit your config in Settings → Config.`
					);
				}
				return true;
			}

			case '/agent': {
				ensureSession();
				if (parts.length < 2) {
					const current = daemon.forcedAgent ?? 'auto (supervisor routing)';
					daemon.postSystemMessage(`Current agent: \`${current}\``);
				} else {
					const agentName = parts[1].toLowerCase();
					const known = daemon.agents.map((a) => a.name);
					if (known.length > 0 && !known.includes(agentName)) {
						daemon.postSystemMessage(
							`Unknown agent \`${agentName}\`. Available: ${known.map((n) => `\`${n}\``).join(', ')}`
						);
					} else {
						daemon.setForcedAgent(agentName);
						daemon.postSystemMessage(`Agent forced to: \`${agentName}\``);
					}
				}
				return true;
			}

			case '/auto': {
				ensureSession();
				daemon.setForcedAgent(null);
				daemon.postSystemMessage('Automatic supervisor routing enabled.');
				return true;
			}

			case '/agents': {
				ensureSession();
				if (daemon.agents.length === 0) {
					daemon.postSystemMessage('No agents registered.');
				} else {
					const current = daemon.forcedAgent ?? null;
					const lines = daemon.agents.map((a) => {
						const marker = a.name === current ? ' ← active' : '';
						return `- **${a.name}**${marker} *(${a.source})*`;
					});
					daemon.postSystemMessage(`**Available agents**\n\n${lines.join('\n')}`);
				}
				return true;
			}

			case '/skills': {
				ensureSession();
				if (daemon.skills.length === 0) {
					daemon.postSystemMessage('No skills loaded.');
				} else {
					const lines = daemon.skills.map((s) => `- **${s.name}** — ${s.summary}`);
					daemon.postSystemMessage(`**Loaded skills**\n\n${lines.join('\n')}`);
				}
				return true;
			}

			case '/status': {
				ensureSession();
				const session = daemon.activeSession;
				if (!session) {
					daemon.postSystemMessage('No active session.');
				} else {
					const msgCount = session.messages.filter((m) => m.role !== 'system').length;
					const created = new Date(session.created_at * 1000).toLocaleString();
					const updated = new Date(session.updated_at * 1000).toLocaleString();
					daemon.postSystemMessage(
						`**Session status**\n\n- **ID**: \`${session.id}\`\n- **Title**: ${session.title}\n- **Messages**: ${msgCount}\n- **Created**: ${created}\n- **Updated**: ${updated}`
					);
				}
				return true;
			}

			default:
				// Unknown /command — show error rather than sending to LLM
				ensureSession();
				daemon.postSystemMessage(
					`Unknown command \`${name}\`. Type \`/help\` to see available commands.`
				);
				return true;
		}
	}

	// ── Submit ────────────────────────────────────────────────────────────────

	function submit() {
		const text = draft.trim();
		if (!text || daemon.connectionState !== 'connected') return;

		// Intercept /commands — handle locally, no LLM call
		if (handleCommand(text)) {
			draft = '';
			hideAutocomplete();
			if (textareaEl) textareaEl.style.height = '48px';
			return;
		}

		let agent: string | undefined;
		let content = text;

		if (text.startsWith('@')) {
			const parts = text.split(/\s+/);
			const mention = parts[0].slice(1).toLowerCase();
			const agentExists = daemon.agents.some((a) => a.name.toLowerCase() === mention);
			if (agentExists) {
				agent = mention;
				content = parts.slice(1).join(' ');
			}
		}

		if (!content.trim()) return;

		daemon.sendMessage(content, agent);
		draft = '';
		hideAutocomplete();
		if (textareaEl) textareaEl.style.height = '48px';
	}

	// ── Keyboard handler ──────────────────────────────────────────────────────

	function onKeydown(event: KeyboardEvent) {
		if (showAutocomplete) {
			if (event.key === 'ArrowDown') {
				event.preventDefault();
				selectedIndex = (selectedIndex + 1) % autocompleteItems.length;
				return;
			}
			if (event.key === 'ArrowUp') {
				event.preventDefault();
				selectedIndex = (selectedIndex - 1 + autocompleteItems.length) % autocompleteItems.length;
				return;
			}
			if (event.key === 'Enter' || event.key === 'Tab') {
				event.preventDefault();
				insertCompletion(autocompleteItems[selectedIndex]);
				return;
			}
			if (event.key === 'Escape') {
				event.preventDefault();
				hideAutocomplete();
				return;
			}
		}

		if (event.key === 'Enter' && !event.shiftKey) {
			event.preventDefault();
			submit();
		}
	}

	function onInput() {
		resize();
		updateAutocomplete();
	}
</script>

<!-- Dropdown rendered at fixed position so it's never clipped -->
{#if showAutocomplete && autocompleteItems.length > 0}
	<!-- svelte-ignore a11y_no_static_element_interactions -->
	<div
		class="fixed z-[9999] min-w-40 overflow-hidden rounded-lg border bg-popover py-1 shadow-lg"
		style="bottom: {window.innerHeight -
			dropdownTop}px; left: {dropdownLeft}px; width: {dropdownWidth}px;"
		onmousedown={(e) => e.preventDefault()}
	>
		<p
			class="px-2 pt-0.5 pb-1 text-[10px] font-medium tracking-wide text-muted-foreground uppercase"
		>
			{completionType === '@' ? 'Agents' : 'Commands'}
		</p>
		{#each autocompleteItems as item, i (item)}
			<button
				type="button"
				class="w-full px-3 py-1.5 text-left text-sm transition-colors
					{i === selectedIndex
					? 'bg-accent text-accent-foreground'
					: 'text-popover-foreground hover:bg-accent/60'}"
				onmousedown={(e) => {
					e.preventDefault();
					insertCompletion(item);
				}}
				onmouseenter={() => {
					selectedIndex = i;
				}}
			>
				{item}
			</button>
		{/each}
	</div>
{/if}

<div class="w-full px-4 pt-2 pb-4">
	<div class="mx-auto">
		<div
			class="flex min-h-12 items-center gap-3 rounded-4xl border bg-background px-2 py-0 shadow-[0_4px_18px_rgba(0,0,0,0.06)]"
		>
			<button
				type="button"
				class="flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
				disabled={daemon.connectionState !== 'connected'}
				aria-label="Add attachment"
			>
				<Plus class="h-5 w-5" />
			</button>

			<textarea
				bind:this={textareaEl}
				bind:value={draft}
				oninput={onInput}
				onkeydown={onKeydown}
				onblur={() => setTimeout(hideAutocomplete, 150)}
				placeholder="Ask anything"
				rows={1}
				disabled={daemon.connectionState !== 'connected'}
				class="max-h-44 min-h-11 flex-1 resize-none border-0 bg-transparent px-0 py-3 text-[15px] leading-6 text-foreground placeholder:text-muted-foreground/70 focus:ring-0 focus:outline-none"
			></textarea>

			<button
				type="button"
				class="flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-foreground transition-colors hover:bg-muted"
				aria-label="Voice input"
			>
				<Mic class="h-5 w-5" />
			</button>

			<button
				type="button"
				onclick={submit}
				disabled={daemon.connectionState !== 'connected' || !draft.trim()}
				class="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-foreground text-background transition-colors hover:opacity-90 disabled:cursor-not-allowed disabled:bg-muted disabled:text-muted-foreground"
				aria-label="Send message"
			>
				<ArrowUp class="h-5 w-5" />
			</button>
		</div>
	</div>
</div>
