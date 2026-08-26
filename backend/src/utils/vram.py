from __future__ import annotations

from utils.api_logger import get_logger

log = get_logger(__name__)


def _dtype_bytes_per_param(config, quantization: str | None) -> float:
    """Bytes per parameter implied by the quantization mode / config dtype."""
    if quantization == "4bit":
        return 0.5
    if quantization == "8bit":
        return 1.0
    dtype = str(getattr(config, "torch_dtype", "")).lower()
    if "16" in dtype:  # float16 / bfloat16
        return 2.0
    return 4.0  # fp32


def estimate_hf_vram_bytes(model_id: str, model_cls, quantization: str | None = None,
                           safety_factor: float = 1.0) -> int:
    """Estimate the VRAM a HuggingFace model needs, without loading weights.

    Counts parameters via a meta-device instantiation (config only, no weight
    download) and scales by the dtype implied by the quantization mode plus a
    safety factor for activations / attention cache. Returns 0 on failure, so
    callers fall back to a single-GPU lease.
    """
    try:
        from accelerate import init_empty_weights
        from transformers import AutoConfig

        config = AutoConfig.from_pretrained(model_id)
        bpp = _dtype_bytes_per_param(config, quantization)
        with init_empty_weights():
            if hasattr(model_cls, "from_config"):
                model = model_cls.from_config(config)
            else:
                model = model_cls(config)
        params = int(sum(p.numel() for p in model.parameters()))
        return int(params * bpp * max(1.0, safety_factor))
    except Exception as e:
        log.warning("Could not estimate VRAM for %s: %s", model_id, e)
        return 0
