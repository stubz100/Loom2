"""E0 sanity matrix for the loom2 engine environment (12 §1a).

Run with the engine venv:  engine/.venv/Scripts/python.exe engine/spikes/e0_sanity.py
Writes engine/spikes/out/e0_sanity.json and prints a summary. Every timing is bracketed by
torch.cuda.synchronize() (loom lesson 3: HIP is asynchronous, unsynchronised timings lie).
"""
from __future__ import annotations

import json
import platform
import sys
import time
from pathlib import Path

import torch

OUT = Path(__file__).resolve().parent / "out" / "e0_sanity.json"
OUT.parent.mkdir(parents=True, exist_ok=True)
result: dict = {"when": time.strftime("%Y-%m-%d %H:%M:%S"), "python": sys.version.split()[0], "os": platform.platform()}


def timed(fn, iters: int = 10, warmup: int = 3) -> float:
    for _ in range(warmup):
        fn()
    torch.cuda.synchronize()
    t0 = time.perf_counter()
    for _ in range(iters):
        fn()
    torch.cuda.synchronize()
    return (time.perf_counter() - t0) / iters


def main() -> int:
    result["torch"] = torch.__version__
    result["hip"] = getattr(torch.version, "hip", None)
    result["cuda_available"] = torch.cuda.is_available()
    if not torch.cuda.is_available():
        print("FAIL: torch.cuda.is_available() is False")
        OUT.write_text(json.dumps(result, indent=2))
        return 1
    props = torch.cuda.get_device_properties(0)
    result["device"] = {
        "name": torch.cuda.get_device_name(0),
        "gcn_arch": getattr(props, "gcnArchName", None),
        "total_vram_gb": round(props.total_memory / 2**30, 2),
        "multi_processor_count": props.multi_processor_count,
    }
    free, total = torch.cuda.mem_get_info()
    result["device"]["free_vram_gb_at_start"] = round(free / 2**30, 2)
    result["cudnn_enabled"] = torch.backends.cudnn.enabled
    result["sdpa_flags"] = {
        "flash": torch.backends.cuda.flash_sdp_enabled(),
        "mem_efficient": torch.backends.cuda.mem_efficient_sdp_enabled(),
        "math": torch.backends.cuda.math_sdp_enabled(),
    }

    dev = torch.device("cuda")
    bf16 = torch.bfloat16

    # 1. bf16 GEMM throughput (rough TFLOPS)
    a = torch.randn(4096, 4096, device=dev, dtype=bf16)
    b = torch.randn(4096, 4096, device=dev, dtype=bf16)
    t = timed(lambda: a @ b)
    result["bf16_gemm_4096_tflops"] = round(2 * 4096**3 / t / 1e12, 1)

    # 2. SDPA per backend at a FLUX.2-like shape: batch 1, 24 heads, 4096 tokens, head dim 128
    from torch.nn.attention import SDPBackend, sdpa_kernel

    q = torch.randn(1, 24, 4096, 128, device=dev, dtype=bf16)
    k = torch.randn_like(q)
    v = torch.randn_like(q)
    sdpa = {}
    for name, backend in [("flash", SDPBackend.FLASH_ATTENTION), ("mem_efficient", SDPBackend.EFFICIENT_ATTENTION), ("math", SDPBackend.MATH)]:
        try:
            with sdpa_kernel(backend):
                ms = timed(lambda: torch.nn.functional.scaled_dot_product_attention(q, k, v), iters=5) * 1e3
            sdpa[name] = {"ok": True, "ms": round(ms, 2)}
        except Exception as e:  # noqa: BLE001
            sdpa[name] = {"ok": False, "error": str(e).splitlines()[0][:200]}
    result["sdpa_4096x128_bf16"] = sdpa

    # 3. fp8 scaled matmul (the path fp8-scaled FLUX.2 weights use on gfx1201)
    try:
        x = torch.randn(1024, 2048, device=dev, dtype=bf16).to(torch.float8_e4m3fn)
        w = torch.randn(4096, 2048, device=dev, dtype=bf16).to(torch.float8_e4m3fn)
        sx = torch.tensor(1.0, device=dev)
        sw = torch.tensor(1.0, device=dev)
        y = torch._scaled_mm(x, w.t(), scale_a=sx, scale_b=sw, out_dtype=bf16)
        torch.cuda.synchronize()
        result["fp8_scaled_mm"] = {"ok": bool(torch.isfinite(y).all().item()), "shape": list(y.shape)}
    except Exception as e:  # noqa: BLE001
        result["fp8_scaled_mm"] = {"ok": False, "error": str(e).splitlines()[0][:200]}

    # 4. fp8 cast round-trip (the 7.14.1-nightly text-encoder regression)
    try:
        z = torch.randn(4096, 4096, device=dev, dtype=bf16)
        z8 = z.to(torch.float8_e4m3fn)
        back = z8.to(bf16)
        torch.cuda.synchronize()
        result["fp8_cast_roundtrip"] = {"ok": True, "max_abs_err": round((z - back).abs().max().item(), 3)}
    except Exception as e:  # noqa: BLE001
        result["fp8_cast_roundtrip"] = {"ok": False, "error": str(e).splitlines()[0][:200]}

    # 5. conv path (VAE-like) with cudnn/MIOpen on vs off
    conv = torch.nn.Conv2d(128, 128, 3, padding=1).to(dev, bf16)
    img = torch.randn(1, 128, 512, 512, device=dev, dtype=bf16)
    convres = {}
    for flag in (False, True):
        torch.backends.cudnn.enabled = flag
        try:
            ms = timed(lambda: conv(img), iters=5, warmup=2) * 1e3
            convres["miopen_on" if flag else "miopen_off"] = {"ok": True, "ms": round(ms, 2)}
        except Exception as e:  # noqa: BLE001
            convres["miopen_on" if flag else "miopen_off"] = {"ok": False, "error": str(e).splitlines()[0][:200]}
    torch.backends.cudnn.enabled = False
    result["conv3x3_128ch_512px"] = convres

    free, _ = torch.cuda.mem_get_info()
    result["device"]["free_vram_gb_at_end"] = round(free / 2**30, 2)
    OUT.write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
