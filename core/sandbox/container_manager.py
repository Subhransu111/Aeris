import time
import requests
import docker

client = docker.from_env()

COMMON_PORTS = [3000, 5000, 8000, 8080, 8501, 4000, 5173]

def run_container(image_id: str, container_name: str, internal_ports: list, context, network_name: str = None):
    port_bindings = {f"{p}/tcp": None for p in internal_ports}
    run_kwargs = dict(
        detach=True,
        ports=port_bindings,
        mem_limit=f"{context.max_memory_mb}m",
        cpu_quota=int(context.max_cpu_percent * 1000),
    )
    if network_name:
        run_kwargs["network"] = network_name  # attach directly at creation
    else:
        run_kwargs["network_mode"] = "bridge"

    container = client.containers.run(image_id, name=container_name, **run_kwargs)
    return container

def get_container_status(container) -> dict:
    container.reload()
    return {
        "status": container.status,
        "exit_code": container.attrs["State"].get("ExitCode"),
        "error": container.attrs["State"].get("Error")
    }

def get_host_port_map(container, internal_ports: list) -> dict:
    time.sleep(3)  # let Docker finish registering port bindings
    container.reload()
    mapping = {}
    for p in internal_ports:
        port_data = container.attrs["NetworkSettings"]["Ports"].get(f"{p}/tcp")
        if port_data:
            mapping[p] = int(port_data[0]["HostPort"])
    return mapping

def health_check(host_port: int, timeout_seconds: int = 60) -> bool:
    url = f"http://127.0.0.1:{host_port}"
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            resp = requests.get(url, timeout=2)
            if resp.status_code < 500:
                return True
        except requests.exceptions.RequestException:
            pass
        time.sleep(2)
    return False

def find_responsive_port(host_port_map: dict, timeout_seconds: int = 60) -> int:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        for internal_port, host_port in host_port_map.items():
            try:
                resp = requests.get(f"http://127.0.0.1:{host_port}", timeout=2)
                print(f"[DEBUG] port {internal_port}->{host_port}: status {resp.status_code}")
                if resp.status_code < 500:
                    return host_port
            except requests.exceptions.RequestException as e:
                print(f"[DEBUG] port {internal_port}->{host_port}: {type(e).__name__}: {e}")
                continue
        time.sleep(2)
    return None

def get_logs(container) -> str:
    return container.logs(tail=200).decode("utf-8", errors="ignore")

def stop_and_remove(container):
    container.stop(timeout=10)
    container.remove()