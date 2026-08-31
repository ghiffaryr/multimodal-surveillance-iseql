# ISEQL Event Queries: Multimodal Surveillance

This document defines all ISEQL query expressions for the WATCHOUT ISEQL project.

### Predicate naming

Predicate names in `σ_{pred="..."}` must match the `RelationType` values in the
`VisualPerInterval` table (visual) or the `AudioClass` values in the
`AudioPerInterval` table (audio).

### Operators

| Notation | Meaning |
|----------|---------|
| `Bef(δ:N; ζ:<=, ρ:0)` | Before: gap ≤ N frames between end of first interval and start of second |
| `SP(δ:N; ζ:<=, ρ:0)` | Start Preceding: r starts no later than s and the intervals overlap |
| `EF(ε:N; η:<=, ρ:0)` | End Following: s.Te follows r.Te within N frames |
| `DJ/RDJ(δ:N, ε:N; ζ:<=, η:<=, ρ:0)` | During / Reverse-During Join |
| `LOJ/ROJ(δ:N, ε:N; ζ:<=, η:<=, ρ:0)` | Left / Right Overlap Join |
| `∨` | Logical OR (combine temporal operators or sigma conditions) |
| `∪` | Set union (multimodal: combine visual + audio results) |
| `π_{...}` | Projection (select output columns) |
| `σ_{...}` | Selection (filter matching intervals) |

Each operator always lists its full parameter set. A numeric δ/ε/ρ of `0` is written explicitly; a strictness operator is one of `<`, `<=`, `>`, `>=`; an unbounded gap is written `∞` (e.g. `Bef(δ:∞; ζ:<=, ρ:0)`).

---

## Fight

**Description:** Two or more people physically altercating. Audio: shout
followed by impact sounds within 5 seconds.

### Visual

```iseql
-- Generated ISEQL query for fight_visual
π_{M1.arg1, M1.arg2, M1.st, M1.et} (
  σ_{M1.arg1≠M1.arg2} (
  σ_{pred="physical_altercation" ∧ arg1="person" ∧ arg2="person"}(M1)))
```

### Audio

```iseql
-- Generated ISEQL query for fight_audio
π_{M1.st, M2.et} (
  σ_{pred="shout"}(M1)
  Bef(δ:5; ζ:<=, ρ:0)
  σ_{pred="impact"}(M2))
```

### Multimodal

```iseql
-- Generated ISEQL query for fight_multimodal
π_{M1.st, M2.et} (
  σ_{pred="shout"}(M1)
  Bef(δ:5; ζ:<=, ρ:0)
  σ_{pred="impact"}(M2))
∪
π_{M1.arg1, M1.arg2, M1.st, M1.et} (
  σ_{M1.arg1≠M1.arg2} (
  σ_{pred="physical_altercation" ∧ arg1="person" ∧ arg2="person"}(M1)))
```

---

## Gunshot / Explosion

**Description:** A gunshot or explosion. Simple detection, no temporal
operator needed.

### Visual

```iseql
-- Generated ISEQL query for gunshot_or_explosion_visual
π_{M1.arg1, M1.st, M1.et} (
  σ_{
    (pred="gunshot_visible" ∧ arg1="person")
    ∨
    (pred="explosion_visible" ∧ (arg1="vehicle" ∨ arg1="object"))}(M1))
```

### Audio

```iseql
-- Generated ISEQL query for gunshot_or_explosion_audio
π_{M1.st, M1.et} (
  σ_{pred="gunshot_or_explosion"}(M1))
```

### Multimodal

```iseql
-- Generated ISEQL query for gunshot_or_explosion_multimodal
π_{M1.st, M1.et} (
  σ_{pred="gunshot_or_explosion"}(M1))
∪
π_{M1.arg1, M1.st, M1.et} (
  σ_{
    (pred="gunshot_visible" ∧ arg1="person")
    ∨
    (pred="explosion_visible" ∧ (arg1="vehicle" ∨ arg1="object"))}(M1))
```

---

## Handoff

**Description:** One person carrying an object, then another person carrying
the same object. The second carrying interval follows the first (direct or
indirect package exchange). Requires different persons but same object. The
`Bef` gap is unbounded (∞).

### Visual

```iseql
-- Generated ISEQL query for handoff
π_{M1.arg1, M2.arg1, M1.arg2, M1.st, M2.et} (
  σ_{M1.arg1≠M2.arg1 ∧ M1.arg2=M2.arg2} (
      σ_{pred="carrying" ∧ arg1="person" ∧ arg2="object"}(M1)
      Bef(δ:∞; ζ:<=, ρ:0)
      σ_{pred="carrying" ∧ arg1="person" ∧ arg2="object"}(M2)))
```

The two `carrying` intervals must involve distinct persons (M1.arg1 ≠ M2.arg1)
on the same object (M1.arg2 = M2.arg2), with the second following the first
(BEFORE). The `Bef` gap is unbounded (∞).

### Audio

Not applicable: handoff has no acoustic correlate.

### Multimodal

Same as visual. Handoff is visual-only.

---

## Suspicious Near Vehicle

**Description:** A person remains suspiciously close to or inspecting a parked
vehicle for at least 3 seconds. Detected via the `suspicious_near_vehicle` visual
predicate over a single interval; the duration condition
`(M1.et − M1.st) ≥ 3` is applied in seconds.

### Visual

```iseql
-- Generated ISEQL query for suspicious_near_vehicle
π_{M1.arg1, M1.arg2, M1.st, M1.et} (
  σ_{(M1.et − M1.st) ≥ 3} (
    σ_{pred="suspicious_near_vehicle" ∧ arg1="person" ∧ arg2="vehicle"}(M1)))
```

