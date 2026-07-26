"""
Generate evaluation notebooks for each audio model.
Run: python experiments/notebooks/generate_notebooks.py
"""
import json
import re
import openpyxl
from pathlib import Path


def _find_root():
    for p in [Path.cwd()] + list(Path.cwd().parents):
        if (p / ".gitignore").exists():
            return p
    return Path.cwd()

PROJECT_ROOT = _find_root()
ROOT = PROJECT_ROOT  # shorthand for use inside f-strings below
NB_DIR = ROOT / "experiments/notebooks"
NB_DIR.mkdir(parents=True, exist_ok=True)

def _load_ground_truth():
    wb = openpyxl.load_workbook(ROOT / "data/videos/eval/ground_truth.xlsx")
    ws = wb.active
    gt = {}
    for row in ws.iter_rows(min_row=2, values_only=True):
        scene, modality, cls, _, _, start_time, end_time, desc = row
        if modality != "audio":
            continue
        safe_cls = cls.replace(" ", "_")
        fname = f"scene{int(scene)}_{safe_cls}_{start_time:.3f}-{end_time:.3f}.wav"
        gt[fname] = cls
    return gt

GROUND_TRUTH = _load_ground_truth()

CLASSES = sorted({v for v in GROUND_TRUTH.values()})

_GT_LABELS = sorted(set(GROUND_TRUTH.values()), key=len, reverse=True)

# --- synonym resolution (shared by all notebooks) ---
_RE_KEEP = re.compile(r"[^a-zA-Z0-9_ ]+")

def _stem(word: str) -> str:
    w = word.lower().strip("_.,;:!?")
    for suf in ["ing", "ed", "ly", "s", "es", "ies", "ness", "tion"]:
        if w.endswith(suf) and len(w) > len(suf) + 2:
            return w[: -len(suf)]
    return w

_GT_KEYWORDS = {
    "scream":          {"scream"},
    "shout":           {"shout", "yell"},
    "impact":          {"impact", "thump", "thud", "bang", "slam", "smash", "crash", "punch", "hit"},
    "gunshot_or_explosion": {"gunshot", "gunfire", "artillery_fire", "artillery", "explosion", "explosive", "firework", "boom"},
    "engine":          {"engine", "vehicle", "car"},
    "tire_squeal":     {"tire", "tyre", "tire_squeal", "screech", "squeal"},
    "skidding":        {"skidding", "skid"},
    "glass_breaking":  {"glass", "glass_breaking", "shatter", "shattering"},
    "horn":        {"horn", "honk", "honking"},
}

_SYNONYM_LOOKUP: dict[str, str] = {}
for gt, kws in _GT_KEYWORDS.items():
    for kw in kws:
        _SYNONYM_LOOKUP[kw] = gt
        _SYNONYM_LOOKUP[_stem(kw)] = gt

TIRE_SQUEAL_KWS = _GT_KEYWORDS["tire_squeal"]
HORN_KWS = _GT_KEYWORDS["horn"]

def _resolve_label(text: str) -> str | None:
    clean = _RE_KEEP.sub(" ", text or "").lower()
    clean = " ".join(clean.split())
    if not clean:
        return None
    tokens = [t.strip("_.,;:!?'\"") for t in re.split(r"[_ ,;:\-]+", clean)]
    tokens = [t for t in tokens if len(t) >= 2]
    if not tokens:
        return None
    # Priority: if any token is a tire_squeal keyword, resolve to tire_squeal
    for token in tokens:
        if token in TIRE_SQUEAL_KWS or _stem(token) in TIRE_SQUEAL_KWS:
            return "tire_squeal"
    # Priority: if any token is a horn keyword, resolve to horn
    for token in tokens:
        if token in HORN_KWS or _stem(token) in HORN_KWS:
            return "horn"
    fallback = tokens[0]
    for token in tokens:
        if token in _SYNONYM_LOOKUP:
            return _SYNONYM_LOOKUP[token]
        s = _stem(token)
        if s in _SYNONYM_LOOKUP:
            return _SYNONYM_LOOKUP[s]
        if token in _GT_LABELS:
            return token
    return fallback


_SYNONYM_NOTEBOOK_CODE = '''
import re

_RE_KEEP = re.compile(r"[^a-zA-Z0-9_ ]+")

def _stem(word: str) -> str:
    w = word.lower().strip("_.,;:!?")
    for suf in ["ing", "ed", "ly", "s", "es", "ies", "ness", "tion"]:
        if w.endswith(suf) and len(w) > len(suf) + 2:
            return w[:-len(suf)]
    return w

_GT_KEYWORDS = {
    "scream":          {"scream"},
    "shout":           {"shout", "yell"},
    "impact":          {"impact", "thump", "thud", "bang", "slam", "smash", "crash", "punch", "hit"},
    "gunshot_or_explosion": {"gunshot", "gunfire", "artillery_fire", "artillery", "explosion", "explosive", "firework", "boom"},
        "tire_squeal":     {"tire", "tyre", "tire_squeal", "screech", "squeal"},
    "skidding":        {"skidding", "skid"},
    "glass_breaking":  {"glass", "glass_breaking", "shatter", "shattering"},
    "horn":        {"horn", "honk", "honking"},
}

_SYNONYM_LOOKUP: dict[str, str] = {}
for gt, kws in _GT_KEYWORDS.items():
    for kw in kws:
        _SYNONYM_LOOKUP[kw] = gt
        _SYNONYM_LOOKUP[_stem(kw)] = gt

TIRE_SQUEAL_KWS = _GT_KEYWORDS["tire_squeal"]
HORN_KWS = _GT_KEYWORDS["horn"]

def _resolve_label(text: str) -> str | None:
    clean = _RE_KEEP.sub(" ", text or "").lower()
    clean = " ".join(clean.split())
    if not clean:
        return None
    tokens = [t.strip("_.,;:!?'\\"") for t in re.split(r"[_ ,;:\-]+", clean)]
    tokens = [t for t in tokens if len(t) >= 2]
    if not tokens:
        return None
    # Priority: if any token is a tire_squeal keyword, resolve to tire_squeal
    for token in tokens:
        if token in TIRE_SQUEAL_KWS or _stem(token) in TIRE_SQUEAL_KWS:
            return "tire_squeal"
    # Priority: if any token is a horn keyword, resolve to horn
    for token in tokens:
        if token in HORN_KWS or _stem(token) in HORN_KWS:
            return "horn"
    fallback = tokens[0]
    for token in tokens:
        if token in _SYNONYM_LOOKUP:
            return _SYNONYM_LOOKUP[token]
        s = _stem(token)
        if s in _SYNONYM_LOOKUP:
            return _SYNONYM_LOOKUP[s]
        if token in _GT_LABELS:
            return token
    return fallback
'''


