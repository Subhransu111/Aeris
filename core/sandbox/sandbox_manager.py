import uuid
import tempfile
import os
from core.sandbox.repository_manager import clone_repo
from core.sandbox.technology_detector import detect_stack
from core.sandbox.dockerfile_generator import generate_dockerfile, build_with_buildpack
from core.sandbox.image_builder import build_image
from core.sandbox.container_manager import (
    run_container, get_host_port_map, health_check, find_responsive_port, get_logs, stop_and_remove, COMMON_PORTS
)
from core.sandbox.execution_context import ExecutionContext
from core.sandbox.dependency_detector import detect_db_dependency
from core.sandbox.env_scanner import scan_env_vars, generate_env_values
from core.sandbox.network_manager import create_isolated_network, remove_network
from core.sandbox.db_provisioner import provision_database, teardown_database
from core.budget.timeout_watchdog import run_with_timeout, TimeoutException
from core.budget.cleanup_manager import full_cleanup
import docker

client = docker.from_env()

def create_sandbox(repo_url: str, context: ExecutionContext, subdirectory: str = None) -> dict:
    dest_dir = os.path.join(tempfile.gettempdir(), f"aegis_{uuid.uuid4().hex[:8]}")
    container_name = f"aegis-sandbox-{uuid.uuid4().hex[:8]}"
    container = None
    db_container = None
    network_name = None

    try:
        clone_repo(repo_url, dest_dir)
        stack = detect_stack(dest_dir, subdirectory=subdirectory)

        if stack["framework"] == "multi_service":
            full_cleanup(dest_dir)
            return {"status": "multi_service_detected", "services": stack["services"]}

        build_path = os.path.join(dest_dir, subdirectory) if subdirectory else dest_dir

        # --- NEW: detect DB dependency + env vars before building ---
        db_info = detect_db_dependency(build_path)
        env_vars_found = scan_env_vars(build_path)

        network_name = create_isolated_network()
        db_host = None

        if db_info:
            db_result = provision_database(db_info, network_name)
            db_container = db_result["container"]
            db_host = db_result["hostname"]

        app_port = "5000"
        env_values = generate_env_values(env_vars_found, db_info, db_host, app_port=app_port)
        # write .env file into build context so it's picked up at container start
        env_file_path = os.path.join(build_path, ".env")
        with open(env_file_path, "w") as f:
            for k, v in env_values.items():
                f.write(f"{k}={v}\n")

        gen_result = generate_dockerfile(build_path, stack)
        if gen_result["method"] == "failed":
            full_cleanup(dest_dir)
            if db_container: teardown_database(db_container)
            if network_name: remove_network(network_name)
            return {"status": "failed", "reason": "unsupported_stack_no_dockerfile", "stack": stack}

        if gen_result["method"] == "buildpack":
            build_result = run_with_timeout(
                build_with_buildpack, args=(build_path, container_name),
                kwargs={"timeout_seconds": context.timeout_seconds},
                timeout_seconds=context.timeout_seconds
            )
            if not build_result["success"]:
                full_cleanup(dest_dir, image_tag=container_name)
                if db_container: teardown_database(db_container)
                if network_name: remove_network(network_name)
                return {"status": "build_failed", "method": "buildpack", "logs": build_result["logs"]}
            image_id = container_name
            candidate_ports = COMMON_PORTS
        else:
            dockerfile_path = gen_result["dockerfile_path"]
            image, build_logs = run_with_timeout(
                build_image, args=(build_path, dockerfile_path, container_name),
                timeout_seconds=context.timeout_seconds
            )
            image_id = image.id
            candidate_ports = list(set(COMMON_PORTS + [int(app_port)]))
        
        
        container = run_container(image_id, container_name, candidate_ports, context, network_name=network_name)
        
        import time as _t
        _t.sleep(2)
        from core.sandbox.container_manager import get_container_status
        status_info = get_container_status(container)
        if status_info["status"] != "running":
            crash_logs = get_logs(container)
            full_cleanup(dest_dir, container=container, image_tag=container_name)
            if db_container: teardown_database(db_container)
            if network_name: remove_network(network_name)
            return {"status": "crashed_immediately", "container_status": status_info, "logs": crash_logs}
        
        host_port_map = get_host_port_map(container, candidate_ports)

        if len(candidate_ports) == 1 and candidate_ports[0] in host_port_map:
            host_port = host_port_map[candidate_ports[0]]
            healthy = health_check(host_port, timeout_seconds=60)
        else:
            host_port = find_responsive_port(host_port_map, timeout_seconds=60)
            healthy = host_port is not None

        if not healthy:
            runtime_logs = get_logs(container)
            full_cleanup(dest_dir, container=container, image_tag=container_name)
            if db_container: teardown_database(db_container)
            if network_name: remove_network(network_name)
            return {"status": "unhealthy", "runtime_logs": runtime_logs}

        return {
            "status": "running",
            "container": container,
            "container_id": container.id,
            "host_port": host_port,
            "stack": stack,
            "db_container": db_container,
            "network_name": network_name,
            "dest_dir": dest_dir,
            "image_tag": container_name
        }

    except TimeoutException as e:
        full_cleanup(dest_dir, container=container, image_tag=container_name)
        if db_container: teardown_database(db_container)
        if network_name: remove_network(network_name)
        return {"status": "timeout", "reason": str(e)}

    except Exception as e:
        full_cleanup(dest_dir, container=container, image_tag=container_name)
        if db_container: teardown_database(db_container)
        if network_name: remove_network(network_name)
        return {"status": "error", "reason": str(e)}


def teardown_sandbox(result: dict):
    full_cleanup(result.get("dest_dir"), container=result.get("container"), image_tag=result.get("image_tag"))
    if result.get("db_container"):
        teardown_database(result["db_container"])
    if result.get("network_name"):
        remove_network(result["network_name"])