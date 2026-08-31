// Types and conversion helpers for the visual ISEQL event builder.
//
// The builder edits a model of *groups* (each a chain of intervals) combined by
// a *set-expression tree* (∪ / \ / ∩). This maps onto the backend model shape:
//
//   intervals:   flat list, each carrying a `group` name
//   set_expression: tree whose leaves reference group names (with per-group projection)
//   delta_map:   keyed "<group>.<pairIdx>", values are threshold overrides
//   operator_overrides: keyed by (side=group, pair_idx) for manual operators
//   cross_conditions: global alias constraints (M1.arg1 = M2.arg1, duration)

export type Modality = 'visual' | 'audio';
export type Unit = 'frames' | 'seconds';

export interface PredicateVocab {
  name: string;
  modality: Modality;
  args: string[][];
}

export interface Vocabulary {
  predicates: PredicateVocab[];
  participant_classes: string[];
}

export interface BuilderInterval {
  id: string;
  pred: string;
  args: string[];
  ts: number;
  te: number;
  selection?: Record<string, unknown> | null;
}

export interface BuilderOperator {
  op: string; // 'auto' or one of Bef Aft SP EF DJ RDJ LOJ ROJ
  delta: string; // number or named key or '' (unbounded)
  epsilon: string;
  zeta: string;
  eta: string;
  rho: string;
}

export interface BuilderGroup {
  name: string;
  intervals: BuilderInterval[];
  ops: BuilderOperator[];
  projection: string[] | null;
  crossConditions: CrossCondition[];
}

export type SetOp = '∪' | '\\' | '∩';

export interface ExprLeaf {
  group: string;
  projection?: string[];
}

export interface ExprBranch {
  op: SetOp;
  children: ExprNode[];
}

export type ExprNode = ExprLeaf | ExprBranch;

export interface CrossCondition {
  id: string;
  type: 'attr' | 'duration';
  left_alias: string;
  left_attr: string;
  op: string;
  right_alias?: string;
  right_attr?: string;
  value?: number;
}

export interface BuilderState {
  groups: BuilderGroup[];
  expr: ExprNode | null;
  unit: Unit;
}

// Intervals not assigned to any set live in the trailing group whose name is the
// empty string. It is rendered as a "no set" lane and is excluded from sets,
// the set expression, and the set list.
export const UNASSIGNED_GROUP = '';

export interface IseqlInterval {
  pred: { name: string; arguments: string[] };
  ts: number;
  te: number;
  group?: string | null;
  set_side?: string | null;
  [k: string]: unknown;
}

export interface IseqlModel {
  event_name?: string;
  intervals: IseqlInterval[];
  set_expression?: ExprNode | null;
  cross_conditions?: Record<string, unknown>[];
  operator_overrides?: { side?: string | null; pair_idx: number; operator: string }[];
  delta_map?: Record<string, Record<string, unknown>>;
  custom_projection?: string[] | null;
  left_projection?: string[] | null;
  right_projection?: string[] | null;
  set_operator?: string | null;
  delta_unit?: string;
  iseql_text?: string;
  [k: string]: unknown;
}

export const SET_OPS: SetOp[] = ['∪', '\\', '∩'];
export const TEMPORAL_ATTRS = ['sf', 'ef', 'st', 'et'];
export const ARG_ATTRS = ['arg1', 'arg2', 'arg3', 'arg4'];

const OPERATOR_PARAMS: Record<string, string[]> = {
  Bef: ['delta'],
  Aft: ['delta'],
  SP: ['delta'],
  EF: ['epsilon'],
  DJ: ['delta', 'epsilon'],
  RDJ: ['delta', 'epsilon'],
  LOJ: ['delta', 'epsilon'],
  ROJ: ['delta', 'epsilon'],
};

const ALL_OPERATORS = ['Bef', 'Aft', 'SP', 'EF', 'DJ', 'RDJ', 'LOJ', 'ROJ'];

export const OPERATOR_OPTIONS: { value: string; label: string }[] = [
  { value: 'auto', label: 'Auto (from interval times)' },
  ...ALL_OPERATORS.map((op) => ({ value: op, label: op })),
];

let _idSeq = 0;
export function nextId(prefix = 'iv'): string {
  _idSeq += 1;
  return `${prefix}_${Date.now().toString(36)}_${_idSeq}`;
}

export function isLeaf(node: ExprNode): node is ExprLeaf {
  return 'group' in node;
}