def cell(cell_type, source, outputs=None):
    lines = source.splitlines(keepends=True) if isinstance(source, str) else source
    c = {"cell_type": cell_type, "metadata": {}, "source": lines}
    if cell_type == "code":
        c["execution_count"] = None
        c["outputs"] = outputs or []
    return c


def markdown(src):
    return cell("markdown", src)


def code(src):
    return cell("code", src)


def build_notebook(cells, kernel="python3"):
    return {
        "nbformat": 4,
        "nbformat_minor": 5,
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": kernel},
            "language_info": {"name": "python", "version": "3.10.0"},
        },
        "cells": cells,
    }


# ═══════════════════════════════════════════════════════════════
# 1. PANNs CNN14 Notebook
# ═══════════════════════════════════════════════════════════════

panns_cells = [
    markdown("""# PANNs CNN14  -  Audio Event Evaluation

Evaluates PANNs CNN14 on 9 surveillance audio clips extracted from scene videos.
Compares predictions against ground-truth labels and computes performance metrics.

**Model**: PANNs CNN14 (panns_inference.AudioTagging)
**VRAM**: ~50 MB
"""),

    code("""import json, os, re, sys, warnings
from pathlib import Path
from typing import List, Tuple

import numpy as np
import soundfile as sf
import torch
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics import confusion_matrix, classification_report, precision_recall_fscore_support

warnings.filterwarnings("ignore")
%matplotlib inline

# --- auto-detect project root ---
_root = Path.cwd()
for _p in [_root] + list(_root.parents):
    if (_p / ".gitignore").exists():
        PROJECT_ROOT = _p; break
else:
    PROJECT_ROOT = _root
del _root, _p
# --------------------------------
"""),

    code("""import re

AUDIO_DIR = PROJECT_ROOT / "data/audio/eval"
SAMPLE_RATE = 16000
PANNS_SR = 32000

GROUND_TRUTH = """ + json.dumps(GROUND_TRUTH, indent=4) + """

CLASSES = sorted(set(GROUND_TRUTH.values()))
_GT_LABELS = sorted(set(GROUND_TRUTH.values()), key=len, reverse=True)

_RE_KEEP = re.compile(r"[^a-zA-Z0-9_ ]+")

def _stem(word: str) -> str:
    w = word.lower().strip("_.,;:!?")
    for suf in ["ing", "ed", "ly", "s", "es", "ies", "ness", "tion"]:
        if w.endswith(suf) and len(w) > len(suf) + 2:
            return w[:-len(suf)]
    return w

_GT_KEYWORDS = {
    "scream":          {"scream"},
    "shout":           {"shout", "yell"},
    "impact":          {"impact", "thump", "thud", "bang", "slam", "smash", "crash", "punch", "hit"},
    "gunshot_or_explosion": {"gunshot", "gunfire", "artillery_fire", "artillery", "explosion", "explosive", "firework", "boom"},
    "engine":          {"engine", "vehicle", "car"},
    "tire_squeal":     {"tire", "tyre", "tire_squeal", "screech", "squeal"},
    "skidding":        {"skidding", "skid"},
    "glass_breaking":  {"glass", "glass_breaking", "shatter", "shattering"},
    "horn":        {"horn", "honk", "honking"},
}

_SYNONYM_LOOKUP: dict[str, str] = {}
for gt, kws in _GT_KEYWORDS.items():
    for kw in kws:
        _SYNONYM_LOOKUP[kw] = gt
        _SYNONYM_LOOKUP[_stem(kw)] = gt

TIRE_SQUEAL_KWS = _GT_KEYWORDS["tire_squeal"]
HORN_KWS = _GT_KEYWORDS["horn"]

def _resolve_label(text: str) -> str | None:
    clean = _RE_KEEP.sub(" ", text or "").lower()
    clean = " ".join(clean.split())
    if not clean:
        return None
    tokens = [t.strip("_.,;:!?'\\"") for t in re.split(r"[_ ,;:\-]+", clean)]
    tokens = [t for t in tokens if len(t) >= 2]
    if not tokens:
        return None
    # Priority: if any token is a tire_squeal keyword, resolve to tire_squeal
    for token in tokens:
        if token in TIRE_SQUEAL_KWS or _stem(token) in TIRE_SQUEAL_KWS:
            return "tire_squeal"
    # Priority: if any token is a horn keyword, resolve to horn
    for token in tokens:
        if token in HORN_KWS or _stem(token) in HORN_KWS:
            return "horn"
    fallback = tokens[0]
    for token in tokens:
        if token in _SYNONYM_LOOKUP:
            return _SYNONYM_LOOKUP[token]
        s = _stem(token)
        if s in _SYNONYM_LOOKUP:
            return _SYNONYM_LOOKUP[s]
        if token in _GT_LABELS:
            return token
    return fallback

def resample(audio: np.ndarray, sr_in: int, sr_out: int) -> np.ndarray:
    import scipy.signal
    if sr_in == sr_out:
        return audio
    n_out = int(round(len(audio) * sr_out / sr_in))
    return scipy.signal.resample(audio.astype(np.float32), n_out).astype(np.float32)
"""),

    code("""print("Loading PANNs CNN14...", flush=True)
from panns_inference import AudioTagging
_panns = AudioTagging(device="cuda" if torch.cuda.is_available() else "cpu")
_panns.model.eval()

def _panns_infer(audio_np):
    audio_t = torch.tensor(audio_np, dtype=torch.float32)
    if audio_t.dim() == 1:
        audio_t = audio_t.unsqueeze(0)
    if _panns.device != "cpu":
        audio_t = audio_t.to(_panns.device)
    with torch.no_grad():
        out = _panns.model(audio_t, None)
    return out["clipwise_output"][0].detach().cpu().tolist(), out["embedding"][0].detach().cpu().tolist()

print(f"PANNs loaded on {_panns.device}")
"""),

    code("""def predict_panns(audio_16k: np.ndarray) -> List[Tuple[str, float]]:
    audio_32k = resample(audio_16k, SAMPLE_RATE, PANNS_SR)
    if audio_32k.size < PANNS_SR // 2:
        audio_32k = np.concatenate([audio_32k, np.zeros(PANNS_SR // 2 - audio_32k.size, dtype=np.float32)])
    probs, _ = _panns_infer(audio_32k[None, :])
    if isinstance(probs, list) and probs and isinstance(probs[0], list):
        probs = probs[0]
    best_label, best_prob = None, 0.0
    for l, p in zip(_panns.labels, probs):
        if p > best_prob:
            best_label, best_prob = l, p
    pred = best_label.lower() if best_label else "none"
    print(f"  Raw: {best_label} ({best_prob:.3f})")
    return pred, best_prob

results = []

wav_files = sorted(AUDIO_DIR.glob("*.wav"))
print(f"Found {len(wav_files)} eval clips\\n")

import time
start_time = time.time()

for wf in wav_files:
    true_label = GROUND_TRUTH[wf.name]
    audio_16k, sr = sf.read(str(wf), dtype="float32")
    if audio_16k.ndim > 1:
        audio_16k = audio_16k.mean(axis=-1)

    predicted_label, top_conf = predict_panns(audio_16k)
    predicted_label = _resolve_label(predicted_label) or "none"
    top_conf = top_conf or 0.0
    correct = predicted_label == true_label

    results.append({
        "file": wf.name,
        "true": true_label,
        "predicted": predicted_label,
        "confidence": top_conf,
        "correct": correct,
    })

    mark = "[OK]" if correct else "[NO]"
    print(f"{mark:5s} {wf.name:45s} true={true_label:12s} pred={predicted_label} ({top_conf:.3f})")

elapsed = time.time() - start_time

correct = sum(1 for r in results if r["correct"])
total = len(results)
print(f"\\nAccuracy: {correct}/{total} ({100*correct//total}%)")
print(f"Total inference time: {elapsed:.1f}s ({elapsed/total:.2f}s per clip)")
"""),

    code("""print("\\n=== Classification Report ===\\n")

y_true = [r["true"] for r in results]
y_pred = [r["predicted"] if r["predicted"] in CLASSES else "other" for r in results]

all_labels = sorted(set(y_true + [l for l in y_pred if l != "other"]))
if "other" in [l for l in y_pred]:
    all_labels.append("other")

print(classification_report(y_true, y_pred, labels=all_labels, zero_division=0))

# Per-class metrics
print("\\n--- Per-Class Metrics ---")
classes_in_data = sorted(set(y_true))
for cls in classes_in_data:
    tp = sum(1 for t, p in zip(y_true, y_pred) if t == cls and p == cls)
    fp = sum(1 for t, p in zip(y_true, y_pred) if t != cls and p == cls)
    fn = sum(1 for t, p in zip(y_true, y_pred) if t == cls and p != cls)
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    support = tp + fn
    print(f"  {cls:12s}  prec={precision:.3f}  recall={recall:.3f}  f1={f1:.3f}  support={support}")
"""),

    code("""# Confusion Matrix
cm = confusion_matrix(y_true, y_pred, labels=all_labels)
plt.figure(figsize=(8, 6))
sns.heatmap(cm, annot=True, fmt="d", cmap="Blues",
            xticklabels=all_labels, yticklabels=all_labels)
plt.title("PANNs CNN14  -  Confusion Matrix")
plt.xlabel("Predicted")
plt.ylabel("True")
plt.tight_layout()
plt.savefig(PROJECT_ROOT / "experiments/notebooks/panns_confusion_matrix.png", dpi=150)
plt.show()
"""),

    code("""# Accuracy per class
classes_in_data = sorted(set(y_true))
correct_by_class = {}
total_by_class = {}
for cls in classes_in_data:
    correct_by_class[cls] = sum(1 for t, p in zip(y_true, y_pred) if t == cls and p == cls)
    total_by_class[cls] = sum(1 for t in y_true if t == cls)

fig, ax = plt.subplots(figsize=(8, 4))
x = range(len(classes_in_data))
accs = [correct_by_class[c] / total_by_class[c] * 100 for c in classes_in_data]
bars = ax.bar(x, accs, color=["#4CAF50" if a == 100 else "#FF9800" for a in accs])
ax.set_xticks(x)
ax.set_xticklabels(classes_in_data, rotation=45, ha="right")
ax.set_ylabel("Accuracy (%)")
ax.set_title("PANNs CNN14  -  Per-Class Accuracy")
ax.set_ylim(0, 110)
for bar, acc in zip(bars, accs):
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1, f"{acc:.0f}%",
            ha="center", va="bottom", fontweight="bold")
plt.tight_layout()
plt.savefig(PROJECT_ROOT / "experiments/notebooks/panns_per_class_accuracy.png", dpi=150)
plt.show()
"""),

    code("""# Metrics Summary
from sklearn.metrics import precision_recall_fscore_support

mac_p, mac_r, mac_f1, _ = precision_recall_fscore_support(y_true, y_pred, average="macro", zero_division=0)
wgt_p, wgt_r, wgt_f1, _ = precision_recall_fscore_support(y_true, y_pred, average="weighted", zero_division=0)
print("=== Metrics Summary ===")
print(f"  Macro     P={mac_p:.3f}  R={mac_r:.3f}  F1={mac_f1:.3f}")
print(f"  Weighted  P={wgt_p:.3f}  R={wgt_r:.3f}  F1={wgt_f1:.3f}")
print(f"  Accuracy: {correct}/{total} ({100*correct//total}%)")
"""),

    code("""# Detailed results table
print(f"{'File':45s} {'True':12s} {'Predicted':12s} {'Conf':6s} {'Correct':8s}")
print("-" * 85)
for r in results:
    mark = "[OK]" if r["correct"] else "[NO]"
    print(f"{r['file']:45s} {r['true']:12s} {r['predicted']:12s} {r['confidence']:.3f}  {mark:8s}")
print(f"\\nOverall: {correct}/{total} ({100*correct//total}%)")
"""),

]

