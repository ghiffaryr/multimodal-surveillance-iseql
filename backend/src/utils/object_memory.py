from __future__ import annotations

import base64
import hashlib
import io
import json
import re
from pathlib import Path
from typing import Callable, Optional

import numpy as np
from PIL import Image


def _load_hf_embedder(model_id: str, device: str = "cpu") -> Callable[[list[Image.Image]], np.ndarray]:
    import torch
    from transformers import AutoImageProcessor, AutoModel

    model = AutoModel.from_pretrained(model_id)
    if device != "cpu":
        model = model.to(device)
    processor = AutoImageProcessor.from_pretrained(model_id)
    model.eval()

    dim: dict[str, int | None] = {"n": None}

    def embed(crops: list[Image.Image]) -> np.ndarray:
        if not crops:
            n = dim["n"]
            return np.zeros((0, n if n is not None else 0), dtype=np.float32)
        inputs = processor(images=crops, return_tensors="pt")
        if device != "cpu":
            inputs = {k: v.to(device) for k, v in inputs.items()}
        with torch.no_grad():
            out = model.get_image_features(**inputs)
        if hasattr(out, "pooler_output") and out.pooler_output is not None:
            emb = out.pooler_output
        else:
            emb = out.last_hidden_state[:, 0]
        emb = emb.detach().cpu().float().numpy()
        if dim["n"] is None:
            dim["n"] = emb.shape[1]
        norms = np.linalg.norm(emb, axis=-1, keepdims=True)
        return emb / np.clip(norms, 1e-6, None)

    return embed


def estimate_embedding_vram_bytes(model_id: str, safety_factor: float) -> int:
    """Estimate the VRAM the HuggingFace embedding model needs (no weight download)."""
    from transformers import AutoModel

    from utils.vram import estimate_hf_vram_bytes
    return estimate_hf_vram_bytes(model_id, AutoModel, None, safety_factor)


def _load_ollama_embedder(model_id: str, base_url: str) -> Callable[[list[Image.Image]], np.ndarray]:
    import httpx

    dim: dict[str, int | None] = {"n": None}

    def embed(crops: list[Image.Image]) -> np.ndarray:
        if not crops:
            n = dim["n"]
            return np.zeros((0, n if n is not None else 0), dtype=np.float32)
        images = []
        for c in crops:
            buf = io.BytesIO()
            c.convert("RGB").save(buf, format="PNG")
            images.append("data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii"))
        resp = httpx.post(
            f"{base_url.rstrip('/')}/api/embed",
            json={"model": model_id, "images": images},
            timeout=60.0,
        )
        resp.raise_for_status()
        data = resp.json()
        if not data.get("embeddings"):
            raise RuntimeError(
                f"Ollama embedding model '{model_id}' returned no embeddings; "
                "image embeddings require an Ollama build that accepts 'images' in /api/embed"
            )
        emb = np.asarray(data["embeddings"], dtype=np.float32)
        if dim["n"] is None:
            dim["n"] = emb.shape[1]
        norms = np.linalg.norm(emb, axis=-1, keepdims=True)
        return emb / np.clip(norms, 1e-6, None)

    return embed


_embedder_cache: dict[tuple, Callable[[list[Image.Image]], np.ndarray]] = {}


def _get_embedder(provider: str, model: str,
                  ollama_base_url: str = "http://localhost:11434",
                  device: str = "cpu") -> Callable[[list[Image.Image]], np.ndarray]:
    if not provider:
        raise ValueError("embedding provider is required (huggingface or ollama)")
    if not model:
        raise ValueError("embedding model is required (e.g. an HF id or an ollama model)")
    provider = provider.lower()
    # Cache per device: a model pinned to one GPU cannot be reused from another.
    key = (provider, model, device if provider == "huggingface" else "",
           ollama_base_url if provider == "ollama" else "")
    if key not in _embedder_cache:
        if provider == "huggingface":
            _embedder_cache[key] = _load_hf_embedder(model, device=device)
        elif provider == "ollama":
            _embedder_cache[key] = _load_ollama_embedder(model, ollama_base_url)
        else:
            raise ValueError(
                f"unsupported embedding provider '{provider}' (supported: huggingface, ollama)"
            )
    return _embedder_cache[key]


