import docker
from fastapi import HTTPException

docker_client = docker.from_env()


def get_logs(container: str, tail: int) -> dict:
    try:
        raw = docker_client.containers.get(container).logs(tail=tail, timestamps=True)
    except docker.errors.NotFound:
        raise HTTPException(404, f"Container '{container}' not found")
    return {"container": container, "lines": raw.decode(errors="replace").splitlines()}