export function isBranch(node: ExprNode): node is ExprBranch {
  return 'op' in node;
}

export function leaf(group: string, projection: string[] | null = null): ExprLeaf {
  return projection ? { group, projection } : { group };
}

export function branch(op: SetOp, children: ExprNode[]): ExprBranch {
  return { op, children };
}

// ---------------------------------------------------------------------------
// flat token representation for the drag-and-drop set-expression editor
// ---------------------------------------------------------------------------

export type ExprToken =
  | { type: 'group'; name: string }
  | { type: 'op'; op: SetOp }
  | { type: 'open' }
  | { type: 'close' };

export function treeToTokens(node: ExprNode, parenthesize = false): ExprToken[] {
  if (isLeaf(node)) return [{ type: 'group', name: node.group }];
  const out: ExprToken[] = [];
  if (parenthesize) out.push({ type: 'open' });
  node.children.forEach((child, i) => {
    if (i > 0) out.push({ type: 'op', op: node.op });
    // Left-associative: only parenthesize a non-first child when it is itself a
    // branch, so "g1 ∪ g2 ∪ g3" stays flat instead of "(g1 ∪ g2) ∪ g3".
    out.push(...treeToTokens(child, i > 0 && !isLeaf(child)));
  });
  if (parenthesize) out.push({ type: 'close' });
  return out;
}

export function tokensToTree(tokens: ExprToken[]): ExprNode | null {
  let i = 0;
  function parseTerm(): ExprNode | null {
    const t = tokens[i];
    if (!t) return null;
    if (t.type === 'open') {
      i += 1;
      const node = parseExpr();
      if (!node || tokens[i]?.type !== 'close') return null;
      i += 1;
      return node;
    }
    if (t.type === 'group') {
      i += 1;
      return { group: t.name };
    }
    return null;
  }
  function parseExpr(): ExprNode | null {
    let left = parseTerm();
    if (!left) return null;
    while (tokens[i]?.type === 'op') {
      const op = (tokens[i] as { type: 'op'; op: SetOp }).op;
      i += 1;
      const right = parseTerm();
      if (!right) return null;
      left = { op, children: [left, right] };
    }
    return left;
  }
  const node = parseExpr();
  if (i !== tokens.length) return null;
  return node;
}

export function exprToText(node: ExprNode | null): string {
  if (!node) return '';
  return treeToTokens(node)
    .map((t) => {
      switch (t.type) {
        case 'group': return t.name;
        case 'op': return t.op;
        case 'open': return '(';
        case 'close': return ')';
      }
    })
    .join(' ');
}

export function tokenizeExprText(text: string): ExprToken[] | null {
  const s = text.replace(/∖/g, '\\');
  const tokens: ExprToken[] = [];
  let i = 0;
  while (i < s.length) {
    const ch = s[i];
    if (/\s/.test(ch)) { i += 1; continue; }
    if (ch === '(') { tokens.push({ type: 'open' }); i += 1; continue; }
    if (ch === ')') { tokens.push({ type: 'close' }); i += 1; continue; }
    if (ch === '∪' || ch === '∩' || ch === '\\') { tokens.push({ type: 'op', op: ch as SetOp }); i += 1; continue; }
    if (/[A-Za-z0-9_]/.test(ch)) {
      let j = i;
      while (j < s.length && /[A-Za-z0-9_]/.test(s[j])) j += 1;
      tokens.push({ type: 'group', name: s.slice(i, j) });
      i = j;
      continue;
    }
    return null;
  }
  return tokens;
}

export function tokensToText(tokens: ExprToken[]): string {
  return tokens
    .map((t) => {
      switch (t.type) {
        case 'group': return t.name;
        case 'op': return t.op;
        case 'open': return '(';
        case 'close': return ')';
      }
    })
    .join(' ')
    .replace(/\( /g, '(')
    .replace(/ \)/g, ')');
}

export function parseExprText(text: string): ExprNode | null {
  const tokens = tokenizeExprText(text);
  if (!tokens) return null;
  return tokensToTree(tokens);
}

// ---------------------------------------------------------------------------
// predicate boolean expressions (interval selection): identifiers + ∨ / ()
// Parsed into an OR of predicates, matching the backend `selection` shape.
// ---------------------------------------------------------------------------