# ═══════════════════════════════════════════════════════════════
# 2. Qwen2-Audio-7B Notebook
# ═══════════════════════════════════════════════════════════════

qwen_cells = [
    markdown("""# Qwen2-Audio-7B-Instruct  -  Audio Event Evaluation

Evaluates Qwen2-Audio-7B-Instruct on 9 surveillance audio clips.
Compares predictions against ground-truth labels and computes performance metrics.

**Model**: Qwen/Qwen2-Audio-7B-Instruct (4-bit quantized)
**VRAM**: ~7.6 GB
"""),

    code("""import json, os, re, sys, warnings
from pathlib import Path
from typing import List, Tuple

import numpy as np
import soundfile as sf
import torch
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics import confusion_matrix, classification_report

warnings.filterwarnings("ignore")
%matplotlib inline

# --- auto-detect project root ---
_root = Path.cwd()
for _p in [_root] + list(_root.parents):
    if (_p / ".gitignore").exists():
        PROJECT_ROOT = _p; break
else:
    PROJECT_ROOT = _root
del _root, _p
# --------------------------------
""" + _SYNONYM_NOTEBOOK_CODE + """
AUDIO_DIR = PROJECT_ROOT / "data/audio/eval"

GROUND_TRUTH = """ + json.dumps(GROUND_TRUTH, indent=4) + """

CLASSES = sorted({v for v in GROUND_TRUTH.values()})
_GT_LABELS = sorted(set(GROUND_TRUTH.values()), key=len, reverse=True)
"""),

    code("""print("Loading Qwen2-Audio-7B-Instruct (4-bit)...", flush=True)
from transformers import Qwen2AudioForConditionalGeneration, AutoProcessor, BitsAndBytesConfig

model_id = "Qwen/Qwen2-Audio-7B-Instruct"
quant = None
if torch.cuda.is_available():
    try:
        quant = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_compute_dtype=torch.float16)
    except Exception:
        pass

load_kw = {"pretrained_model_name_or_path": model_id, "device_map": "cuda:0"}
if quant:
    load_kw["quantization_config"] = quant
    load_kw["torch_dtype"] = torch.float16

os.environ["TORCH_CUDAGRAPH_STOP_GROWTH"] = "1"
_model = Qwen2AudioForConditionalGeneration.from_pretrained(**load_kw)
_processor = AutoProcessor.from_pretrained(model_id)
print(f"Qwen2-Audio loaded on {_model.device}")
"""),

    code("""sampling = False
def _qwen_predict_one(wav_path: str) -> str:
    waveform, sr = sf.read(wav_path, dtype="float32")
    if waveform.ndim > 1:
        waveform = waveform.mean(axis=-1)

    prompt = "What's that sound? Output one word or two words separated by underscore (e.g. first_second)."
    conv = [
        {'role': 'system', 'content': 'You are a helpful assistant.'},
        {"role": "user", "content": [
            {"type": "audio", "audio_url": str(wav_path)},
            {"type": "text", "text": prompt},
        ]},
    ]
    text = _processor.apply_chat_template(conv, add_generation_prompt=True, tokenize=False)
    inputs = _processor(text=text, audio=waveform, return_tensors="pt", padding=True, sampling_rate=sr)
    inputs = {k: v.to(_model.device) for k, v in inputs.items()}
    with torch.no_grad():
        if sampling:
            ids = _model.generate(**inputs, max_new_tokens=32, do_sample=True, temperature=0.8, top_p=0.9)
        else:
            ids = _model.generate(**inputs, max_new_tokens=32, do_sample=False)
    resp = _processor.batch_decode(ids[:, inputs["input_ids"].shape[1]:], skip_special_tokens=True)[0]
    return resp.strip().rstrip(".")

N_RUNS = 5

results = []
wav_files = sorted(AUDIO_DIR.glob("*.wav"))

import time
start_time = time.time()

for wf in wav_files:
    true_label = GROUND_TRUTH[wf.name]
    print(f"\\n--- {wf.name} | True: {true_label} ---")

    votes = []
    raw_outputs = []
    for i in range(N_RUNS):
        resp = _qwen_predict_one(str(wf))
        raw_outputs.append(resp)
        gt = _resolve_label(resp)
        votes.append(gt or "none")
        print(f"  [{i+1}] {resp} -> {gt}")

    predicted_label = max(set(votes), key=votes.count)
    correct = predicted_label == true_label

    results.append({
        "file": wf.name,
        "true": true_label,
        "predicted": predicted_label,
        "votes": votes,
        "raw_outputs": raw_outputs,
        "correct": correct,
    })

    mark = "[OK]" if correct else "[NO]"
    print(f"  {mark} vote={predicted_label} (true={true_label})")

elapsed = time.time() - start_time
correct = sum(1 for r in results if r["correct"])
total = len(results)
print(f"\\nAccuracy: {correct}/{total} ({100*correct//total}%)")
print(f"Total inference time: {elapsed:.1f}s ({elapsed/total:.2f}s per clip)")
"""),

    code("""print("\\n=== Classification Report ===\\n")
y_true = [r["true"] for r in results]
y_pred = [r["predicted"] if r["predicted"] in CLASSES else "other" for r in results]

all_labels = sorted(set(y_true + [l for l in y_pred if l != "other"]))
if "other" in [l for l in y_pred]:
    all_labels.append("other")

print(classification_report(y_true, y_pred, labels=all_labels, zero_division=0))

print("\\n--- Per-Class Metrics ---")
classes_in_data = sorted(set(y_true))
for cls in classes_in_data:
    tp = sum(1 for t, p in zip(y_true, y_pred) if t == cls and p == cls)
    fp = sum(1 for t, p in zip(y_true, y_pred) if t != cls and p == cls)
    fn = sum(1 for t, p in zip(y_true, y_pred) if t == cls and p != cls)
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    support = tp + fn
    print(f"  {cls:12s}  prec={precision:.3f}  recall={recall:.3f}  f1={f1:.3f}  support={support}")
"""),

    code("""# Confusion Matrix
cm = confusion_matrix(y_true, y_pred, labels=all_labels)
plt.figure(figsize=(8, 6))
sns.heatmap(cm, annot=True, fmt="d", cmap="Blues",
            xticklabels=all_labels, yticklabels=all_labels)
plt.title("Qwen2-Audio-7B  -  Confusion Matrix")
plt.xlabel("Predicted")
plt.ylabel("True")
plt.tight_layout()
plt.savefig(PROJECT_ROOT / "experiments/notebooks/qwen2_confusion_matrix.png", dpi=150)
plt.show()
"""),

    code("""# Accuracy per class
classes_in_data = sorted(set(y_true))
correct_by_class = {}
total_by_class = {}
for cls in classes_in_data:
    correct_by_class[cls] = sum(1 for t, p in zip(y_true, y_pred) if t == cls and p == cls)
    total_by_class[cls] = sum(1 for t in y_true if t == cls)

fig, ax = plt.subplots(figsize=(8, 4))
x = range(len(classes_in_data))
accs = [correct_by_class[c] / total_by_class[c] * 100 for c in classes_in_data]
bars = ax.bar(x, accs, color=["#4CAF50" if a == 100 else "#FF9800" for a in accs])
ax.set_xticks(x)
ax.set_xticklabels(classes_in_data, rotation=45, ha="right")
ax.set_ylabel("Accuracy (%)")
ax.set_title("Qwen2-Audio-7B  -  Per-Class Accuracy")
ax.set_ylim(0, 110)
for bar, acc in zip(bars, accs):
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1, f"{acc:.0f}%",
            ha="center", va="bottom", fontweight="bold")
plt.tight_layout()
plt.savefig(PROJECT_ROOT / "experiments/notebooks/qwen2_per_class_accuracy.png", dpi=150)
plt.show()
"""),

    code("""# Metrics Summary
from sklearn.metrics import precision_recall_fscore_support

mac_p, mac_r, mac_f1, _ = precision_recall_fscore_support(y_true, y_pred, average="macro", zero_division=0)
wgt_p, wgt_r, wgt_f1, _ = precision_recall_fscore_support(y_true, y_pred, average="weighted", zero_division=0)
print("=== Metrics Summary ===")
print(f"  Macro     P={mac_p:.3f}  R={mac_r:.3f}  F1={mac_f1:.3f}")
print(f"  Weighted  P={wgt_p:.3f}  R={wgt_r:.3f}  F1={wgt_f1:.3f}")
print(f"  Accuracy: {correct}/{total} ({100*correct//total}%)")
"""),

    code("""print(f"{'File':45s} {'True':12s} {'Predicted':12s} {'Correct':8s}")
print("-" * 80)
for r in results:
    mark = "[OK]" if r["correct"] else "[NO]"
    print(f"{r['file']:45s} {r['true']:12s} {r['predicted']:12s} {mark:8s}")
print(f"\\nOverall: {correct}/{total} ({100*correct//total}%)")
"""),
]

