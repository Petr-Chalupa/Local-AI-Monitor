from collections import deque
from datetime import datetime, timezone
from contextlib import asynccontextmanager
import os
import time
import threading

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from metrics.containers import get_containers
from metrics.gpus import get_gpus
from metrics.logs import get_logs
from metrics.requests import get_requests
from metrics.resources import get_resources

# ----- BUFFERS -----


HISTORY_SIZE = int(os.getenv("MONITOR_HISTORY_SIZE", "300"))


class RingBuffer:
    def __init__(self, max_size: int = HISTORY_SIZE):
        self._data = deque(maxlen=max_size)
        self._lock = threading.Lock()

    def add(self, item: dict) -> None:
        with self._lock:
            self._data.append(item)

    def get_latest(self) -> dict | None:
        with self._lock:
            return self._data[-1] if self._data else None

    def get_all(self) -> list[dict]:
        with self._lock:
            return list(self._data)


buffers = {name: RingBuffer() for name in ("resources", "containers", "gpus", "requests")}


def collect(name: str, data) -> dict:
    item = {"timestamp": datetime.now(timezone.utc).isoformat(), "data": data}
    buffers[name].add(item)
    return item


# ----- API -----


def collector_loop():
    while True:
        try:
            collect("resources", get_resources())
            collect("containers", get_containers())
            collect("gpus", get_gpus())
            collect("requests", get_requests())
        except Exception as e:
            print(f"Data collection failed: {e}")
        time.sleep(3)


@asynccontextmanager
async def lifespan(app: FastAPI):
    thread = threading.Thread(target=collector_loop, daemon=True)
    thread.start()
    yield


app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
def index():
    return FileResponse("static/index.html")


@app.get("/api/resources")
def resources():
    return buffers["resources"].get_latest()


@app.get("/api/containers")
def containers():
    return buffers["containers"].get_latest()


@app.get("/api/gpus")
def gpus():
    return buffers["gpus"].get_latest()


@app.get("/api/requests")
def requests():
    return buffers["requests"].get_latest()


@app.get("/api/logs")
def logs(container: str, tail: int = 100):
    return {"timestamp": datetime.now(timezone.utc).isoformat(), "data": get_logs(container, tail)}


@app.get("/api/history/{name}")
def history(name: str):
    if name not in buffers:
        raise HTTPException(404, f"Unknown source '{name}'")
    return buffers[name].get_all()


@app.get("/health")
def health():
    return {"status": "ok"}
