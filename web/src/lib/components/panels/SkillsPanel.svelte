<script lang="ts">
	import { daemon } from '$lib/daemon/store.svelte';
	import { FileText, ChevronLeft, Trash2, Tag } from '@lucide/svelte';

	let selectedSkill = $state<string | null>(null);
	let editorValue = $state('');
	let isNew = $state(false);
	let newName = $state('');
	let saveMsg = $state('');

	$effect(() => {
		const sk = daemon.activeSkillContent;
		if (sk) {
			editorValue = sk.content;
		}
	});

	function selectSkill(name: string) {
		selectedSkill = name;
		isNew = false;
		daemon.fetchSkill(name);
	}

	function startNew() {
		isNew = true;
		selectedSkill = null;
		newName = '';
		editorValue = '# Skill name\n\nDescribe the skill here.';
	}

	function save() {
		const name = isNew ? newName.trim() : selectedSkill;
		if (!name) return;
		daemon.saveSkill(name, editorValue);
		saveMsg = '✓ Saved';
		if (isNew) {
			isNew = false;
			selectedSkill = name;
			daemon.fetchSkills();
		}
		setTimeout(() => (saveMsg = ''), 2000);
	}

	function deleteSkill(name: string) {
		if (!confirm(`Delete skill "${name}"?`)) return;
		daemon.deleteSkill(name);
		selectedSkill = null;
		editorValue = '';
	}

	const labelClass = 'text-xs font-medium text-muted-foreground';
</script>

{#if isNew || selectedSkill}
	<!-- Detail view -->
	<div class="mx-auto flex max-w-2xl flex-col gap-8 px-6 py-8">
		<!-- Breadcrumb + name -->
		<div>
			<button
				onclick={() => {
					selectedSkill = null;
					isNew = false;
				}}
				class="mb-2 flex items-center gap-1.5 text-xs text-muted-foreground transition-colors hover:text-foreground"
			>
				<ChevronLeft class="h-3.5 w-3.5" /> All Skills
			</button>
			{#if isNew}
				<div class="flex flex-col gap-1.5">
					<label class={labelClass} for="skill-name">Skill Name</label>
					<div class="relative">
						<Tag
							class="pointer-events-none absolute top-1/2 left-3 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground"
						/>
						<input
							id="skill-name"
							type="text"
							bind:value={newName}
							placeholder="my-skill"
							class="h-9 w-full rounded-md border bg-background pr-3 pl-9 text-sm outline-none focus:ring-1 focus:ring-ring"
						/>
					</div>
				</div>
			{:else}
				<h2 class="text-lg font-semibold">{selectedSkill}</h2>
			{/if}
		</div>

		<!-- Content card -->
		<div class="flex flex-col gap-5 rounded-xl border bg-card p-6">
			<div class="mb-2 flex items-start gap-3">
				<div
					class="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary"
				>
					<FileText class="h-4 w-4" />
				</div>
				<div>
					<h3 class="text-sm font-semibold text-foreground">Content</h3>
					<p class="mt-0.5 text-xs text-muted-foreground">
						Markdown content that defines this skill
					</p>
				</div>
			</div>
			<textarea
				id="skill-content"
				bind:value={editorValue}
				rows={16}
				class="w-full resize-y rounded-md border bg-background px-3 py-2 font-mono text-xs outline-none focus:ring-1 focus:ring-ring"
			></textarea>
		</div>

		<!-- Actions -->
		<div class="flex items-center gap-3 pt-2 pb-4">
			<button
				onclick={save}
				class="rounded-md bg-primary px-6 py-2 text-sm font-medium text-primary-foreground transition-opacity hover:opacity-90"
			>
				{saveMsg || 'Save changes'}
			</button>
			{#if saveMsg}<p class="text-xs text-muted-foreground">{saveMsg}</p>{/if}
			{#if selectedSkill}
				<button
					onclick={() => selectedSkill && deleteSkill(selectedSkill)}
					class="ml-auto flex items-center gap-1.5 rounded-md border border-destructive/50 px-4 py-2 text-sm font-medium text-destructive transition-colors hover:bg-destructive/10"
				>
					<Trash2 class="h-3.5 w-3.5" /> Delete
				</button>
			{/if}
		</div>
	</div>
{:else}
	<!-- List view -->
	<div class="mx-auto flex max-w-2xl flex-col gap-6 px-6 py-8">
		<div class="flex items-center justify-between">
			<div>
				<h2 class="text-lg font-semibold">Skills</h2>
				<p class="mt-0.5 text-sm text-muted-foreground">Manage your agent skills</p>
			</div>
			<button
				onclick={startNew}
				class="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-opacity hover:opacity-90"
			>
				+ New Skill
			</button>
		</div>

		<div class="flex flex-col gap-2">
			{#each daemon.skills as skill (skill.name)}
				<div
					class="flex items-center gap-3 rounded-xl border bg-card px-4 py-3 transition-colors hover:bg-accent/30"
				>
					<div
						class="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-muted text-xs font-bold text-muted-foreground"
					>
						{skill.name[0].toUpperCase()}
					</div>
					<div class="min-w-0 flex-1">
						<p class="truncate text-sm font-semibold">{skill.name}</p>
						<p class="mt-0.5 truncate text-xs text-muted-foreground">
							{skill.summary || 'No description'}
						</p>
					</div>
					<button
						onclick={() => selectSkill(skill.name)}
						class="shrink-0 rounded-md border px-3 py-1.5 text-xs font-medium transition-colors hover:bg-accent"
					>
						Edit
					</button>
				</div>
			{/each}
			{#if daemon.skills.length === 0}
				<p class="py-8 text-center text-sm text-muted-foreground">No skills found</p>
			{/if}
		</div>
	</div>
{/if}
