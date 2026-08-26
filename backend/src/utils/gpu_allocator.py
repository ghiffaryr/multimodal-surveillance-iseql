from __future__ import annotations

import itertools
import threading

_GIB = 1024 ** 3


def _detect_cuda_devices() -> list[int]:
    """Return the visible CUDA device indices (respects CUDA_VISIBLE_DEVICES)."""
    try:
        import torch
    except ImportError:
        return []
    if not torch.cuda.is_available():
        return []
    return list(range(torch.cuda.device_count()))


def _resolve_indices(devices) -> list[int]:
    """Normalise a config ``gpu.devices`` value into a list of CUDA indices.

    Accepts ``"auto"``/``None`` (all visible GPUs), a single int/str, or an
    iterable of ints/strs. An empty result means CPU-only.
    """
    if devices is None or devices == "auto":
        return _detect_cuda_devices()
    if isinstance(devices, int):
        return [devices]
    if isinstance(devices, str):
        devices = devices.replace(",", " ").split()
    try:
        return [int(d) for d in devices]
    except (TypeError, ValueError):
        return []


class GpuAllocator:
    """VRAM-driven, thread-safe lease of GPU devices.

    Each analysis asks for an estimated VRAM budget and the allocator hands out
    the fewest devices needed to satisfy it -- one GPU when the model fits,
    sharded across several when it does not. A lease spans the whole device
    (no co-location), so concurrency is bounded naturally by available VRAM.
    """

    def __init__(self, devices, max_memory_fraction: float) -> None:
        self._indices = _resolve_indices(devices)
        self._fraction = max(0.1, min(1.0, float(max_memory_fraction)))
        self._cpu_only = not self._indices
        self._free: list[int] = list(self._indices)
        self._leases: dict[int, list[int]] = {}
        self._counter = itertools.count()
        self._cond = threading.Condition()
        self._cpu_sem = threading.BoundedSemaphore(1) if self._cpu_only else None

    @property
    def device_indices(self) -> list[int]:
        return list(self._indices)

    @property
    def cpu_only(self) -> bool:
        return self._cpu_only

    def _device_capacity(self, idx: int) -> int:
        import torch

        total = torch.cuda.get_device_properties(idx).total_memory
        return int(total * self._fraction)

    def total_capacity(self) -> int:
        if self._cpu_only:
            return 0
        return sum(self._device_capacity(i) for i in self._indices)

    def _pick_fewest(self, required_bytes: int, exhausted: bool) -> list[int] | None:
        if exhausted:
            # Needs every device; only grant the lease once nothing else is running.
            if len(self._free) == len(self._indices):
                return list(self._indices)
            return None
        free = list(self._free)
        # Prefer a single GPU that fits, taking the smallest such device so the
        # bigger ones stay free for bigger models.
        single = [i for i in free if self._device_capacity(i) >= required_bytes]
        if single:
            return [min(single, key=self._device_capacity)]
        # Otherwise shard: grab the largest devices first until the budget is met.
        chosen: list[int] = []
        total = 0
        for i in sorted(free, key=lambda i: -self._device_capacity(i)):
            chosen.append(i)
            total += self._device_capacity(i)
            if total >= required_bytes:
                return chosen
        return None

    def acquire_for_vram(self, required_bytes: int) -> tuple[list[str], int, bool]:
        """Block until enough free VRAM is available; return (devices, token, offload).

        ``offload`` is True when even all devices combined fall short of the
        request, so the model must spill the remainder to CPU RAM.
        """
        required_bytes = max(0, int(required_bytes or 0))
        if self._cpu_only:
            self._cpu_sem.acquire()
            return (["cpu"], next(self._counter), False)

        exhausted = required_bytes > self.total_capacity()
        with self._cond:
            while True:
                chosen = self._pick_fewest(required_bytes, exhausted)
                if chosen is not None:
                    break
                self._cond.wait()
            token = next(self._counter)
            self._leases[token] = chosen
            for d in chosen:
                self._free.remove(d)
        return ([f"cuda:{d}" for d in chosen], token, exhausted)

    def release(self, token: int) -> None:
        if self._cpu_only:
            self._cpu_sem.release()
            return
        with self._cond:
            got = self._leases.pop(token, None)
            if got is not None:
                self._free.extend(got)
                self._free.sort()
                self._cond.notify_all()


def _system_ram_gib() -> int:
    import os

    return max(1, int(os.sysconf("SC_AVPHYS_PAGES") * os.sysconf("SC_PAGE_SIZE") / _GIB))


def build_device_map(devices: list[str], max_memory_fraction: float,
                     allow_cpu_offload: bool = False):
    """Build an Accelerate device_map + max_memory for a leased device set.

    Returns ``(device, max_memory)`` where ``device`` is either a single
    ``"cuda:i"`` string (one GPU) or ``"auto"`` (shard across the leased set),
    and ``max_memory`` is the per-GPU VRAM budget (plus a ``"cpu"`` entry when
    ``allow_cpu_offload`` is set). ``(None, None)`` means run on CPU.
    """
    cudas = [d for d in (devices or []) if str(d).startswith("cuda")]
    if not cudas:
        return None, None
    if len(cudas) == 1 and not allow_cpu_offload:
        return cudas[0], None

    import torch

    max_memory: dict = {}
    for d in cudas:
        idx = int(str(d).split(":")[1])
        total = torch.cuda.get_device_properties(idx).total_memory
        budget = int(total * max(0.1, min(1.0, max_memory_fraction)) / _GIB)
        max_memory[idx] = f"{budget}GiB"
    if allow_cpu_offload:
        max_memory["cpu"] = f"{_system_ram_gib()}GiB"
    return "auto", max_memory
