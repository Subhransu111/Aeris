import docker
import uuid
import time

client = docker.from_env()

def provision_database(db_info: dict, network_name: str) -> dict:
    container_name = f"aegis-db-{uuid.uuid4().hex[:8]}"
    container = client.containers.run(
        db_info["image"],
        name=container_name,
        detach=True,
        network=network_name,
        mem_limit="256m",
    )
    time.sleep(5)  # give DB time to initialize before app connects
    return {"container": container, "hostname": container_name}

def teardown_database(container):
    try:
        container.stop(timeout=5)
        container.remove()
    except Exception:
        pass