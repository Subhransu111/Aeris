import docker
import uuid

client = docker.from_env()

def create_isolated_network() -> str:
    network_name = f"aegis-net-{uuid.uuid4().hex[:8]}"
    client.networks.create(network_name, driver="bridge")
    return network_name

def remove_network(network_name: str):
    try:
        network = client.networks.get(network_name)
        network.remove()
    except Exception:
        pass