The single `suspicious_near_vehicle` interval must pair a person (M1.arg1) with a
vehicle (M1.arg2) and last at least 3 seconds.

### Audio

Not applicable: suspicious_near_vehicle has no acoustic correlate.

### Multimodal

Same as visual. Suspicious near vehicle is visual-only.

---

## Vehicle Collision

**Description:** A vehicle with visible collision damage, or the sound of
a collision (start-preceding horn/skid followed by impact/glass breaking).

### Visual

```iseql
-- Generated ISEQL query for vehicle_collision_visual
π_{M1.arg1, M1.st, M1.et} (
  σ_{pred="vehicle_collision" ∧ arg1="vehicle"}(M1))
```

### Audio

```iseql
-- Generated ISEQL query for vehicle_collision_audio
π_{M1.st, M2.et} (
  σ_{pred="horn" ∨ pred="skidding"}(M1)
  SP(δ:∞; ζ:<=, ρ:0)
  σ_{pred="impact" ∨ pred="glass_breaking"}(M2))
```

### Multimodal

```iseql
-- Generated ISEQL query for vehicle_collision_multimodal
π_{M1.st, M2.et} (
  σ_{pred="horn" ∨ pred="skidding"}(M1)
  SP(δ:∞; ζ:<=, ρ:0)
  σ_{pred="impact" ∨ pred="glass_breaking"}(M2))
∪
π_{M1.arg1, M1.st, M1.et} (
  σ_{pred="vehicle_collision" ∧ arg1="vehicle"}(M1))
```

---

## Vehicle Escape

**Description:** A person runs and then enters/exits a vehicle (visual),
or engine sounds followed by tire squeal (audio). The person running and
entering/exiting must be the same person.

### Visual

```iseql
-- Generated ISEQL query for vehicle_escape_visual
π_{M1.arg1, M2.arg2, M1.st, M2.et} (
  σ_{M1.arg1=M2.arg1} (
    σ_{pred="running" ∧ arg1="person"}(M1)
    Bef(δ:2; ζ:<=, ρ:0)
    σ_{pred="enter_or_exit_vehicle" ∧ arg1="person" ∧ arg2="vehicle"}(M2)))
```

The running interval must finish at most 2 s before the enter/exit interval
starts (`Bef(δ:2; ζ:<=, ρ:0)`), for the same person (`M1.arg1 = M2.arg1`).

### Audio

```iseql
-- Generated ISEQL query for vehicle_escape_audio
π_{M1.st, M2.et} (
  σ_{pred="engine"}(M1)
  SP(δ:∞; ζ:<=, ρ:0)
  σ_{pred="tire_squeal"}(M2))
```

### Multimodal

```iseql
-- Generated ISEQL query for vehicle_escape_multimodal
π_{M1.st, M2.et} (
  σ_{pred="engine"}(M1)
  SP(δ:∞; ζ:<=, ρ:0)
  σ_{pred="tire_squeal"}(M2))
∪
π_{M1.arg1, M2.arg2, M1.st, M2.et} (
  σ_{M1.arg1=M2.arg1} (
    σ_{pred="running" ∧ arg1="person"}(M1)
    Bef(δ:2; ζ:<=, ρ:0)
    σ_{pred="enter_or_exit_vehicle" ∧ arg1="person" ∧ arg2="vehicle"}(M2)))
```

---

## Column Output Order

The SQL queries return columns in the order shown below. These are the actual
column names in our backend; the ISEQL `π{...}` above uses symbolic fields.

### Condition A: Visual

| Event | Column order |
|-------|-------------|
| Fight | `RelationID, StartFrame, EndFrame, PersonID, PersonID2` |
| Vehicle escape | `RelationID, StartFrame, EndFrame, PersonID, VehicleID` |
| Suspicious near vehicle | `RelationID, StartFrame, EndFrame, PersonID, VehicleID` |
| Handoff | `RelationID, StartFrame, EndFrame, GiverID, ReceiverID, ObjectID` |
| Vehicle collision | `RelationID, StartFrame, EndFrame, VehicleID` |
| Gunshot | `RelationID, StartFrame, EndFrame, ClassID` |

### Condition B: Sound

| Event | Column order |
|-------|-------------|
| Fight | `SoundIntervalID, SoundIntervalID2, StartFrame, EndFrame` |
| Gunshot | `SoundIntervalID, StartFrame, EndFrame` |
| Vehicle escape | `SoundIntervalID, SoundIntervalID2, StartFrame, EndFrame` |
| Vehicle collision | `SoundIntervalID, SoundIntervalID2, StartFrame, EndFrame` |

### Condition C: Multimodal

Each query returns one row per audio match and one row per visual match (no aggregation).

| Event | Column order |
|-------|-------------|
| Fight | `VisualRelationID, SoundIntervalID, SoundIntervalID2, StartFrame, EndFrame, PersonID, PersonID2` |
| Gunshot | `VisualRelationID, SoundIntervalID, StartFrame, EndFrame, ClassID` |
| Vehicle escape | `VisualRelationID, SoundIntervalID, SoundIntervalID2, StartFrame, EndFrame, PersonID, VehicleID` |
| Vehicle collision | `VisualRelationID, SoundIntervalID, SoundIntervalID2, StartFrame, EndFrame, VehicleID` |
| Suspicious near vehicle | `RelationID, StartFrame, EndFrame, PersonID, VehicleID` |
| Handoff | `RelationID, StartFrame, EndFrame, GiverID, ReceiverID, ObjectID` |