# ═══════════════════════════════════════════════════════════════
# 3. Audio Flamingo 2 (3B) Notebook
# ═══════════════════════════════════════════════════════════════

af2_cells = [
    markdown("""# Audio Flamingo 2 (3B)  -  Audio Event Evaluation

Evaluates NVIDIA Audio-Flamingo-2 (3B) on 9 surveillance audio clips.
Compares predictions against ground-truth labels and computes performance metrics.

**Model**: nvidia/audio-flamingo-2 (3B)
**Architecture**: CLAP encoder + Qwen2.5-3B LLM + cross-attention adapters
**VRAM**: ~8.6 GB
"""),

    code("""import json, os, re, sys, warnings
from pathlib import Path

import numpy as np
import soundfile as sf
import torch
import yaml
import matplotlib.pyplot as plt
import seaborn as sns
from safetensors.torch import load_file
from sklearn.metrics import confusion_matrix, classification_report

# --- auto-detect project root ---
_root = Path.cwd()
for _p in [_root] + list(_root.parents):
    if (_p / ".gitignore").exists():
        PROJECT_ROOT = _p; break
else:
    PROJECT_ROOT = _root
del _root, _p
# --------------------------------

sys.path.insert(0, str(PROJECT_ROOT / "experiments/af2_inference"))
from utils import Dict2Class, get_autocast, get_cast_dtype
from src.factory import create_model_and_transforms

os.environ["TOKENIZERS_PARALLELISM"] = "false"
warnings.filterwarnings("ignore")
%matplotlib inline
""" + _SYNONYM_NOTEBOOK_CODE + """
AUDIO_DIR = PROJECT_ROOT / "data/audio/eval"
AF2_DIR = PROJECT_ROOT / "experiments/af2_inference"
CKPT_DIR = AF2_DIR / "safe_ckpt"
CLAP_CKPT = str(AF2_DIR / "clap_ckpt" / "epoch_16.pt")

GROUND_TRUTH = """ + json.dumps(GROUND_TRUTH, indent=4) + """
CLASSES = sorted({v for v in GROUND_TRUTH.values()})
_GT_LABELS = sorted(set(GROUND_TRUTH.values()), key=len, reverse=True)

def load_audio(audio_path, clap_config):
    sr = 16000
    window_length = int(float(clap_config["window_length"]) * sr)
    window_overlap = int(float(clap_config["window_overlap"]) * sr)
    max_num_window = int(clap_config["max_num_window"])

    waveform, file_sr = sf.read(audio_path, dtype="float32")
    if waveform.ndim > 1:
        waveform = waveform.mean(axis=-1)
    waveform = waveform / max(abs(waveform.max()), abs(waveform.min()))

    if file_sr != sr:
        import scipy.signal
        n_out = int(round(len(waveform) * sr / file_sr))
        waveform = scipy.signal.resample(waveform, n_out)

    T = len(waveform)
    if T <= window_length:
        num_windows = 1
        full_length = window_length
    elif T >= (max_num_window * window_length - (max_num_window - 1) * window_overlap):
        num_windows = max_num_window
        full_length = (max_num_window * window_length - (max_num_window - 1) * window_overlap)
    else:
        num_windows = 1 + int(np.ceil((T - window_length) / float(window_length - window_overlap)))
        full_length = num_windows * window_length - (num_windows - 1) * window_overlap

    if full_length > T:
        waveform = np.append(waveform, np.zeros(int(full_length - T)))
    elif full_length < T:
        waveform = waveform[:int(full_length)]

    waveform = waveform.reshape(1, -1)
    def int16_to_float32(x):
        return (x / 32767.0).astype(np.float32)
    def float32_to_int16(x):
        x = np.clip(x, a_min=-1., a_max=1.)
        return (x * 32767.).astype(np.int16)
    waveform = torch.from_numpy(int16_to_float32(float32_to_int16(waveform))).float()

    audio_clips = []
    audio_embed_mask = torch.ones(num_windows)
    for i in range(num_windows):
        start = i * (window_length - window_overlap)
        clip = waveform[:, int(start):int(start + window_length)]
        audio_clips.append(clip)

    if len(audio_clips) > max_num_window:
        audio_clips = audio_clips[:max_num_window]
        audio_embed_mask = audio_embed_mask[:max_num_window]

    audio_clips = torch.cat(audio_clips)
    return audio_clips, audio_embed_mask
"""),

    code("""print("Loading Audio Flamingo 2 (3B)...", flush=True)
print(f"Checkpoint dir: {CKPT_DIR}")

config = yaml.load(open(AF2_DIR / "configs" / "inference.yaml"), Loader=yaml.FullLoader)
model_config = config["model_config"]
clap_config = config["clap_config"]
args = Dict2Class(config["train_config"])

model_config["cache_dir"] = str(AF2_DIR / ".cache")
clap_config["checkpoint"] = CLAP_CKPT

model, tokenizer = create_model_and_transforms(
    **model_config,
    clap_config=clap_config,
    use_local_files=args.offline,
    gradient_checkpointing=args.gradient_checkpointing,
    freeze_lm_embeddings=args.freeze_lm_embeddings,
)

device_id = 0 if torch.cuda.is_available() else "cpu"
model = model.to(device_id)
model.eval()

# Load 3B checkpoint
with open(CKPT_DIR / "metadata.json") as f:
    metadata = json.load(f)

state_dict = {}
for chunk_name in metadata:
    chunk_path = CKPT_DIR / f"{chunk_name}.safetensors"
    chunk_tensors = load_file(str(chunk_path))
    state_dict.update(chunk_tensors)
    print(f"  Loaded {chunk_name}: {len(chunk_tensors)} tensors ({chunk_path.name})")

missing_keys, unexpected_keys = model.load_state_dict(state_dict, strict=False)
print(f"Missing keys: {len(missing_keys)}, Unexpected keys: {len(unexpected_keys)}")

cast_dtype = get_cast_dtype(args.precision)
if cast_dtype is None:
    cast_dtype = torch.bfloat16
autocast = get_autocast(args.precision)

free, total = torch.cuda.mem_get_info()
print(f"VRAM: {(total-free)/1e9:.1f}/{total/1e9:.1f} GB")
print("Model ready!")
"""),

    code("""sampling = False
def _af2_predict_one() -> str:
    with torch.no_grad(), autocast():
        if sampling:
            output = model.generate(
                audio_x=audio_clips.unsqueeze(0),
                audio_x_mask=audio_embed_mask.unsqueeze(0),
                lang_x=input_ids,
                eos_token_id=tokenizer.eos_token_id,
                max_new_tokens=32,
                do_sample=True,
                temperature=0.8,
                top_p=0.9,
            )[0]
        else:
            output = model.generate(
                audio_x=audio_clips.unsqueeze(0),
                audio_x_mask=audio_embed_mask.unsqueeze(0),
                lang_x=input_ids,
                eos_token_id=tokenizer.eos_token_id,
                max_new_tokens=32,
                do_sample=False,
            )[0]
    decoded = tokenizer.decode(output).split(tokenizer.sep_token)[-1].replace(
        tokenizer.eos_token, ""
    ).replace(tokenizer.pad_token, "").replace("<|endofchunk|>", "").strip()
    return decoded

N_RUNS = 5

results = []
wav_files = sorted(AUDIO_DIR.glob("*.wav"))

import time
start_time = time.time()

for wf in wav_files:
    true_label = GROUND_TRUTH[wf.name]
    print(f"\\n--- {wf.name} | True: {true_label} ---", flush=True)

    audio_clips, audio_embed_mask = load_audio(str(wf), clap_config)
    audio_clips = audio_clips.to(device_id, non_blocking=True)
    audio_embed_mask = audio_embed_mask.to(device_id, non_blocking=True)

    prompt = "What's that sound? Output one word or two words separated by underscore (e.g. first_second)."
    sample = f"<audio>{prompt.strip()}{tokenizer.sep_token}"
    text = tokenizer(sample, max_length=512, padding="longest", truncation="only_first", return_tensors="pt")
    input_ids = text["input_ids"].to(device_id, non_blocking=True)

    votes = []
    raw_outputs = []
    for i in range(N_RUNS):
        resp = _af2_predict_one()
        raw_outputs.append(resp)
        gt = _resolve_label(resp)
        votes.append(gt or "none")
        print(f"  [{i+1}] {resp} -> {gt}")

    predicted_label = max(set(votes), key=votes.count)
    correct = predicted_label == true_label

    results.append({
        "file": wf.name,
        "true": true_label,
        "predicted": predicted_label,
        "votes": votes,
        "raw_outputs": raw_outputs,
        "correct": correct,
    })

    mark = "[OK]" if correct else "[NO]"
    print(f"  {mark} vote={predicted_label} (true={true_label})")

elapsed = time.time() - start_time
correct = sum(1 for r in results if r["correct"])
total = len(results)
print(f"\\nAccuracy: {correct}/{total} ({100*correct//total}%)")
print(f"Total inference time: {elapsed:.1f}s ({elapsed/total:.2f}s per clip)")
"""),

    code("""print("\\n=== Classification Report ===\\n")
y_true = [r["true"] for r in results]
y_pred = [r["predicted"] if r["predicted"] in CLASSES else "other" for r in results]

all_labels = sorted(set(y_true + [l for l in y_pred if l != "other"]))
if "other" in [l for l in y_pred]:
    all_labels.append("other")

print(classification_report(y_true, y_pred, labels=all_labels, zero_division=0))

print("\\n--- Per-Class Metrics ---")
classes_in_data = sorted(set(y_true))
for cls in classes_in_data:
    tp = sum(1 for t, p in zip(y_true, y_pred) if t == cls and p == cls)
    fp = sum(1 for t, p in zip(y_true, y_pred) if t != cls and p == cls)
    fn = sum(1 for t, p in zip(y_true, y_pred) if t == cls and p != cls)
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    support = tp + fn
    print(f"  {cls:12s}  prec={precision:.3f}  recall={recall:.3f}  f1={f1:.3f}  support={support}")
"""),

    code("""# Confusion Matrix
cm = confusion_matrix(y_true, y_pred, labels=all_labels)
plt.figure(figsize=(8, 6))
sns.heatmap(cm, annot=True, fmt="d", cmap="Blues",
            xticklabels=all_labels, yticklabels=all_labels)
plt.title("Audio Flamingo 2 (3B)  -  Confusion Matrix")
plt.xlabel("Predicted")
plt.ylabel("True")
plt.tight_layout()
plt.savefig(PROJECT_ROOT / "experiments/notebooks/af2_confusion_matrix.png", dpi=150)
plt.show()
"""),

    code("""# Accuracy per class
classes_in_data = sorted(set(y_true))
correct_by_class = {}
total_by_class = {}
for cls in classes_in_data:
    correct_by_class[cls] = sum(1 for t, p in zip(y_true, y_pred) if t == cls and p == cls)
    total_by_class[cls] = sum(1 for t in y_true if t == cls)

fig, ax = plt.subplots(figsize=(8, 4))
x = range(len(classes_in_data))
accs = [correct_by_class[c] / total_by_class[c] * 100 for c in classes_in_data]
bars = ax.bar(x, accs, color=["#4CAF50" if a == 100 else "#FF9800" for a in accs])
ax.set_xticks(x)
ax.set_xticklabels(classes_in_data, rotation=45, ha="right")
ax.set_ylabel("Accuracy (%)")
ax.set_title("Audio Flamingo 2 (3B)  -  Per-Class Accuracy")
ax.set_ylim(0, 110)
for bar, acc in zip(bars, accs):
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1, f"{acc:.0f}%",
            ha="center", va="bottom", fontweight="bold")
plt.tight_layout()
plt.savefig(PROJECT_ROOT / "experiments/notebooks/af2_per_class_accuracy.png", dpi=150)
plt.show()
"""),

    code("""# Metrics Summary
from sklearn.metrics import precision_recall_fscore_support

mac_p, mac_r, mac_f1, _ = precision_recall_fscore_support(y_true, y_pred, average="macro", zero_division=0)
wgt_p, wgt_r, wgt_f1, _ = precision_recall_fscore_support(y_true, y_pred, average="weighted", zero_division=0)
print("=== Metrics Summary ===")
print(f"  Macro     P={mac_p:.3f}  R={mac_r:.3f}  F1={mac_f1:.3f}")
print(f"  Weighted  P={wgt_p:.3f}  R={wgt_r:.3f}  F1={wgt_f1:.3f}")
print(f"  Accuracy: {correct}/{total} ({100*correct//total}%)")
"""),

    code("""print(f"{'File':45s} {'True':12s} {'Predicted':12s} {'Votes':30s} {'Correct':8s}")
print("-" * 110)
for r in results:
    mark = "[OK]" if r["correct"] else "[NO]"
    votes_str = ", ".join(r["votes"])
    print(f"{r['file']:45s} {r['true']:12s} {r['predicted']:12s} {votes_str:30s} {mark:8s}")
print(f"\\nOverall: {correct}/{total} ({100*correct//total}%)")
"""),
]