export function parseBoolExpr(text: string): string[][] | null {
  const tokens: string[] = [];
  let i = 0;
  while (i < text.length) {
    const ch = text[i];
    if (/\s/.test(ch)) { i += 1; continue; }
    if (ch === '(' || ch === ')' || ch === '∨') { tokens.push(ch); i += 1; continue; }
    if (/[A-Za-z0-9_]/.test(ch)) {
      let j = i;
      while (j < text.length && /[A-Za-z0-9_]/.test(text[j])) j += 1;
      tokens.push(text.slice(i, j));
      i = j;
      continue;
    }
    return null;
  }

  let pos = 0;
  function parseOr(): string[][] | null {
    const left = parseAtom();
    if (!left) return null;
    const result = left;
    while (tokens[pos] === '∨') {
      pos += 1;
      const right = parseAtom();
      if (!right) return null;
      result.push(...right);
    }
    return result;
  }
  function parseAtom(): string[][] | null {
    const t = tokens[pos];
    if (t === '(') {
      pos += 1;
      const n = parseOr();
      if (!n || tokens[pos] !== ')') return null;
      pos += 1;
      return n;
    }
    if (t && t !== '∨' && t !== ')' && t !== '(') {
      pos += 1;
      return [[t]];
    }
    return null;
  }
  const result = parseOr();
  if (pos !== tokens.length || !result || !result.length) return null;
  return result;
}

export function boolBranchesToText(branches: string[][]): string {
  return branches.map((b) => b.join(' ∨ ')).join(' ∨ ');
}

export function boolTextFromSelection(sel: Record<string, unknown> | null | undefined, pred: string): string {
  const s = sel as { branches?: { preds?: string[] }[]; preds?: string[] } | null | undefined;
  if (s && Array.isArray(s.branches) && s.branches.length) {
    return boolBranchesToText(s.branches.map((b) => (b.preds ?? [])));
  }
  if (s && Array.isArray(s.preds) && s.preds.length) {
    return s.preds.join(' ∨ ');
  }
  return pred;
}

export type PredToken =
  | { type: 'pred'; name: string }
  | { type: 'op'; op: '∨' }
  | { type: 'open' }
  | { type: 'close' };

// Unified token shape used by the shared contenteditable expression editor.
export type EditorToken =
  | { type: 'item'; name: string }
  | { type: 'op'; op: string }
  | { type: 'open' }
  | { type: 'close' };

export function tokenizeBoolExpr(text: string): PredToken[] | null {
  const tokens: PredToken[] = [];
  let i = 0;
  while (i < text.length) {
    const ch = text[i];
    if (/\s/.test(ch)) { i += 1; continue; }
    if (ch === '(') { tokens.push({ type: 'open' }); i += 1; continue; }
    if (ch === ')') { tokens.push({ type: 'close' }); i += 1; continue; }
    if (ch === '∨') { tokens.push({ type: 'op', op: '∨' }); i += 1; continue; }
    if (/[A-Za-z0-9_]/.test(ch)) {
      let j = i;
      while (j < text.length && /[A-Za-z0-9_]/.test(text[j])) j += 1;
      tokens.push({ type: 'pred', name: text.slice(i, j) });
      i = j;
      continue;
    }
    return null;
  }
  return tokens;
}

export function predTokensToText(tokens: PredToken[]): string {
  return tokens
    .map((t) => {
      switch (t.type) {
        case 'pred': return t.name;
        case 'op': return t.op;
        case 'open': return '(';
        case 'close': return ')';
      }
    })
    .join(' ')
    .replace(/\( /g, '(')
    .replace(/ \)/g, ')');
}

export function collectGroups(node: ExprNode): string[] {
  if (isLeaf(node)) return [node.group];
  return node.children.flatMap(collectGroups);
}

export function emptyOperator(): BuilderOperator {
  return { op: 'auto', delta: '', epsilon: '', zeta: '<=', eta: '<=', rho: '0' };
}

// ---------------------------------------------------------------------------
// operator detection (mirrors backend iseql.helpers.detect_operator)
// ---------------------------------------------------------------------------

export interface Detected {
  op: string;
  delta: number | null;
  epsilon: number | null;
}

