<script lang="ts">
  import ExprEditor from '$lib/components/expr-editor.svelte';
  import { SET_OPS, tokenizeExprText, parseExprText, exprToText, type ExprNode, type EditorToken } from '$lib/iseql-model';

  type Props = {
    expr: ExprNode | null;
    groupNames: string[];
    onExpr: (expr: ExprNode | null) => void;
    onOpenGroup: (name: string) => void;
    onHover?: (groups: string[]) => void;
  };
  let { expr, groupNames, onExpr, onOpenGroup, onHover = () => undefined }: Props = $props();

  let text = $state('');
  let suppress = false;

  const tokens = $derived<EditorToken[] | null>(mapTokens(tokenizeExprText(text)));

  function mapTokens(tk: ReturnType<typeof tokenizeExprText>): EditorToken[] | null {
    if (!tk) return null;
    return tk.map((t) => (t.type === 'group' ? { type: 'item' as const, name: t.name } : t));
  }

  $effect(() => {
    void expr;
    if (suppress) { suppress = false; return; }
    text = exprToText(expr);
  });

  function onText(next: string) {
    suppress = true;
    text = next;
    const tree = parseExprText(next);
    onExpr(tree);
    setTimeout(() => { suppress = false; }, 0);
  }
</script>

<ExprEditor {text} {tokens} options={groupNames} operators={SET_OPS} kind="group" {onText} onOpen={onOpenGroup} {onHover} />
