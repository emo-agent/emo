<script lang="ts">
  import type { ToolCall } from '$lib/daemon/protocol';
  import { Wrench, ChevronDown, ChevronUp } from '@lucide/svelte';

  interface Props {
    toolCall: ToolCall;
  }

  let { toolCall }: Props = $props();
  let expanded = $state(false);

  const preview = $derived(
    toolCall.preview.length > 60
      ? toolCall.preview.slice(0, 60) + '…'
      : toolCall.preview
  );
</script>

<div class="rounded-md border border-border bg-muted/50 text-xs">
  <!-- Header row (always visible) -->
  <button
    type="button"
    class="flex w-full items-center gap-2 px-3 py-2 text-left"
    onclick={() => (expanded = !expanded)}
  >
    <Wrench size={14} class="shrink-0 text-muted-foreground" />
    <span class="font-medium text-foreground">{toolCall.name}</span>
    <span class="flex-1 truncate text-muted-foreground">{preview}</span>
    {#if expanded}
      <ChevronUp size={14} class="shrink-0 text-muted-foreground" />
    {:else}
      <ChevronDown size={14} class="shrink-0 text-muted-foreground" />
    {/if}
  </button>

  <!-- Expanded content -->
  {#if expanded}
    <div class="border-t border-border px-3 py-2 space-y-2">
      <p class="text-muted-foreground">{toolCall.preview}</p>

      {#if toolCall.input}
        <div>
          <p class="mb-1 font-medium text-foreground/70 uppercase tracking-wide text-[10px]">Input</p>
          <pre class="rounded bg-background/60 p-2 text-[11px] font-mono overflow-x-auto whitespace-pre-wrap break-all">{JSON.stringify(toolCall.input, null, 2)}</pre>
        </div>
      {/if}

      {#if toolCall.output}
        <div>
          <p class="mb-1 font-medium text-foreground/70 uppercase tracking-wide text-[10px]">Output</p>
          <pre class="rounded bg-background/60 p-2 text-[11px] font-mono overflow-x-auto whitespace-pre-wrap break-all">{toolCall.output}</pre>
        </div>
      {/if}
    </div>
  {/if}
</div>
