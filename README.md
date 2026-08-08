# WATCHOUT ISEQL - Forensic Multimodal Surveillance

> **W**hole-scene **A**udio-visual **T**emporal **C**omplex-event
> **H**andler using **O**ntological **U**nderstanding of **T**emporal ISEQL

A multimodal forensic surveillance framework that detects events through a **three-condition ablation**:

|       | Modality        | Backend                          | Use                                                                                           |
| ----- | --------------- | -------------------------------- | --------------------------------------------------------------------------------------------- |
| **A** | Visual only     | VLM + re-ID + ISEQL (no sound)   | On-camera events requiring temporal chains (handoff, vehicle_escape)         |
| **B** | Audio only      | **PANNs CNN14** / **Qwen2-Audio-7B-Instruct** | Off-camera events the camera cannot see; distinctive sounds (gunshot, tire_squeal)    |
| **C** | Full multimodal | UNION of A and B (no temporal cross-modal JOIN) | Preserves all detections from both modalities; no recall loss from cross-modal gates          |

### Key innovations
- **First application of Large Audio-Language Model (LALM) for surveillance forensics** - Qwen2-Audio-7B-Instruct
- **Object re-identification** via VLM tracking prompt - enables tracking-dependent events (loitering, vehicle escape, handoff)
- **First labeled multimodal forensic surveillance dataset** - 30 scenes generated with Dreamina Seedance (ByteDance) Seedance 2.0, with per-frame ground truth
- **UNION-based multimodal** - C = A U B, no temporal cross-modal JOINs (which reduce recall)
- **Auditable SQL pipeline** - every event is output of a SQL query; no black-box reasoning

### Best result
> **Gemini 3.6 Flash + Qwen2-Audio-7B achieved 30/30 events (F1=0.938)**

---

## Architecture

```
                 ┌──────────────────┐
    video.mp4 ──►│  ffmpeg extract  │──►  16 kHz mono wav
                 └────────┬─────────┘
                          │
         ┌────────────────┴────────────────┐
         │  PANNs CNN14 / Qwen2-Audio      │
         │  → SoundIntervals (SQLite)       │
         └────────────────┬─────────────────┘
                          │           (condition B / C only)
    video.mp4 ──► VLM (4 models)       (condition A / C only)
                  + object re-ID
                          │
                          ▼
               ┌─────────────────────┐
               │  VisRelationIntervals│
               │  (SQLite)            │
               └────────┬─────────────┘
                        │
                        ▼
        ┌───────────────┴──────────────────┐
        │   High-level event detector       │
         │   - 6 visual SQL queries          │   condition A
         │   - 4 sound-only SQL queries      │   condition B
         │   - 6 multimodal SQL queries      │   condition C (UNION)
        └───────────────────────────────────┘
```

- **Backend**: FastAPI + Pipenv (Python 3.11)
- **Frontend**: SvelteKit + TypeScript + shadcn-svelte
- **Audio**: PANNs CNN14 (CPU, AudioSet) or Qwen2-Audio-7B-Instruct (GPU, LALM)
- **VLM**: Gemini 3.6 Flash (best of 4 tested), others: Ministral 3-14B, Pixtral 12B, Gemini 2.5 Flash
- **Eval**: 3-condition harness, 30 curated scenes

---

## Object Re-Identification

Without re-ID, every VLM call assigns new IDs to the same person/vehicle. Short, single-frame intervals cannot satisfy the ISEQL duration thresholds for events that require a persistent identity over time (loitering, vehicle escape, handoff). Prior work (VIS MODE) reported zero events from this failure.

**Re-ID mechanism** (in `backend/src/service/impl/visual_service_impl.py`):

1. **First frame**: VLM detects objects, assigns numeric IDs
2. **Tracking frames**: VLM receives previous frame's ID list with class and grid-block coordinates
3. **Matching rules**:
  - Same class + overlapping blocks: same object, reuse ID
  - Same class + adjacent blocks: same object moved, reuse ID
  - Different class: never reuse ID

**Impact**: Re-ID unlocks tracking-dependent events: loitering and vehicle escape rise from 0 to 4-5 / 5 detected with Gemini 3.6 Flash, raising visual F1 from 0.72 (no re-ID) to 0.84.

---

## Evaluation Dataset