export function detectOperator(r: BuilderInterval, s: BuilderInterval): Detected {
  const rTs = r.ts, rTe = r.te, sTs = s.ts, sTe = s.te;
  if (rTe <= sTs) return { op: 'Bef', delta: sTs - rTe, epsilon: null };
  if (sTe <= rTs) return { op: 'Aft', delta: rTs - sTe, epsilon: null };
  if (sTs <= rTs && rTe <= sTe) return { op: 'DJ', delta: rTs - sTs, epsilon: sTe - rTe };
  if (rTs <= sTs && sTe <= rTe) return { op: 'RDJ', delta: sTs - rTs, epsilon: rTe - sTe };
  if (rTs <= sTs && sTs < rTe && rTe <= sTe) return { op: 'LOJ', delta: sTs - rTs, epsilon: sTe - rTe };
  if (sTs <= rTs && rTs < sTe && sTe <= rTe) return { op: 'ROJ', delta: rTs - sTs, epsilon: rTe - sTe };
  return { op: 'UNKNOWN', delta: null, epsilon: null };
}

// ---------------------------------------------------------------------------
// projection helpers
// ---------------------------------------------------------------------------

export function domainAttr(unit: Unit): { start: string; end: string } {
  return unit === 'seconds' ? { start: 'st', end: 'et' } : { start: 'sf', end: 'ef' };
}

export function autoProjection(g: BuilderGroup, unit: Unit): string[] {
  const { start, end } = domainAttr(unit);
  const fields: string[] = [];
  g.intervals.forEach((iv, i) => {
    const m = `M${i + 1}`;
    for (let k = 1; k <= iv.args.length; k++) fields.push(`${m}.arg${k}`);
    fields.push(`${m}.${start}`, `${m}.${end}`);
  });
  return fields;
}

export function effectiveProjection(g: BuilderGroup, unit: Unit): string[] {
  return g.projection ?? autoProjection(g, unit);
}

export function projectionDomain(projection: string[] | null): Unit {
  if (!projection) return 'frames';
  let hasTime = false;
  let hasFrame = false;
  for (const f of projection) {
    const attr = f.split('.').pop() ?? '';
    if (attr === 'st' || attr === 'et') hasTime = true;
    if (attr === 'sf' || attr === 'ef') hasFrame = true;
  }
  if (hasTime && !hasFrame) return 'seconds';
  return 'frames';
}

// ---------------------------------------------------------------------------
// flattened interval list (for cross-conditions + global alias mapping)
// ---------------------------------------------------------------------------

export interface FlatInterval {
  group: string;
  localIndex: number;
  globalIndex: number; // 0-based
  interval: BuilderInterval;
}

export function flattenIntervals(groups: BuilderGroup[]): FlatInterval[] {
  const out: FlatInterval[] = [];
  let g = 0;
  for (const grp of groups) {
    grp.intervals.forEach((iv, i) => {
      out.push({ group: grp.name, localIndex: i, globalIndex: g++, interval: iv });
    });
  }
  return out;
}

export function aliasOf(globalIndex: number): string {
  return `M${globalIndex + 1}`;
}

// Display label for a predicate with its argument slots (each slot a list of
// alternative classes), e.g. `running(person)`,
// `explosion_visible(vehicle ∨ object)` or `gunshot()`.
export function predicateLabel(name: string, slots: string[][]): string {
  const rendered = slots.map((s) => (s.length > 1 ? s.join(' ∨ ') : s[0] ?? ''));
  return `${name}(${rendered.join(', ')})`;
}

// Human label for an interval, reflecting its authored selection (a single
// predicate or an OR of predicates).
export function intervalLabel(iv: BuilderInterval): string {
  if (!iv.pred) return '';

  type SelBranch = {
    preds?: string[];
    args?: Record<string, string[]>;
    pred_args?: Record<string, string[][]>;
  };
  const sel = iv.selection as {
    branches?: SelBranch[];
    preds?: string[];
    args?: Record<string, string[]>;
    pred_args?: Record<string, string[][]>;
  } | null | undefined;

  const mapSlots = (m: Record<string, string[]> | undefined): string[][] =>
    Object.keys(m ?? {})
      .sort((a, b) => Number(a) - Number(b))
      .map((k) => (m![k] ?? []).filter(Boolean))
      .filter((s) => s.length);

  const flatSlots = (flat: string[]): string[][] => flat.map((c) => [c]);

  const labelPred = (p: string, own: string[][] | undefined, shared: string[][]): string =>
    predicateLabel(p, own && own.some((s) => s.length) ? own : shared);

  if (sel && Array.isArray(sel.branches) && sel.branches.length) {
    return sel.branches
      .map((b) => {
        const shared = mapSlots(b.args);
        return (b.preds ?? []).map((p) => labelPred(p, b.pred_args?.[p], shared)).join(' ∨ ');
      })
      .join(' ∨ ');
  }

  if (sel && Array.isArray(sel.preds) && sel.preds.length) {
    const shared = mapSlots(sel.args);
    const fallback = flatSlots(iv.args);
    return sel.preds
      .map((p) => labelPred(p, sel.pred_args?.[p], shared.length ? shared : fallback))
      .join(' ∨ ');
  }

  return predicateLabel(iv.pred, flatSlots(iv.args));
}

