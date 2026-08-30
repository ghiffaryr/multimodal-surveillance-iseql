<script lang="ts">
  type Props = {
    filtered: number;
    total: number;
    filtering?: boolean;
  };
  let { filtered, total, filtering = false }: Props = $props();
</script>

<span class="inline-flex items-center rounded-full bg-muted px-2 py-0.5 text-[10px] font-medium leading-none text-muted-foreground">
  {filtering ? `${filtered} / ${total}` : `${total}`}
</span>
