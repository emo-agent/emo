<script lang="ts">
  import type { AgentAction } from '$lib/daemon/protocol';
  import { Bot, ChevronDown, ChevronUp } from '@lucide/svelte';

  interface Props {
    action: AgentAction;
  }

  let { action }: Props = $props();
  let expanded = $state(false);

  function formatTime(ts: number): string {
    return new Date(ts * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  }
</script>

<div class="rounded-md border border-blue-200/40 bg-blue-500/5 text-xs">
  <!-- Header row -->
  <button
    type="button"
    class="flex w-full items-center gap-2 px-3 py-2 text-left"
    onclick={() => (expanded = !expanded)}
  >
    <Bot size={14} class="shrink-0 text-blue-400" />
    <span class="font-medium text-foreground">{action.name}</span>
    <span class="text-muted-foreground">{action.action}</span>
    <span class="flex-1 text-right text-muted-foreground/60">{formatTime(action.started_at)}</span>
    {#if expanded}
      <ChevronUp size={14} class="shrink-0 text-muted-foreground" />
    {:else}
      <ChevronDown size={14} class="shrink-0 text-muted-foreground" />
    {/if}
  </button>

  <!-- Expanded content -->
  {#if expanded}
    <div class="border-t border-blue-200/30 px-3 py-2 space-y-1">
      <div class="flex items-center gap-2">
        <span class="text-muted-foreground/70 w-20">Agent</span>
        <span class="font-medium text-foreground">{action.name}</span>
      </div>
      <div class="flex items-center gap-2">
        <span class="text-muted-foreground/70 w-20">Action</span>
        <span class="text-foreground">{action.action}</span>
      </div>
      <div class="flex items-center gap-2">
        <span class="text-muted-foreground/70 w-20">Started</span>
        <span class="text-foreground font-mono">{formatTime(action.started_at)}</span>
      </div>
      {#if action.finished_at}
        <div class="flex items-center gap-2">
          <span class="text-muted-foreground/70 w-20">Finished</span>
          <span class="text-foreground font-mono">{formatTime(action.finished_at)}</span>
        </div>
      {/if}
    </div>
  {/if}
</div>
