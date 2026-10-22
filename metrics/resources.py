import psutil


def get_resources() -> dict:
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    return {
        "cpu": {"usage_percent": psutil.cpu_percent(), "cores": psutil.cpu_count()},
        "memory": {"total_bytes": memory.total, "used_bytes": memory.used, "usage_percent": memory.percent},
        "disk": {"total_bytes": disk.total, "used_bytes": disk.used, "usage_percent": disk.percent},
    }