// ---------------------------------------------------------------------------
// state <-> model conversion
// ---------------------------------------------------------------------------

function numOrStr(s: string): number | string | null {
  const t = s.trim();
  if (t === '') return null;
  if (/^\d+$/.test(t)) return parseInt(t, 10);
  return t;
}

export function stateToModel(state: BuilderState, eventName: string): IseqlModel {
  const { groups, expr, unit } = state;
  const intervals: IseqlInterval[] = [];
  const overrides: { side: string | null; pair_idx: number; operator: string }[] = [];
  const deltaMap: Record<string, Record<string, unknown>> = {};

  // attach per-group projection to the tree leaves, pruning empty groups
  // (groups with no intervals carry no data and can't be compiled). The
  // unassigned group is never part of the set expression.
  const sets = groups.filter((g) => g.name !== UNASSIGNED_GROUP);
  const validGroups = new Set(sets.filter((g) => g.intervals.length > 0).map((g) => g.name));
  const finalExpr = expr ? pruneExpr(attachProjections(expr, sets, unit), validGroups) : null;

  for (const g of groups) {
    const isUnassigned = g.name === UNASSIGNED_GROUP;
    for (const iv of g.intervals) {
      const out: IseqlInterval = {
        pred: { name: iv.pred, arguments: iv.args },
        ts: iv.ts,
        te: iv.te,
        group: isUnassigned ? null : g.name,
      };
      if (iv.selection) out.selection = iv.selection;
      intervals.push(out);
    }
    if (isUnassigned) {
      g.ops.forEach((op, i) => {
        if (op.op && op.op !== 'auto') {
          overrides.push({ side: null, pair_idx: i + 1, operator: op.op });
        }
        const entry: Record<string, unknown> = {};
        if (op.delta === '∞') entry.delta = null;
        else if (op.delta.trim() !== '') entry.delta = numOrStr(op.delta);
        if (op.epsilon === '∞') entry.epsilon = null;
        else if (op.epsilon.trim() !== '') entry.epsilon = numOrStr(op.epsilon);
        if (op.zeta && op.zeta !== '<=') entry.zeta = op.zeta;
        if (op.eta && op.eta !== '<=') entry.eta = op.eta;
        if (op.rho.trim() !== '' && op.rho.trim() !== '0') entry.rho = numOrStr(op.rho);
        if (Object.keys(entry).length) deltaMap[String(i)] = entry;
      });
      continue;
    }
    g.ops.forEach((op, i) => {
      if (op.op && op.op !== 'auto') {
        overrides.push({ side: g.name, pair_idx: i + 1, operator: op.op });
      }
      const entry: Record<string, unknown> = {};
      if (op.delta === '∞') entry.delta = null;
      else if (op.delta.trim() !== '') entry.delta = numOrStr(op.delta);
      if (op.epsilon === '∞') entry.epsilon = null;
      else if (op.epsilon.trim() !== '') entry.epsilon = numOrStr(op.epsilon);
      if (op.zeta && op.zeta !== '<=') entry.zeta = op.zeta;
      if (op.eta && op.eta !== '<=') entry.eta = op.eta;
      if (op.rho.trim() !== '' && op.rho.trim() !== '0') entry.rho = numOrStr(op.rho);
      if (Object.keys(entry).length) deltaMap[`${g.name}.${i}`] = entry;
    });
  }

  const model: IseqlModel = {
    event_name: eventName,
    intervals,
    set_expression: finalExpr,
    delta_unit: unit,
  };
  if (overrides.length) model.operator_overrides = overrides;
  if (Object.keys(deltaMap).length) model.delta_map = deltaMap;

  // cross-conditions are authored per-group with local aliases (M1..Mn);
  // rebase them to the global flattened alias indices.
  const localToGlobal = new Map<string, Map<number, number>>();
  for (const f of flattenIntervals(groups)) {
    let m = localToGlobal.get(f.group);
    if (!m) { m = new Map(); localToGlobal.set(f.group, m); }
    m.set(f.localIndex, f.globalIndex);
  }
  const ccs: Record<string, unknown>[] = [];
  for (const g of groups) {
    const map = localToGlobal.get(g.name);
    if (!map) continue;
    for (const c of g.crossConditions) {
      const li = aliasIndex(c.left_alias);
      const ri = aliasIndex(c.right_alias ?? '');
      const gl = li == null ? undefined : map.get(li);
      const gr = ri == null ? undefined : map.get(ri);
      if (gl == null || gr == null) continue;
      if (c.type === 'duration') {
        ccs.push({
          type: 'duration',
          left_alias: `M${gl + 1}`, left_attr: c.left_attr,
          right_alias: `M${gr + 1}`, right_attr: c.right_attr,
          op: c.op, value: c.value,
        });
      } else {
        ccs.push({
          left_alias: `M${gl + 1}`, left_attr: c.left_attr,
          op: c.op,
          right_alias: `M${gr + 1}`, right_attr: c.right_attr,
        });
      }
    }
  }
  if (ccs.length) model.cross_conditions = ccs;

  return model;
}

