<script lang="ts">
  import type { MessageStats } from '$lib/daemon/protocol';
  import { Info } from '@lucide/svelte';
  import { Popover, PopoverContent, PopoverTrigger } from '$lib/components/ui/popover';

  interface Props {
    stats: MessageStats;
  }

  let { stats }: Props = $props();

  const duration = $derived(
    stats.finished_at != null
      ? (stats.finished_at - stats.started_at).toFixed(1) + 's'
      : null
  );
</script>

<Popover>
  <PopoverTrigger>
    <button type="button" class="inline-flex items-center justify-center text-muted-foreground hover:text-foreground transition-colors">
      <Info size={14} />
    </button>
  </PopoverTrigger>
  <PopoverContent class="w-52 p-3 text-xs">
    <div class="space-y-1.5">
      <div class="flex justify-between gap-2">
        <span class="text-muted-foreground">Agent</span>
        <span class="font-medium text-foreground text-right">{stats.agent_name ?? 'unknown'}</span>
      </div>
      {#if duration}
        <div class="flex justify-between gap-2">
          <span class="text-muted-foreground">Duration</span>
          <span class="font-medium text-foreground font-mono">{duration}</span>
        </div>
      {/if}
      {#if stats.token_count != null}
        <div class="flex justify-between gap-2">
          <span class="text-muted-foreground">Tokens</span>
          <span class="font-medium text-foreground font-mono">{stats.token_count}</span>
        </div>
      {/if}
    </div>
  </PopoverContent>
</Popover>
