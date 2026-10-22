import re
import subprocess
from pathlib import Path


def read_number(path: Path) -> float | None:
    try:
        return float(path.read_text())
    except (OSError, ValueError):
        return None


def get_nvidia_gpus() -> list[dict]:
    query = "index,name,utilization.gpu,memory.used,memory.total,temperature.gpu"
    try:
        out = subprocess.run(
            ["nvidia-smi", f"--query-gpu={query}", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        ).stdout
    except (FileNotFoundError, subprocess.SubprocessError):
        return []

    gpus = []
    for line in out.strip().splitlines():
        index, name, util, mem_used, mem_total, temp = [v.strip() for v in line.split(",")]
        gpus.append(
            {
                "index": int(index),
                "name": name,
                "usage_percent": float(util),
                "memory_used_mb": float(mem_used),
                "memory_total_mb": float(mem_total),
                "temperature_c": float(temp),
            }
        )
    return gpus


def get_amd_gpus() -> list[dict]:
    mb = lambda b: round(b / 1024**2) if b is not None else None
    gpus = []
    for card in sorted(Path("/sys/class/drm").glob("card*")):
        dev = card / "device"
        if not re.fullmatch(r"card\d+", card.name) or not (dev / "gpu_busy_percent").exists():
            continue

        temp = read_number(next(dev.glob("hwmon/hwmon*/temp1_input"), Path("/nonexistent")))
        gpus.append(
            {
                "index": int(card.name[4:]),
                "name": f"AMD GPU ({card.name})",
                "usage_percent": read_number(dev / "gpu_busy_percent"),
                "memory_used_mb": mb(read_number(dev / "mem_info_vram_used")),
                "memory_total_mb": mb(read_number(dev / "mem_info_vram_total")),
                "temperature_c": temp / 1000 if temp is not None else None,
            }
        )
    return gpus


def get_gpus() -> list[dict]:
    return get_nvidia_gpus() or get_amd_gpus()