function aliasIndex(alias: string): number | null {
  const m = /^M(\d+)$/.exec(alias);
  return m ? parseInt(m[1], 10) - 1 : null;
}

function attachProjections(expr: ExprNode, groups: BuilderGroup[], unit: Unit): ExprNode {
  const byName = new Map(groups.map((g) => [g.name, g]));
  if (isLeaf(expr)) {
    const g = byName.get(expr.group);
    const proj = g ? effectiveProjection(g, unit) : null;
    return proj ? { ...expr, projection: proj } : expr;
  }
  return { ...expr, children: expr.children.map((c) => attachProjections(c, groups, unit)) };
}

function pruneExpr(node: ExprNode, valid: Set<string>): ExprNode | null {
  if (isLeaf(node)) return valid.has(node.group) ? node : null;
  const children = node.children
    .map((c) => pruneExpr(c, valid))
    .filter((c): c is ExprNode => c != null);
  if (children.length === 0) return null;
  if (children.length === 1) return children[0];
  return { ...node, children };
}

function strOr(v: unknown): string {
  if (v === null || v === undefined) return '';
  return String(v);
}

// Named threshold keys (e.g. delta_visual_handoff) are not literal values the
// builder can edit; they resolve per-detect. In the builder they preview as
// unbounded ('∞') to match the rendered ISEQL text. A literal null also means
// unbounded, while undefined means "no entry" (auto / unspecified).
function mapDeltaValue(v: unknown): string {
  if (typeof v === 'number') return String(v);
  if (v === null) return '∞';
  if (v === undefined) return '';
  return '∞';
}

function mapRhoValue(v: unknown): string {
  if (typeof v === 'number') return String(v);
  return '0';
}

// Named strictness keys resolve per-detect; fall back to the default '<='.
function strictnessValue(v: unknown): string {
  const s = strOr(v);
  return ['<', '<=', '>', '>='].includes(s) ? s : '<=';
}

export function normalizeModel(model: IseqlModel): IseqlModel {
  const ivs = model.intervals ?? [];
  const hasGroup = ivs.some((iv) => iv.group);
  const hasSide = ivs.some((iv) => iv.set_side);

  let result: IseqlModel;

  if (model.set_expression && hasGroup) {
    result = model;
  } else if (hasSide) {
    const left = ivs.filter((iv) => iv.set_side === 'left');
    const right = ivs.filter((iv) => iv.set_side === 'right');
    const op = (model.set_operator as SetOp) ?? '∪';
    result = {
      ...model,
      intervals: [
        ...left.map((iv) => ({ ...iv, group: 'left', set_side: null })),
        ...right.map((iv) => ({ ...iv, group: 'right', set_side: null })),
      ],
      set_expression: branch(op, [
        leaf('left', model.left_projection ?? null),
        leaf('right', model.right_projection ?? null),
      ]),
      set_operator: null,
      left_projection: null,
      right_projection: null,
    };
  } else if (model.custom_projection?.length) {
    // A custom projection requires a set: wrap the flat chain in a single set
    // so the projection has a set home instead of a dangling custom_projection.
    result = {
      ...model,
      intervals: ivs.map((iv) => ({ ...iv, group: 's1', set_side: null })),
      set_expression: { group: 's1', projection: [...model.custom_projection] },
      custom_projection: null,
      set_operator: null,
      left_projection: null,
      right_projection: null,
      operator_overrides: (model.operator_overrides ?? []).map((o) => ({
        ...o,
        side: o.side == null || o.side === 'none' || o.side === '' ? 's1' : o.side,
      })),
      delta_map: remapFlatDeltaMap(model.delta_map),
    };
  } else {
    // Flat single chain (no groups, no set sides, no custom projection): keep
    // it flat; the projection is auto.
    result = {
      ...model,
      intervals: ivs.map((iv) => ({ ...iv, group: null, set_side: null })),
      set_expression: null,
      set_operator: null,
      operator_overrides: (model.operator_overrides ?? []).map((o) => ({ ...o, side: o.side ?? null })),
      custom_projection: null,
      left_projection: null,
      right_projection: null,
    };
  }

  return renameLegacyGroups(result);
}

