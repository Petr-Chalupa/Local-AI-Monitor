import docker
from fastapi import HTTPException
from containers import docker_client, is_visible


def get_logs(container: str, tail: int) -> dict:
    try:
        c = docker_client.containers.get(container)
    except docker.errors.NotFound:
        c = None
    if c is None or not is_visible(c):
        raise HTTPException(404, f"Container '{container}' not found")
    raw = c.logs(tail=tail, timestamps=True)
    return {"container": container, "lines": raw.decode(errors="replace").splitlines()}