The first labeled multimodal forensic surveillance dataset, generated using Dreamina Seedance (ByteDance's text-to-video service, Seedance 2.0 model).

| Property | Value |
|----------|-------|
| Source | Dreamina Seedance (ByteDance), Seedance 2.0 |
| Scenes | 30 curated surveillance scenarios (10s each, 24 fps, 1280x720) |
| Event types | fight, gunshot_or_explosion, vehicle_escape, vehicle_collision, loitering, handoff |
| Annotations | Per-frame visual relations, audio sound classes, event-level ground truth (TP/FN/FP/TN) |
| Storage | Excel ground truth + SQLite databases per VLM/audio combination |

No public dataset existed for multimodal forensic surveillance with temporal interval annotations.

## Visual: VLM Comparison (30 scenes)

| VLM                  | Re-ID | F1     | TP | FP | FN |
|----------------------|-------|--------|----|----|----|
| **Gemini 3.6 Flash** | Yes   | **0.847** | 25 | 4  | 5  |
| Ministral 3-14B      | Yes   | 0.750  | 21 | 5  | 9  |
| Gemini 2.5 Flash     | Yes   | 0.692  | 18 | 4  | 12 |
| Pixtral 12B          | Yes   | 0.691  | 19 | 6  | 11 |

Without re-ID (ablation F1/TP): Gemini 3.6 Flash 0.706/18, Pixtral 12B 0.689/21, Ministral 3-14B 0.655/19, Gemini 2.5 Flash 0.560/14. Re-ID mainly adds loitering, vehicle escape, and handoff, which require a persistent identity over time.

---

## Audio: LALM vs CNN (14 audio-relevant scenes)

| Model             | Type    | F1     | TP | FP | FN |
|----------------------|---------|--------|----|----|----|
| **Qwen2-Audio-7B**   | **LALM**| **0.788** | 13 | 0  | 7  |
| PANNs CNN14          | CNN     | 0.429  | 6  | 2  | 14 |
This is the **first application of a Large Audio-Language Model for surveillance forensic event detection**. No prior work found on arXiv or Google Scholar.

---

## Multimodal: Ablation Results (30 scenes)

Best config per pair, ties shown (all 8 window/hop configs per pair are in `data/analysis_*/summary.xlsx`; the full ranked 64-combination ablation is in the thesis appendix):

| VLM + Audio Model                        | Best audio config | F1     | TP | FP | FN |
|------------------------------------|-------------------|--------|----|----|----|
| **Gemini 3.6 Flash + Qwen2**       | 2.5/1.25, 5.0/2.5, 5.0/5.0 | **0.938** | 30 | 4  | 0  |
| **Ministral 3-14B + Qwen2**        | 5.0/2.5, 5.0/5.0       | **0.889** | 28 | 5  | 2  |
| Gemini 3.6 Flash + PANNs           | 5.0/5.0, 10/5, 10/10   | 0.867  | 26 | 4  | 4  |
| Gemini 2.5 Flash + Qwen2           | 5.0/2.5               | 0.847  | 25 | 4  | 5  |
| Pixtral 12B + Qwen2                | 5.0/2.5, 5.0/5.0       | 0.839  | 26 | 6  | 4  |
| Ministral 3-14B + PANNs            | 5.0/5.0, 10/5, 10/10   | 0.772  | 22 | 5  | 8  |
| Gemini 2.5 Flash + PANNs           | 5.0/5.0               | 0.741  | 20 | 4  | 10 |
| Pixtral 12B + PANNs                | 5.0/5.0, 10/5, 10/10   | 0.714  | 20 | 6  | 10 |

Thesis claim C >= max(A, B) holds on all scenes across all providers.

---

## Events detected, by condition

|       | Condition       | Query set                                                                                                                    |
| ----- | --------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| **A** | Visual only     | 6 visual SQL queries (fight, vehicle_escape, loitering, handoff, vehicle_collision, gunshot_or_explosion) |
| **B** | Sound only      | 4 sound-only SQL queries (fight, gunshot_or_explosion, vehicle_escape, vehicle_collision)                                             |
| **C** | Full multimodal | 6 SQL queries (4 via UNION of AUB, 2 visual-only for events with no audio correlate) |

The full set is registered in `backend/src/service/impl/events_service_impl.py` and exposed via `GET /api/events/types`.

---

## Quick start

Requires: `cmake`, `g++`, `python3.11`, `pipenv`, `node >= 18`, `pnpm`, `ffmpeg`, `libsndfile`, `git`.

```bash
git clone <repo-url> multimodal-surveillance-iseql
cd multimodal-surveillance-iseql

make engine     # builds interval_engine/build/release/iseql
make backend    # pipenv install --dev
make frontend   # pnpm install
make local      # boots backend on :8000 and frontend on :5173
```

Then open <http://localhost:5173>, upload a video, and pick a **condition** (A / B / C).

### Docker

```bash
make engine
make docker
```

Open <http://localhost:5173>.

---

## Makefile targets

| Target             | What it does                                                   |
| ------------------ | -------------------------------------------------------------- |
| `make engine`      | Build the C++ ISEQL interval engine (Linux)                    |
| `make backend`     | Install Python deps via Pipenv                                 |
| `make frontend`    | Install JS deps via pnpm                                       |
| `make local`       | Run backend (`uvicorn`) + frontend (`vite dev`) in parallel    |
| `make docker`      | Build and run both services via `docker compose`               |
| `make test`        | Run `pytest`                                                   |
| `make clean`       | Remove build artefacts, `.db`, `node_modules`, `.venv`, models |

---

## Project layout

```
multimodal-surveillance-iseql/
├── backend/             FastAPI + Pipenv
│   └── src/
│       ├── api/             analysis, schema, events, database controllers
│       ├── models/          analysis (Condition enum)
│       ├── service/         interfaces (audio, visual, events, interval)
│       │   └── impl/        implementations + iseql_helpers
│       └── utils/           database, config, VLM client, logger
├── frontend/            SvelteKit + TypeScript + shadcn-svelte
├── experiments/         Evaluation notebooks and scene definitions
│   ├── evaluation_scenes.md
│   └── notebooks/       24 evaluation notebooks (VLM, audio, multimodal)
├── reports/
│   ├── slides/           Defense slides (Beamer)
│   └── thesis/           Master's thesis (LaTeX)
├── data/                Runtime artefacts (uploads, DBs, analysis XLSX, sound)
│   ├── analysis_*/       Per-VLM/audio ablation results
│   └── videos/eval/      30 curated evaluation scenes
├── Makefile             Root convenience
├── docker-compose.yml
└── LICENSE
```

---

## API endpoints (backend)

OpenAPI docs are auto-generated at `/docs` and `/redoc` when the backend is running.

| Method | Path                        | Purpose                                                             |
| ------ | --------------------------- | ------------------------------------------------------------------- |
| `GET`  | `/api/health`               | Liveness, includes the three conditions                             |
| `GET`  | `/api/schema`               | Table names, per-condition event catalogue                          |
| `GET`  | `/api/events/types`         | Per-condition event-type catalogue                                  |
| `POST` | `/api/analysis/start`       | Start a new analysis (multipart: video + `condition=A\|B\|C`)       |
| `GET`  | `/api/analysis/{id}/logs`   | SSE stream of stage logs                                            |
| `GET`  | `/api/analysis/{id}/status` | Current stage + condition + counters                                |
| `POST` | `/api/analysis/{id}/detect` | Run a high-level event detector (dispatches by the run's condition) |
| `GET`  | `/api/db/download`          | Stream the SQLite database                                          |
| `POST` | `/api/db/upload`            | Upload a pre-existing `.db`                                         |

---

## Attribution

- **Object re-identification** and **first LALM for surveillance**: Ghiffary R. (this thesis)
- C++ interval engine (`interval_engine/`): Piatov, Helmer, Dignoes, Persia (2021), *Cache-efficient sweeping-based interval joins for extended Allen relation predicates*, VLDB Journal 30(3), 379-402.
- VIS MODE framework (predecessor, ECCV 2026 demo): Crescitelli, Persia, Cipriani, Pea, *VIS MODE: Complex Event Detection from VLM-Based Video Observations*. Prior work suffered from zero-event bug (no re-ID, so tracking-dependent events were missed) and unverifiable claims (no labeled ground truth). This project fixes both.
- PANNs CNN14: Kong et al., *PANNs: Large-scale Pretrained Audio Neural Networks for Audio Pattern Recognition*, IEEE/ACM TASLP 2020.
- Qwen2-Audio-7B-Instruct: Chu et al., *Qwen2-Audio Technical Report*, 2024.

---

## License

Apache 2.0. See `LICENSE`.
