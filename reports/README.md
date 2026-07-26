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

**VIS MODE: Video Interval-based Surveillance using complex event
MOdeling and DEtection** - Crescitelli, Persia, Cipriani, Pea
(CIKM '26 demo). Prior work suffered from a zero-event bug (no object re-ID)
and unverifiable precision/recall claims on unlabeled ground truth.
This project fixes both through object re-identification and a 30-scene labeled
evaluation benchmark.

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
| `data/analysis_gemini_3_6_flash_qwen2_audio/` | Best result: Gemini 3.6 Flash + Qwen2-Audio (29/30, F1=0.892) |
| `backend/src/service/impl/events_service_impl.py` | All 16 SQL queries and EventSpec definitions |
| `backend/src/service/impl/iseql_helpers.py` | ISEQL temporal operator definitions |
