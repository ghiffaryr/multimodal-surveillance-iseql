import { describe, it, expect } from 'vitest';
import {
  UNASSIGNED_GROUP,
  aliasOf,
  autoProjection,
  boolBranchesToText,
  boolTextFromSelection,
  branch,
  collectGroups,
  detectOperator,
  domainAttr,
  effectiveProjection,
  emptyOperator,
  emptyState,
  exprToText,
  flattenIntervals,
  intervalLabel,
  isBranch,
  isLeaf,
  leaf,
  modelToState,
  nextId,
  normalizeModel,
  parseBoolExpr,
  parseExprText,
  predTokensToText,
  projectionDomain,
  stateToModel,
  tokenizeBoolExpr,
  tokenizeExprText,
  tokensToText,
  tokensToTree,
  treeToTokens,
  type BuilderGroup,
  type BuilderInterval,
  type BuilderOperator,
  type BuilderState,
  type IseqlModel,
  type Unit,
} from './iseql-model';

// ---------------------------------------------------------------------------
// helpers
// ---------------------------------------------------------------------------

function makeInterval(pred: string, args: string[] = [], ts = 0, te = 100): BuilderInterval {
  return { id: nextId(), pred, args, ts, te };
}

function makeGroup(
  name: string,
  intervals: BuilderInterval[] = [],
  ops: BuilderOperator[] = [],
): BuilderGroup {
  return { name, intervals, ops, projection: null, crossConditions: [] };
}

function flatState(): BuilderState {
  const g = makeGroup('g1', [
    makeInterval('running', ['person'], 10, 20),
    makeInterval('enter_or_exit_vehicle', ['person', 'vehicle'], 22, 30),
  ]);
  g.ops = [{ ...emptyOperator(), op: 'Bef', delta: '5', rho: '2', zeta: '<=' }];
  return { groups: [g], expr: leaf('g1'), unit: 'frames' };
}

// ---------------------------------------------------------------------------
// expression tree helpers
// ---------------------------------------------------------------------------