def crop_from_blocks(
    frame_orig: Image.Image, blocks: list[int], grid_rows: int, grid_cols: int
) -> Image.Image:
    """Bounding box = union of the grid-block rectangles the object occupies."""
    w, h = frame_orig.size
    bw, bh = w // max(grid_cols, 1), h // max(grid_rows, 1)
    xs1, ys1, xs2, ys2 = w, h, 0, 0
    for b in blocks or []:
        try:
            b = int(b)
        except (TypeError, ValueError):
            continue
        col = (b - 1) % grid_cols
        row = (b - 1) // grid_cols
        x1, y1 = col * bw, row * bh
        x2, y2 = min(x1 + bw, w), min(y1 + bh, h)
        xs1, ys1 = min(xs1, x1), min(ys1, y1)
        xs2, ys2 = max(xs2, x2), max(ys2, y2)
    if xs2 <= xs1 or ys2 <= ys1:
        return frame_orig
    return frame_orig.crop((xs1, ys1, xs2, ys2))


class ObjectMemory:
    """Persistent per-analysis object history backed by Chroma + image
    embeddings (HuggingFace transformers locally, or Ollama). One collection per
    analysis; one entry per (frame, object) detection. Used both to bound the
    VLM tracking prompt (recency + top-k similar from all other frames) and to
    surface stored history to the frontend viewer."""

    def __init__(self, db_dir: str | Path = "data/vector_db",
                 embed_provider: str | None = None,
                 embed_model: str | None = None,
                 ollama_base_url: str = "http://localhost:11434",
                 device: str = "cpu"):
        self.db_dir = Path(db_dir)
        self.db_dir.mkdir(parents=True, exist_ok=True)
        import chromadb

        self._client = chromadb.PersistentClient(path=str(self.db_dir))
        self._embed_provider = embed_provider
        self._embed_model = embed_model
        self._ollama_base_url = ollama_base_url
        self._device = device

    def _embed(self, crops: list[Image.Image]) -> np.ndarray:
        return _get_embedder(self._embed_provider, self._embed_model,
                             self._ollama_base_url, device=self._device)(crops)

    def _collection(self, analysis_id: str):
        name = self._safe_name(analysis_id)
        return self._client.get_or_create_collection(
            name, metadata={"hnsw:space": "cosine"}
        )

    @staticmethod
    def _safe_name(analysis_id: str) -> str:
        name = analysis_id or "unnamed"
        if len(name) < 3 or not re.fullmatch(r"[a-zA-Z0-9._-]+", name):
            digest = hashlib.sha256(name.encode()).hexdigest()[:16]
            name = f"objmem_{digest}"
        return name

    def clear(self, analysis_id: str) -> None:
        try:
            self._client.delete_collection(self._safe_name(analysis_id))
        except Exception:
            pass

    def save_frame(
        self,
        analysis_id: str,
        frame: int,
        objects: list[dict],
        grid_rows: int,
        grid_cols: int,
        frame_orig: Image.Image,
        log: Callable[[str], None] = print,
    ) -> None:
        rows = [o for o in objects if o.get("blocks")]
        if not rows:
            return
        try:
            crops = [
                crop_from_blocks(frame_orig, o.get("blocks") or [], grid_rows, grid_cols)
                for o in rows
            ]
            embeddings = self._embed(crops)
        except Exception as e:
            log(f"Object memory: skipping embedding save (frame {frame}): {e}")
            return
        ids, docs, metadatas = [], [], []
        for o, emb in zip(rows, embeddings):
            cid = int(o.get("db_id", 0))
            blocks = [int(b) for b in (o.get("blocks") or [])]
            ids.append(f"{analysis_id}:{frame}:{cid}")
            docs.append(
                f"ID {cid}, Class {o.get('class')}, {o.get('description')}, "
                f"Blocks {blocks}, Frame {frame}"
            )
            metadatas.append(
                {
                    "aid": analysis_id,
                    "frame": int(frame),
                    "class_id": cid,
                    "class": o.get("class", ""),
                    "blocks": json.dumps(blocks),
                    "description": o.get("description", ""),
                }
            )
        if ids:
            self._collection(analysis_id).upsert(
                ids=ids, embeddings=[e.tolist() for e in embeddings],
                documents=docs, metadatas=metadatas,
            )

    def get_embedding(self, analysis_id: str, frame: int, object_id) -> Optional[np.ndarray]:
        got = self._collection(analysis_id).get(
            ids=[f"{analysis_id}:{int(frame)}:{int(object_id)}"], include=["embeddings"]
        )
        if got["ids"]:
            embs = got["embeddings"]
            if embs is not None and len(embs) > 0:
                return np.asarray(embs[0], dtype=np.float32)
        return None

    def query_similar(
        self,
        analysis_id: str,
        query_embeddings: list[np.ndarray],
        top_k: int = 5,
        exclude_frame: Optional[int] = None,
    ) -> list[dict]:
        if not query_embeddings:
            return []
        col = self._collection(analysis_id)
        where: dict = {"aid": analysis_id}
        if exclude_frame is not None:
            where = {
                "$and": [{"aid": analysis_id}, {"frame": {"$lt": int(exclude_frame)}}]
            }
        res = col.query(
            query_embeddings=np.asarray(query_embeddings, dtype=np.float32),
            n_results=max(top_k, 1),
            where=where,
        )
        best: dict[int, tuple[str, float]] = {}
        for ids, dists in zip(res["ids"], res["distances"]):
            for full, d in zip(ids, dists):
                if full is None:
                    continue
                class_id = int(full.rsplit(":", 1)[-1])
                if class_id not in best or d < best[class_id][1]:
                    best[class_id] = (full, d)
        ranked = sorted(best.items(), key=lambda kv: kv[1][1])[:top_k]
        if not ranked:
            return []
        top_ids = [full for _, (full, _) in ranked]
        got = col.get(ids=top_ids, include=["documents", "metadatas"])
        out = []
        for full, meta, doc in zip(got["ids"], got["metadatas"], got["documents"]):
            blocks = json.loads(meta["blocks"]) if meta.get("blocks") else []
            out.append(
                {
                    "id": int(meta["class_id"]),
                    "class": meta["class"],
                    "description": meta["description"],
                    "blocks": blocks,
                    "frame": meta["frame"],
                    "document": doc,
                }
            )
        return out

    def stats(self, analysis_id: str) -> dict:
        got = self._collection(analysis_id).get(
            where={"aid": analysis_id}, include=["metadatas"]
        )
        if not got["ids"]:
            return {"total": 0, "frame_min": None, "frame_max": None, "per_class": {}}
        metas = got["metadatas"]
        frames = [m["frame"] for m in metas]
        per_class: dict[str, int] = {}
        for m in metas:
            per_class[m["class"]] = per_class.get(m["class"], 0) + 1
        return {
            "total": len(metas),
            "frame_min": min(frames),
            "frame_max": max(frames),
            "per_class": dict(sorted(per_class.items())),
        }

    def list_entries(
        self,
        analysis_id: str,
        class_name: Optional[str] = None,
        frame_min: Optional[int] = None,
        frame_max: Optional[int] = None,
        limit: int = 200,
        offset: int = 0,
    ) -> dict:
        col = self._collection(analysis_id)
        conds = [{"aid": analysis_id}]
        if class_name:
            conds.append({"class": class_name})
        if frame_min is not None:
            conds.append({"frame": {"$gte": int(frame_min)}})
        if frame_max is not None:
            conds.append({"frame": {"$lte": int(frame_max)}})
        where = conds[0] if len(conds) == 1 else {"$and": conds}
        got = col.get(
            where=where, include=["documents", "metadatas"],
            limit=max(limit, 1), offset=max(offset, 0),
        )
        total = len(col.get(where=where, include=["metadatas"])["ids"])
        items = []
        for full, meta, doc in zip(got["ids"], got["metadatas"], got["documents"]):
            blocks = json.loads(meta["blocks"]) if meta.get("blocks") else []
            items.append(
                {
                    "id": meta["class_id"],
                    "frame": meta["frame"],
                    "class": meta["class"],
                    "blocks": blocks,
                    "description": meta["description"],
                    "document": doc,
                }
            )
        return {"items": items, "count": len(items), "total": total}
