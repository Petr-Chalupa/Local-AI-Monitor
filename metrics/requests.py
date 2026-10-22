import json
import os
import urllib.request

ENGINE_TYPE = os.getenv("MONITOR_INFERENCE_ENGINE", "llamacpp").lower()
ENGINE_URL = os.getenv("MONITOR_ENGINE_URL", "http://localhost:8080").rstrip("/")
ENGINE_API_KEY = os.getenv("MONITOR_ENGINE_API_KEY")


def fetch_url(url: str, headers: dict | None = None) -> str | None:
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=3) as resp:
            return resp.read().decode()
    except (OSError, ValueError):
        return None


def get_llamacpp_requests() -> dict | None:
    headers = {"Authorization": f"Bearer {ENGINE_API_KEY}"} if ENGINE_API_KEY else {}

    slots_text = fetch_url(f"{ENGINE_URL}/slots", headers)
    metrics_text = fetch_url(f"{ENGINE_URL}/metrics", headers)

    if slots_text is None and metrics_text is None:
        return None

    try:
        raw_slots = json.loads(slots_text or "[]")
    except ValueError:
        raw_slots = []

    metrics = {}
    for line in (metrics_text or "").splitlines():
        if line.startswith("llamacpp:"):
            name, _, value = line.partition(" ")
            try:
                metrics[name.removeprefix("llamacpp:")] = float(value)
            except ValueError:
                pass

    busy_slots = 0
    live_gen_tokens = 0

    for s in raw_slots:
        if s.get("is_processing") is True:
            busy_slots += 1
            n_dec = s.get("n_decoded")
            if n_dec is None and isinstance(s.get("next_token"), list) and len(s["next_token"]) > 0:
                n_dec = s["next_token"][0].get("n_decoded", 0)
            live_gen_tokens += n_dec or 0

    return {
        "processing": int(metrics.get("requests_processing", busy_slots)),
        "queued": int(metrics.get("requests_deferred", 0)),
        "slots_total": len(raw_slots),
        "slots_busy": busy_slots,
        "stats": {
            "gen_tokens": metrics.get("tokens_predicted_total", 0) + live_gen_tokens,
            "gen_seconds": metrics.get("tokens_predicted_seconds_total", 0),
            "prompt_tokens": metrics.get("prompt_tokens_total", 0),
            "prompt_seconds": metrics.get("prompt_seconds_total", 0),
        },
    }


def get_requests() -> dict | None:
    if ENGINE_TYPE == "llamacpp":
        return get_llamacpp_requests()
    return None