describe('expr tree', () => {
  it('round-trips exprToText / parseExprText', () => {
    const node = branch('∪', [leaf('s1'), leaf('s2')]);
    expect(isBranch(node)).toBe(true);
    expect(exprToText(node)).toBe('s1 ∪ s2');
    const back = parseExprText('s1 ∪ s2');
    expect(back).not.toBeNull();
    expect(isBranch(back!)).toBe(true);
  });

  it('parses nested parenthesised expressions', () => {
    const node = parseExprText('(s1 ∪ s2) \\ s3');
    expect(node).not.toBeNull();
    const b = node as { op: string; children: unknown[] };
    expect(b.op).toBe('\\');
    expect(b.children).toHaveLength(2);
  });

  it('isLeaf / isBranch discriminate', () => {
    expect(isLeaf(leaf('s1'))).toBe(true);
    expect(isBranch(branch('∩', [leaf('a'), leaf('b')]))).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// predicate boolean expressions
// ---------------------------------------------------------------------------

describe('bool expressions', () => {
  it('rejects AND conjunction', () => {
    expect(parseBoolExpr('running ∧ walking')).toBeNull();
  });

  it('parses OR branches', () => {
    expect(parseBoolExpr('running ∨ walking')).toEqual([['running'], ['walking']]);
  });

  it('tokenizes into predicates', () => {
    const tokens = tokenizeBoolExpr('running ∨ walking');
    const preds = (tokens ?? []).filter((t) => t.type === 'pred').map((t) => t.name);
    expect(preds).toEqual(['running', 'walking']);
  });
});

// ---------------------------------------------------------------------------
// empty state + labels
// ---------------------------------------------------------------------------

describe('empty state and labels', () => {
  it('emptyState has a single unassigned group', () => {
    const st = emptyState();
    expect(st.groups).toHaveLength(1);
    expect(st.groups[0].name).toBe(UNASSIGNED_GROUP);
    expect(st.expr).toBeNull();
  });

  it('emptyOperator is auto/unbounded', () => {
    const op = emptyOperator();
    expect(op.op).toBe('auto');
    expect(op.rho).toBe('0');
  });

  it('intervalLabel reflects a multi-branch selection', () => {
    const iv = makeInterval('running');
    iv.selection = {
      branches: [
        { preds: ['running'], args: { 1: ['person'] } },
        { preds: ['walking'], args: { 1: ['person'] } },
      ],
    };
    expect(intervalLabel(iv)).toBe('running(person) ∨ walking(person)');
  });

  it('intervalLabel renders multi-value args without wrapping parens', () => {
    const iv = makeInterval('explosion_visible', ['vehicle']);
    iv.selection = {
      branches: [{ preds: ['explosion_visible'], args: { 1: ['vehicle', 'object'] } }],
    };
    expect(intervalLabel(iv)).toBe('explosion_visible(vehicle ∨ object)');
  });

  it('intervalLabel shows empty parens for audio predicates', () => {
    const iv = makeInterval('gunshot', []);
    expect(intervalLabel(iv)).toBe('gunshot()');
  });

  it('intervalLabel shows args for a multi-predicate selection', () => {
    const iv = makeInterval('running', ['person']);
    iv.selection = { preds: ['running', 'walking'], args: { 1: ['person'] } };
    expect(intervalLabel(iv)).toBe('running(person) ∨ walking(person)');
  });

  it('intervalLabel shows args for OR branches', () => {
    const iv = makeInterval('running', ['person']);
    iv.selection = {
      branches: [
        { preds: ['running'], args: { 1: ['person'] } },
        { preds: ['walking'], args: { 1: ['person'] } },
      ],
    };
    expect(intervalLabel(iv)).toBe('running(person) ∨ walking(person)');
  });

  it('intervalLabel falls back to interval args for multi-predicate without selection args', () => {
    const iv = makeInterval('running', ['person']);
    iv.selection = { preds: ['running', 'walking'], args: {} };
    expect(intervalLabel(iv)).toBe('running(person) ∨ walking(person)');
  });

  it('intervalLabel renders per-predicate args from pred_args', () => {
    const iv = makeInterval('running', ['person']);
    iv.selection = {
      preds: ['running', 'carrying'],
      args: { 1: ['person'], 2: ['object'] },
      pred_args: { running: [['person']], carrying: [['person'], ['object']] },
    };
    expect(intervalLabel(iv)).toBe('running(person) ∨ carrying(person, object)');
  });

  it('intervalLabel renders a single predicate with alternatives', () => {
    const iv = makeInterval('explosion_visible', ['vehicle']);
    iv.selection = {
      preds: ['explosion_visible'],
      args: { 1: ['vehicle', 'object'] },
      pred_args: { explosion_visible: [['vehicle', 'object']] },
    };
    expect(intervalLabel(iv)).toBe('explosion_visible(vehicle ∨ object)');
  });

  it('intervalLabel renders a single predicate with args', () => {
    const iv = makeInterval('carrying', ['person', 'object']);
    expect(intervalLabel(iv)).toBe('carrying(person, object)');
  });

  it('detectOperator returns a known operator', () => {
    const a = makeInterval('running', [], 0, 10);
    const b = makeInterval('walking', [], 20, 30);
    const d = detectOperator(a, b);
    expect(typeof d.op).toBe('string');
  });
});

// ---------------------------------------------------------------------------
// state <-> model round trip
// ---------------------------------------------------------------------------

describe('state <-> model', () => {
  it('stateToModel emits a flat single-set model', () => {
    const m = stateToModel(flatState(), 'e');
    expect(m.event_name).toBe('e');
    expect(m.intervals).toHaveLength(2);
    expect(m.intervals[0].group).toBe('g1');
    expect(m.set_expression).toEqual({ group: 'g1', projection: expect.any(Array) });
    expect(m.operator_overrides).toEqual([
      { side: 'g1', pair_idx: 1, operator: 'Bef' },
    ]);
    expect(m.delta_map).toHaveProperty('g1.0');
  });

  it('modelToState keeps a single set as a named group', () => {
    const m = stateToModel(flatState(), 'e');
    const st = modelToState(m);
    const named = st.groups.filter((g) => g.name !== UNASSIGNED_GROUP);
    expect(named).toHaveLength(1);
    expect(named[0].intervals).toHaveLength(2);
    expect(named[0].intervals[0].pred).toBe('running');
    expect(st.groups.find((g) => g.name === UNASSIGNED_GROUP)?.intervals).toHaveLength(0);
  });

  it('round-trips numeric thresholds', () => {
    const m = stateToModel(flatState(), 'e');
    const st = modelToState(m);
    const op = st.groups[0].ops[0];
    expect(op.op).toBe('Bef');
    expect(op.delta).toBe('5');
    expect(op.rho).toBe('2');
  });

  it('flattenIntervals assigns global indices across groups', () => {
    const g1 = makeGroup('s1', [makeInterval('running')]);
    const g2 = makeGroup('s2', [makeInterval('walking')]);
    const flat = flattenIntervals([g1, g2]);
    expect(flat).toHaveLength(2);
    expect(flat.map((f) => f.globalIndex)).toEqual([0, 1]);
  });

  it('preserves empty sets (no intervals) across a round-trip', () => {
    const filled = makeGroup('s1', [makeInterval('running', ['person'], 10, 20)]);
    const empty = makeGroup('s2', []); // authored set with no intervals yet
    const state: BuilderState = {
      groups: [filled, empty],
      expr: leaf('s1'),
      unit: 'seconds',
    };
    const m = stateToModel(state, 'e');
    // The empty set is kept out of set_expression and recorded separately.
    expect(m.set_expression).toEqual({ group: 's1', projection: expect.any(Array) });
    expect(m.empty_groups).toEqual(['s2']);

    const st = modelToState(m);
    const named = st.groups.filter((g) => g.name !== UNASSIGNED_GROUP);
    expect(named.map((g) => g.name).sort()).toEqual(['s1', 's2']);
    expect(named.find((g) => g.name === 's2')?.intervals).toHaveLength(0);
  });
});

// ---------------------------------------------------------------------------
// normalizeModel
// ---------------------------------------------------------------------------

describe('normalizeModel', () => {
  it('keeps a flat model flat when there is no custom projection', () => {
    const m: IseqlModel = {
      event_name: 'e',
      intervals: [
        { pred: { name: 'running', arguments: ['person'] }, ts: 10, te: 20 },
      ],
    };
    const n = normalizeModel(m);
    expect(n.set_expression).toBeNull();
    expect(n.intervals[0].group).toBeNull();
    expect(n.custom_projection).toBeNull();
  });

  it('wraps a flat model with a custom projection into a single set', () => {
    const m: IseqlModel = {
      event_name: 'e',
      intervals: [
        { pred: { name: 'running', arguments: ['person'] }, ts: 10, te: 20 },
      ],
      custom_projection: ['M1.arg1', 'M1.sf', 'M1.ef'],
      delta_map: { '0': { delta: 5 } },
      operator_overrides: [{ side: 'none', pair_idx: 1, operator: 'Bef' }],
    };
    const n = normalizeModel(m);
    expect(n.set_expression).toEqual({ group: 's1', projection: ['M1.arg1', 'M1.sf', 'M1.ef'] });
    expect(n.intervals[0].group).toBe('s1');
    expect(n.custom_projection).toBeNull();
    expect(n.delta_map).toEqual({ 's1.0': { delta: 5 } });
    expect(n.operator_overrides).toEqual([{ side: 's1', pair_idx: 1, operator: 'Bef' }]);
  });

  it('migrates legacy left/right set sides to s1/s2', () => {
    const m: IseqlModel = {
      event_name: 'e',
      intervals: [
        { pred: { name: 'running', arguments: [] }, ts: 0, te: 10, set_side: 'left' },
        { pred: { name: 'walking', arguments: [] }, ts: 0, te: 10, set_side: 'right' },
      ],
      set_operator: '∪',
    };
    const n = normalizeModel(m);
    const groups = n.intervals.map((iv) => iv.group);
    expect(groups).toEqual(['s1', 's2']);
  });
});

// ---------------------------------------------------------------------------
// expression token round-trips
// ---------------------------------------------------------------------------

describe('expression tokens', () => {
  it('tokenizes and renders expression text', () => {
    const tokens = tokenizeExprText('(s1 ∪ s2) \\ s3');
    expect(tokens).not.toBeNull();
    expect(tokensToText(tokens!)).toBe('(s1 ∪ s2) \\ s3');
  });

  it('treeToTokens / tokensToTree round-trip', () => {
    const node = branch('\\', [branch('∪', [leaf('s1'), leaf('s2')]), leaf('s3')]);
    const tokens = treeToTokens(node);
    expect(tokensToTree(tokens)).toEqual(node);
  });

  it('tokenizeExprText maps ∖ to \\', () => {
    const tokens = tokenizeExprText('s1 ∖ s2');
    expect(tokens?.[1]).toEqual({ type: 'op', op: '\\' });
  });

  it('tokenizeExprText rejects invalid characters', () => {
    expect(tokenizeExprText('s1 + s2')).toBeNull();
  });

  it('collectGroups gathers leaf names', () => {
    const node = branch('∪', [leaf('s1'), leaf('s2')]);
    expect(collectGroups(node)).toEqual(['s1', 's2']);
  });
});

// ---------------------------------------------------------------------------
// boolean expression helpers
// ---------------------------------------------------------------------------

describe('boolean helpers', () => {
  it('boolBranchesToText renders an OR of predicates', () => {
    expect(boolBranchesToText([['running'], ['walking'], ['carrying']])).toBe(
      'running ∨ walking ∨ carrying',
    );
  });

  it('boolTextFromSelection handles branches / preds / fallback', () => {
    expect(boolTextFromSelection({ branches: [{ preds: ['running'] }, { preds: ['walking'] }] }, 'x')).toBe('running ∨ walking');
    expect(boolTextFromSelection({ preds: ['running', 'walking'] }, 'x')).toBe('running ∨ walking');
    expect(boolTextFromSelection(null, 'running')).toBe('running');
  });

  it('predTokensToText renders tokens compactly', () => {
    expect(predTokensToText([{ type: 'pred', name: 'running' }, { type: 'op', op: '∨' }, { type: 'pred', name: 'walking' }])).toBe('running ∨ walking');
  });

  it('parseBoolExpr handles parentheses', () => {
    expect(parseBoolExpr('(running ∨ walking) ∨ carrying')).toEqual([
      ['running'],
      ['walking'],
      ['carrying'],
    ]);
  });
});

// ---------------------------------------------------------------------------
// operator detection (all branches)
// ---------------------------------------------------------------------------

describe('detectOperator', () => {
  it('detects all relation types', () => {
    const r = makeInterval('a', [], 0, 10);
    expect(detectOperator(r, makeInterval('b', [], 15, 25)).op).toBe('Bef');
    expect(detectOperator(makeInterval('b', [], 15, 25), r).op).toBe('Aft');
    expect(detectOperator(makeInterval('b', [], 5, 15), makeInterval('c', [], 0, 20)).op).toBe('DJ');
    expect(detectOperator(makeInterval('c', [], 0, 20), makeInterval('b', [], 5, 15)).op).toBe('RDJ');
    expect(detectOperator(makeInterval('c', [], 0, 10), makeInterval('b', [], 5, 15)).op).toBe('LOJ');
    expect(detectOperator(makeInterval('b', [], 5, 15), makeInterval('c', [], 0, 10)).op).toBe('ROJ');
  });
});

// ---------------------------------------------------------------------------
// projection helpers
// ---------------------------------------------------------------------------

describe('projection helpers', () => {
  it('domainAttr maps unit to attribute names', () => {
    expect(domainAttr('seconds')).toEqual({ start: 'st', end: 'et' });
    expect(domainAttr('frames')).toEqual({ start: 'sf', end: 'ef' });
  });

  it('autoProjection builds arg + temporal fields', () => {
    const g = makeGroup('s1', [makeInterval('running', ['person', 'vehicle'], 0, 10)]);
    expect(autoProjection(g, 'frames')).toEqual(['M1.arg1', 'M1.arg2', 'M1.sf', 'M1.ef']);
  });

  it('effectiveProjection falls back to auto', () => {
    const g = makeGroup('s1', [makeInterval('running', ['person'], 0, 10)]);
    expect(effectiveProjection(g, 'frames')).toEqual(['M1.arg1', 'M1.sf', 'M1.ef']);
    g.projection = ['M1.sf'];
    expect(effectiveProjection(g, 'frames')).toEqual(['M1.sf']);
  });

  it('projectionDomain detects time vs frames', () => {
    expect(projectionDomain(null)).toBe('frames');
    expect(projectionDomain(['M1.st', 'M1.et'])).toBe('seconds');
    expect(projectionDomain(['M1.sf', 'M1.ef'])).toBe('frames');
  });

  it('aliasOf formats global indices', () => {
    expect(aliasOf(0)).toBe('M1');
    expect(aliasOf(2)).toBe('M3');
  });
});

// ---------------------------------------------------------------------------
// multi-group state <-> model round trip
// ---------------------------------------------------------------------------

describe('multi-group state <-> model', () => {
  function twoGroupState(): BuilderState {
    const s1 = makeGroup('s1', [
      makeInterval('running', ['person'], 0, 10),
      makeInterval('walking', ['person'], 20, 30),
    ]);
    s1.ops = [{ op: 'Bef', delta: '5', epsilon: '', zeta: '<=', eta: '<=', rho: '2' }];
    s1.crossConditions = [{
      id: nextId('cc'),
      type: 'duration',
      left_alias: 'M1',
      left_attr: 'ef',
      op: '>=',
      right_alias: 'M1',
      right_attr: 'sf',
      value: 5,
    }];
    const s2 = makeGroup('s2', [makeInterval('carrying', ['person', 'object'], 0, 10)]);
    return { groups: [s1, s2], expr: branch('∪', [leaf('s1'), leaf('s2')]), unit: 'frames' };
  }

  it('stateToModel emits groups + union + thresholds + cross-conditions', () => {
    const m = stateToModel(twoGroupState(), 'e');
    const groups = [...new Set(m.intervals.map((i) => i.group))];
    expect(groups).toEqual(['s1', 's2']);
    expect(m.set_expression).toEqual({ op: '∪', children: [expect.anything(), expect.anything()] });
    expect(m.delta_map).toHaveProperty('s1.0');
    expect(m.cross_conditions?.length).toBe(1);
  });

  it('modelToState restores two groups + unassigned', () => {
    const m = stateToModel(twoGroupState(), 'e');
    const st = modelToState(m);
    expect(st.groups).toHaveLength(3);
    const s1 = st.groups.find((g) => g.name === 's1')!;
    expect(s1.intervals).toHaveLength(2);
    expect(s1.ops[0].op).toBe('Bef');
    expect(s1.ops[0].delta).toBe('5');
    expect(s1.crossConditions).toHaveLength(1);
  });
});

// ---------------------------------------------------------------------------
// flat model (no set) handling
// ---------------------------------------------------------------------------

describe('flat model handling', () => {
  it('modelToState treats a flat model with custom projection as auto (no set)', () => {
    const m: IseqlModel = {
      event_name: 'e',
      delta_unit: 'frames',
      intervals: [
        { pred: { name: 'running', arguments: ['person'] }, ts: 0, te: 10 },
        { pred: { name: 'walking', arguments: ['person'] }, ts: 20, te: 30 },
      ],
      operator_overrides: [{ side: null, pair_idx: 1, operator: 'Bef' }],
      delta_map: { '0': { delta: 5 } },
      custom_projection: ['M1.arg1', 'M1.sf', 'M1.ef'],
    };
    const st = modelToState(m);
    const unassigned = st.groups.find((g) => g.name === UNASSIGNED_GROUP);
    expect(unassigned).toBeDefined();
    expect(unassigned!.intervals).toHaveLength(2);
    expect(unassigned!.ops[0].op).toBe('Bef');
    expect(unassigned!.projection).toBeNull();
  });

  it('normalizeModel migrates legacy g1/g2 groups to s1/s2', () => {
    const m: IseqlModel = {
      event_name: 'e',
      intervals: [
        { pred: { name: 'running', arguments: [] }, ts: 0, te: 10, group: 'g1' },
        { pred: { name: 'walking', arguments: [] }, ts: 0, te: 10, group: 'g2' },
      ],
      set_expression: { op: '∪', children: [{ group: 'g1' }, { group: 'g2' }] },
      delta_map: { 'g1.0': { delta: 5 } },
      operator_overrides: [{ side: 'g1', pair_idx: 1, operator: 'Bef' }],
    };
    const n = normalizeModel(m);
    const groups = n.intervals.map((iv) => iv.group);
    expect(groups).toEqual(['s1', 's2']);
    expect((n.delta_map as Record<string, unknown>)).toHaveProperty('s1.0');
    expect(n.operator_overrides?.[0].side).toBe('s1');
  });
});
