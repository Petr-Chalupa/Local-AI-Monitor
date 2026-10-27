import socket
import docker

docker_client = docker.from_env()


def get_own_networks() -> set[str] | None:
    try:
        me = docker_client.containers.get(socket.gethostname())
    except docker.errors.NotFound:
        return None
    return set(me.attrs["NetworkSettings"]["Networks"]) - {"bridge", "host", "none"}


own_networks = get_own_networks()


def is_visible(c) -> bool:
    if own_networks is None:
        return True
    return bool(own_networks & set(c.attrs["NetworkSettings"]["Networks"]))


def get_containers() -> list[dict]:
    def get_memory_bytes(container) -> int | None:
        if container.status != "running":
            return None
        mem = container.stats(stream=False, one_shot=True).get("memory_stats", {})
        if "usage" not in mem:
            return None
        cache = mem.get("stats", {}).get("inactive_file") or mem.get("stats", {}).get("cache") or 0
        return mem["usage"] - cache

    result = []
    for c in docker_client.containers.list(all=True):
        if not is_visible(c):
            continue

        state = c.attrs["State"]
        result.append(
            {
                "name": c.name,
                "image": c.image.tags[0] if c.image.tags else c.image.short_id,
                "status": c.status,
                "health": state.get("Health", {}).get("Status"),
                "started_at": state["StartedAt"] if c.status == "running" else None,
                "exit_code": state["ExitCode"],
                "restarts": c.attrs["RestartCount"],
                "ports": sorted(f"{b['HostPort']}->{port}" for port, binds in c.ports.items() for b in binds or []),
                "memory_bytes": get_memory_bytes(c),
            }
        )
    return sorted(result, key=lambda c: c["name"])
