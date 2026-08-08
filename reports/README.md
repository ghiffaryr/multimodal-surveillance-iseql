# Papers

Manuscripts and slide outlines for the WATCHOUT ISEQL multimodal forensic surveillance project.

## Contents

| File | Description |
|------|-------------|
| `slides/slides.tex` / `slides/slides.pdf` | Defense talk (Beamer, 19 slides, compiled via \texttt{lualatex}) |
| `thesis/` | Master's thesis (LaTeX, 7 chapters) |

## Predecessor work

WATCHOUT ISEQL is the multimodal successor of the G.A.T.C.H.A. project and the
VIS MODE framework.

**VIS MODE: Complex Event Detection from VLM-Based Video Observations** - Crescitelli, Persia, Cipriani, Pea
(ECCV 2026 demo). Prior work lacked object re-identification (so tracking-dependent events went undetected) and had unverifiable precision/recall claims on unlabeled ground truth.
This project addresses both through object re-identification and a 30-scene labeled evaluation benchmark.

For the ISEQL interval-join kernel (the underlying temporal-reasoning machinery
preserved in `interval_engine/`):

> Piatov, D., Helmer, S., Dignoes, A., Persia, F. (2021). Cache-efficient
> sweeping-based interval joins for extended Allen relation predicates.
> The VLDB Journal 30(3), 379-402.
> https://doi.org/10.1007/s00778-020-00650-5

## Reference files

| File | Contents |
|------|----------|
| `experiments/evaluation_scenes.md` | Scene-by-scene prompts, ISEQL patterns, expected results |
| `data/analysis_gemini_3_6_flash_qwen2_audio/` | Best result: Gemini 3.6 Flash + Qwen2-Audio (29/30, F1=0.935) |
| `backend/src/service/impl/events_service_impl.py` | All 16 SQL queries and EventSpec definitions |
| `backend/src/service/impl/iseql_helpers.py` | ISEQL temporal operator definitions |
