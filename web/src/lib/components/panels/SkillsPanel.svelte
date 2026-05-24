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
	<div class="max-w-2xl mx-auto py-8 px-6 flex flex-col gap-8">
		<!-- Breadcrumb + name -->
		<div>
			<button
				onclick={() => { selectedSkill = null; isNew = false; }}
				class="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground mb-2 transition-colors"
			>
				<ChevronLeft class="h-3.5 w-3.5" /> All Skills
			</button>
			{#if isNew}
				<div class="flex flex-col gap-1.5">
					<label class={labelClass} for="skill-name">Skill Name</label>
					<div class="relative">
						<Tag class="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground pointer-events-none" />
						<input
							id="skill-name"
							type="text"
							bind:value={newName}
							placeholder="my-skill"
							class="h-9 rounded-md border bg-background pl-9 pr-3 text-sm outline-none focus:ring-1 focus:ring-ring w-full"
						/>
					</div>
				</div>
			{:else}
				<h2 class="text-lg font-semibold">{selectedSkill}</h2>
			{/if}
		</div>

		<!-- Content card -->
		<div class="rounded-xl border bg-card p-6 flex flex-col gap-5">
			<div class="flex items-start gap-3 mb-2">
				<div class="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
					<FileText class="h-4 w-4" />
				</div>
				<div>
					<h3 class="text-sm font-semibold text-foreground">Content</h3>
					<p class="text-xs text-muted-foreground mt-0.5">Markdown content that defines this skill</p>
				</div>
			</div>
			<textarea
				id="skill-content"
				bind:value={editorValue}
				rows={16}
				class="w-full rounded-md border bg-background px-3 py-2 font-mono text-xs outline-none focus:ring-1 focus:ring-ring resize-y"
			></textarea>
		</div>

		<!-- Actions -->
		<div class="flex items-center gap-3 pt-2 pb-4">
			<button
				onclick={save}
				class="rounded-md bg-primary px-6 py-2 text-sm font-medium text-primary-foreground hover:opacity-90 transition-opacity"
			>
				{saveMsg || 'Save changes'}
			</button>
			{#if saveMsg}<p class="text-xs text-muted-foreground">{saveMsg}</p>{/if}
			{#if selectedSkill}
				<button
					onclick={() => selectedSkill && deleteSkill(selectedSkill)}
					class="ml-auto flex items-center gap-1.5 rounded-md border border-destructive/50 px-4 py-2 text-sm font-medium text-destructive hover:bg-destructive/10 transition-colors"
				>
					<Trash2 class="h-3.5 w-3.5" /> Delete
				</button>
			{/if}
		</div>
	</div>
{:else}
	<!-- List view -->
	<div class="max-w-2xl mx-auto py-8 px-6 flex flex-col gap-6">
		<div class="flex items-center justify-between">
			<div>
				<h2 class="text-lg font-semibold">Skills</h2>
				<p class="text-sm text-muted-foreground mt-0.5">Manage your agent skills</p>
			</div>
			<button
				onclick={startNew}
				class="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90 transition-opacity"
			>
				+ New Skill
			</button>
		</div>

		<div class="flex flex-col gap-2">
			{#each daemon.skills as skill (skill.name)}
				<div class="flex items-center gap-3 rounded-xl border bg-card px-4 py-3 hover:bg-accent/30 transition-colors">
					<div class="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-muted text-muted-foreground text-xs font-bold">
						{skill.name[0].toUpperCase()}
					</div>
					<div class="flex-1 min-w-0">
						<p class="text-sm font-semibold truncate">{skill.name}</p>
						<p class="text-xs text-muted-foreground mt-0.5 truncate">{skill.summary || 'No description'}</p>
					</div>
					<button
						onclick={() => selectSkill(skill.name)}
						class="rounded-md border px-3 py-1.5 text-xs font-medium hover:bg-accent shrink-0 transition-colors"
					>
						Edit
					</button>
				</div>
			{/each}
			{#if daemon.skills.length === 0}
				<p class="text-sm text-muted-foreground py-8 text-center">No skills found</p>
			{/if}
		</div>
	</div>
{/if}