# ═══════════════════════════════════════════════════════════════
# 4. MiMo-Audio-7B-Instruct Notebook
# ═══════════════════════════════════════════════════════════════

mimo_cells = [
    markdown("""# MiMo-Audio-7B-Instruct  -  Audio Event Evaluation

Evaluates XiaomiMiMo/MiMo-Audio-7B-Instruct on 9 surveillance audio clips.
Compares predictions against ground-truth labels and computes performance metrics.

**Model**: XiaomiMiMo/MiMo-Audio-7B-Instruct (4-bit quantized, 8-channels audio)
**Architecture**: Qwen2-7B + 16-layer local transformer + MiMo-Audio-Tokenizer (20-level RVQ, 24kHz)
**VRAM**: ~8.0 GB (4-bit) + audio tokenizer
"""),

    code("""import json, os, re, sys, warnings
from pathlib import Path

import numpy as np
import soundfile as sf
import torch
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics import confusion_matrix, classification_report

warnings.filterwarnings("ignore")
%matplotlib inline

# --- auto-detect project root ---
_root = Path.cwd()
for _p in [_root] + list(_root.parents):
    if (_p / ".gitignore").exists():
        PROJECT_ROOT = _p; break
else:
    PROJECT_ROOT = _root
del _root, _p
# --------------------------------

MIMO_DIR = PROJECT_ROOT / "experiments/MiMo-Audio"
""" + _SYNONYM_NOTEBOOK_CODE + """
AUDIO_DIR = PROJECT_ROOT / "data/audio/eval"

GROUND_TRUTH = """ + json.dumps(GROUND_TRUTH, indent=4) + """

CLASSES = sorted({v for v in GROUND_TRUTH.values()})
_GT_LABELS = sorted(set(GROUND_TRUTH.values()), key=len, reverse=True)
"""),

    code("""print("Loading MiMo-Audio-7B-Instruct (4-bit)...", flush=True)

from mimo_audio.mimo_audio import MimoAudio
from transformers import BitsAndBytesConfig

model_path = str(MIMO_DIR / "models" / "MiMo-Audio-7B-Instruct")
tokenizer_path = str(MIMO_DIR / "models" / "MiMo-Audio-Tokenizer")

quant = None
if torch.cuda.is_available():
    quant = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_compute_dtype=torch.float16,
        bnb_4bit_quant_type="nf4",
    )

os.environ["TORCH_CUDAGRAPH_STOP_GROWTH"] = "1"
_model = MimoAudio(model_path, tokenizer_path, quantization_config=quant)
print(f"MiMo-Audio loaded on {_model.device}")

free, total = torch.cuda.mem_get_info()
print(f"VRAM: {(total-free)/1e9:.1f}/{total/1e9:.1f} GB")
"""),

    code("""def _mimo_predict_one(wav_path: str) -> str:
    prompt = "What's that sound? Output one word or two words separated by underscore (e.g. first_second)."
    resp = _model.audio_understanding_sft(str(wav_path), prompt)
    return resp.strip().rstrip(".")

N_RUNS = 5

results = []
wav_files = sorted(AUDIO_DIR.glob("*.wav"))

import time
start_time = time.time()

for wf in wav_files:
    true_label = GROUND_TRUTH[wf.name]
    print(f"\\n--- {wf.name} | True: {true_label} ---")

    votes = []
    raw_outputs = []
    for i in range(N_RUNS):
        resp = _mimo_predict_one(str(wf))
        raw_outputs.append(resp)
        gt = _resolve_label(resp)
        votes.append(gt or "none")
        print(f"  [{i+1}] {resp} -> {gt}")

    predicted_label = max(set(votes), key=votes.count)
    correct = predicted_label == true_label

    results.append({
        "file": wf.name,
        "true": true_label,
        "predicted": predicted_label,
        "votes": votes,
        "raw_outputs": raw_outputs,
        "correct": correct,
    })

    mark = "[OK]" if correct else "[NO]"
    print(f"  {mark} vote={predicted_label} (true={true_label})")

elapsed = time.time() - start_time
correct = sum(1 for r in results if r["correct"])
total = len(results)
print(f"\\nAccuracy: {correct}/{total} ({100*correct//total}%)")
print(f"Total inference time: {elapsed:.1f}s ({elapsed/total:.2f}s per clip)")
"""),

    code("""print("\\n=== Classification Report ===\\n")
y_true = [r["true"] for r in results]
y_pred = [r["predicted"] if r["predicted"] in CLASSES else "other" for r in results]

all_labels = sorted(set(y_true + [l for l in y_pred if l != "other"]))
if "other" in [l for l in y_pred]:
    all_labels.append("other")

print(classification_report(y_true, y_pred, labels=all_labels, zero_division=0))

print("\\n--- Per-Class Metrics ---")
classes_in_data = sorted(set(y_true))
for cls in classes_in_data:
    tp = sum(1 for t, p in zip(y_true, y_pred) if t == cls and p == cls)
    fp = sum(1 for t, p in zip(y_true, y_pred) if t != cls and p == cls)
    fn = sum(1 for t, p in zip(y_true, y_pred) if t == cls and p != cls)
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    support = tp + fn
    print(f"  {cls:12s}  prec={precision:.3f}  recall={recall:.3f}  f1={f1:.3f}  support={support}")
"""),

    code("""# Confusion Matrix
cm = confusion_matrix(y_true, y_pred, labels=all_labels)
plt.figure(figsize=(8, 6))
sns.heatmap(cm, annot=True, fmt="d", cmap="Blues",
            xticklabels=all_labels, yticklabels=all_labels)
plt.title("MiMo-Audio-7B  -  Confusion Matrix")
plt.xlabel("Predicted")
plt.ylabel("True")
plt.tight_layout()
plt.savefig(PROJECT_ROOT / "experiments/notebooks/mimo_confusion_matrix.png", dpi=150)
plt.show()
"""),

    code("""# Accuracy per class
classes_in_data = sorted(set(y_true))
correct_by_class = {}
total_by_class = {}
for cls in classes_in_data:
    correct_by_class[cls] = sum(1 for t, p in zip(y_true, y_pred) if t == cls and p == cls)
    total_by_class[cls] = sum(1 for t in y_true if t == cls)

fig, ax = plt.subplots(figsize=(8, 4))
x = range(len(classes_in_data))
accs = [correct_by_class[c] / total_by_class[c] * 100 for c in classes_in_data]
bars = ax.bar(x, accs, color=["#4CAF50" if a == 100 else "#FF9800" for a in accs])
ax.set_xticks(x)
ax.set_xticklabels(classes_in_data, rotation=45, ha="right")
ax.set_ylabel("Accuracy (%)")
ax.set_title("MiMo-Audio-7B  -  Per-Class Accuracy")
ax.set_ylim(0, 110)
for bar, acc in zip(bars, accs):
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1, f"{acc:.0f}%",
            ha="center", va="bottom", fontweight="bold")
plt.tight_layout()
plt.savefig(PROJECT_ROOT / "experiments/notebooks/mimo_per_class_accuracy.png", dpi=150)
plt.show()
"""),

    code("""# Metrics Summary
from sklearn.metrics import precision_recall_fscore_support

mac_p, mac_r, mac_f1, _ = precision_recall_fscore_support(y_true, y_pred, average="macro", zero_division=0)
wgt_p, wgt_r, wgt_f1, _ = precision_recall_fscore_support(y_true, y_pred, average="weighted", zero_division=0)
print("=== Metrics Summary ===")
print(f"  Macro     P={mac_p:.3f}  R={mac_r:.3f}  F1={mac_f1:.3f}")
print(f"  Weighted  P={wgt_p:.3f}  R={wgt_r:.3f}  F1={wgt_f1:.3f}")
print(f"  Accuracy: {correct}/{total} ({100*correct//total}%)")
"""),

    code("""print(f"{'File':45s} {'True':12s} {'Predicted':12s} {'Votes':30s} {'Correct':8s}")
print("-" * 110)
for r in results:
    mark = "[OK]" if r["correct"] else "[NO]"
    votes_str = ", ".join(r["votes"])
    print(f"{r['file']:45s} {r['true']:12s} {r['predicted']:12s} {votes_str:30s} {mark:8s}")
print(f"\\nOverall: {correct}/{total} ({100*correct//total}%)")
"""),
]


# ═══════════════════════════════════════════════════════════════
# Write notebooks
# ═══════════════════════════════════════════════════════════════

notebooks = {
    "panns_eval.ipynb": panns_cells,
    "qwen2_audio_eval.ipynb": qwen_cells,
    "af2_eval.ipynb": af2_cells,
    "mimo_eval.ipynb": mimo_cells,
}

for name, cells in notebooks.items():
    nb = build_notebook(cells)
    path = NB_DIR / name
    with open(path, "w") as f:
        json.dump(nb, f, indent=1)
    print(f"Wrote {path}")

print("\nDone! 3 notebooks generated.")