// Rewrite flat delta_map keys ("0", "1", ...) to a set side ("s1.0", ...).
function remapFlatDeltaMap(dm: Record<string, Record<string, unknown>> | undefined) {
  if (!dm) return dm;
  const out: Record<string, Record<string, unknown>> = {};
  for (const [k, v] of Object.entries(dm)) {
    out[k.includes('.') ? k : `s1.${k}`] = v;
  }
  return out;
}

// Migrate legacy set names (g1, g2, left, right) to the current s1, s2, ...
// naming, in first-appearance order across intervals. Also rewrites the
// set_expression leaves, delta_map keys and operator_override sides.
function renameLegacyGroups(model: IseqlModel): IseqlModel {
  const ivs = model.intervals ?? [];
  const map = new Map<string, string>();
  let n = 0;
  for (const iv of ivs) {
    const g = iv.group;
    if (typeof g !== 'string' || !g) continue;
    if (map.has(g)) continue;
    if (/^g\d+$/.test(g) || g === 'left' || g === 'right') {
      map.set(g, `s${++n}`);
    }
  }
  if (map.size === 0) return model;

  const rename = (g: string | null | undefined): string | null | undefined =>
    typeof g === 'string' && map.has(g) ? map.get(g) : g;

  const renameExpr = (node: ExprNode | null): ExprNode | null => {
    if (!node) return null;
    if (isLeaf(node)) return { ...node, group: rename(node.group) as string };
    return { ...node, children: node.children.map((c) => renameExpr(c)!).filter((c): c is ExprNode => c != null) };
  };

  const deltaMap: Record<string, Record<string, unknown>> = {};
  for (const [k, v] of Object.entries(model.delta_map ?? {})) {
    const dot = k.indexOf('.');
    const side = dot >= 0 ? k.slice(0, dot) : k;
    const rest = dot >= 0 ? k.slice(dot) : '';
    const newSide = map.has(side) ? map.get(side)! : side;
    deltaMap[`${newSide}${rest}`] = v;
  }

  return {
    ...model,
    intervals: ivs.map((iv) => ({ ...iv, group: rename(iv.group) })),
    set_expression: renameExpr(model.set_expression ?? null),
    delta_map: Object.keys(deltaMap).length ? deltaMap : model.delta_map,
    operator_overrides: (model.operator_overrides ?? []).map((o) => ({ ...o, side: rename(o.side) })),
  };
}

export function unitFromModel(model: IseqlModel): Unit {
  if (model.delta_unit === 'seconds') return 'seconds';
  // fall back to the projection domain
  if (model.set_expression && !isLeaf(model.set_expression)) {
    // inspect the first leaf's projection
    const first = firstLeaf(model.set_expression);
    if (first && first.projection) return projectionDomain(first.projection);
  }
  return 'frames';
}

function firstLeaf(node: ExprNode): ExprLeaf | null {
  if (isLeaf(node)) return node;
  for (const c of node.children) {
    const l = firstLeaf(c);
    if (l) return l;
  }
  return null;
}

export function modelToState(model: IseqlModel): BuilderState {
  const expr = model.set_expression ?? null;
  const unit = unitFromModel(model);

  const groupNames: string[] = [];
  for (const iv of model.intervals) {
    const g = iv.group || null;
    if (g && !groupNames.includes(g)) groupNames.push(g);
  }

  // A set (even a single one) keeps its own projection; only the unassigned
  // lane (no set) falls back to auto projection.
  const groups: BuilderGroup[] = groupNames.map((name) => ({
    name,
    intervals: [],
    ops: [],
    projection: null,
    crossConditions: [],
  }));
  const unassigned: BuilderGroup = { name: UNASSIGNED_GROUP, intervals: [], ops: [], projection: null, crossConditions: [] };

  const idxByName = new Map(groups.map((n, i) => [n.name, i]));

  for (const iv of model.intervals) {
    const g = iv.group || null;
    const target = g && idxByName.has(g) ? groups[idxByName.get(g)!] : unassigned;
    target.intervals.push({
      id: nextId(),
      pred: iv.pred.name,
      args: [...(iv.pred.arguments ?? [])],
      ts: iv.ts,
      te: iv.te,
      selection: (iv.selection as Record<string, unknown>) ?? null,
    });
  }

  const allGroups = [...groups, unassigned];

  // operators
  for (const g of allGroups) {
    const need = Math.max(0, g.intervals.length - 1);
    g.ops = Array.from({ length: need }, () => emptyOperator());
    for (let i = 0; i < need; i++) {
      const isUnassigned = g.name === UNASSIGNED_GROUP;
      const dmKey = isUnassigned ? String(i) : `${g.name}.${i}`;
      const dm = (model.delta_map ?? {})[dmKey] ?? {};
      const ov = (model.operator_overrides ?? []).find(
        (o) => (isUnassigned
          ? (o.side == null || o.side === 'none' || o.side === '')
          : o.side === g.name) && o.pair_idx === i + 1,
      );
      g.ops[i] = {
        op: ov?.operator ?? 'auto',
        delta: mapDeltaValue(dm.delta),
        epsilon: mapDeltaValue(dm.epsilon),
        zeta: strictnessValue(dm.zeta),
        eta: strictnessValue(dm.eta),
        rho: mapRhoValue(dm.rho),
      };
    }
  }

  // projection
  if (expr) {
    const collect = (n: ExprNode) => {
      if (isLeaf(n)) {
        if (n.projection && idxByName.has(n.group)) {
          groups[idxByName.get(n.group)!].projection = n.projection;
        }
      } else n.children.forEach(collect);
    };
    collect(expr);
  }

  const finalExpr: ExprNode | null = expr ?? (groups.length === 1
    ? leaf(groups[0].name)
    : groups.length > 1
      ? branch('∪', groups.map((g) => leaf(g.name)))
      : null);

  // distribute cross-conditions (global aliases) back to the group that owns
  // both endpoints, rebased to local M1..Mn aliases.
  const globalToLocal = new Map<string, { group: string; localIndex: number }>();
  for (const f of flattenIntervals(allGroups)) {
    globalToLocal.set(`M${f.globalIndex + 1}`, { group: f.group, localIndex: f.localIndex });
  }
  for (const c of (model.cross_conditions ?? [])) {
    const cc = c as Record<string, unknown>;
    const left = globalToLocal.get(String(cc.left_alias ?? ''));
    const right = globalToLocal.get(String(cc.right_alias ?? ''));
    if (!left || !right || left.group !== right.group) continue;
    const isUnassigned = left.group === UNASSIGNED_GROUP;
    const target = isUnassigned ? unassigned : groups[idxByName.get(left.group)!];
    const isDuration = cc.type === 'duration';
    target.crossConditions.push({
      id: nextId('cc'),
      type: isDuration ? 'duration' : 'attr',
      left_alias: `M${left.localIndex + 1}`,
      left_attr: String(cc.left_attr ?? ''),
      op: String(cc.op ?? '='),
      right_alias: `M${right.localIndex + 1}`,
      right_attr: String(cc.right_attr ?? ''),
      value: isDuration ? Number(cc.value ?? 0) : undefined,
    });
  }

  return { groups: allGroups, expr: finalExpr, unit };
}

// ---------------------------------------------------------------------------
// empty / seed state
// ---------------------------------------------------------------------------

export function emptyState(): BuilderState {
  const unassigned: BuilderGroup = { name: UNASSIGNED_GROUP, intervals: [], ops: [], projection: null, crossConditions: [] };
  return { groups: [unassigned], expr: null, unit: 'seconds' };
}
