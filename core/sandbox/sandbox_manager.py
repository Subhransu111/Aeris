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
from core.sandbox.env_scanner import scan_env_vars, generate_env_values ,generate_frontend_env_values, scan_hardcoded_localhost
from core.sandbox.network_manager import create_isolated_network, remove_network
from core.sandbox.db_provisioner import provision_database, teardown_database
from core.budget.timeout_watchdog import run_with_timeout, TimeoutException
from core.budget.cleanup_manager import full_cleanup, cleanup_docker_image
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

## multi_service_sandbox :
def create_multi_service_sandbox(repo_url: str, context: ExecutionContext,
                                   frontend_subdir: str = "Frontend",
                                   backend_subdir: str = "Backend") -> dict:
    """
    Builds and runs Frontend + Backend + DB (if needed) together on one
    isolated network. Backend stays internal-only; only Frontend's port
    is exposed to the host, matching how the real app actually runs.
    """
    dest_dir = os.path.join(tempfile.gettempdir(), f"aegis_{uuid.uuid4().hex[:8]}")
    backend_container_name = f"aegis-backend-{uuid.uuid4().hex[:8]}"
    frontend_container_name = f"aegis-frontend-{uuid.uuid4().hex[:8]}"
    backend_container = None
    frontend_container = None
    db_container = None
    network_name = None

    try:
        clone_repo(repo_url, dest_dir)
        network_name = create_isolated_network()

        # ---------- Backend ----------
        backend_path = os.path.join(dest_dir, backend_subdir)
        backend_stack = detect_stack(dest_dir, subdirectory=backend_subdir)

        db_info = detect_db_dependency(backend_path)
        db_host = None
        if db_info:
            db_result = provision_database(db_info, network_name)
            db_container = db_result["container"]
            db_host = db_result["hostname"]

        backend_env_vars = scan_env_vars(backend_path)
        backend_app_port = "5000"
        backend_env_values = generate_env_values(backend_env_vars, db_info, db_host, app_port=backend_app_port)
        with open(os.path.join(backend_path, ".env"), "w") as f:
            for k, v in backend_env_values.items():
                f.write(f"{k}={v}\n")

        backend_gen = generate_dockerfile(backend_path, backend_stack)
        if backend_gen["method"] == "failed":
            raise RuntimeError(f"Backend: unsupported stack {backend_stack}")

        if backend_gen["method"] == "buildpack":
            build_result = run_with_timeout(build_with_buildpack, args=(backend_path, backend_container_name),
                                              kwargs={"timeout_seconds": context.timeout_seconds},
                                              timeout_seconds=context.timeout_seconds)
            if not build_result["success"]:
                raise RuntimeError(f"Backend build failed: {build_result['logs'][-500:]}")
            backend_image_id = backend_container_name
        else:
            image, _ = run_with_timeout(build_image, args=(backend_path, backend_gen["dockerfile_path"], backend_container_name),
                                          timeout_seconds=context.timeout_seconds)
            backend_image_id = image.id

        backend_candidate_ports = list(set(COMMON_PORTS + [int(backend_app_port)]))
        backend_container = run_container(backend_image_id, backend_container_name, backend_candidate_ports,
                                            context, network_name=network_name)
        
        backend_host_port_map = get_host_port_map(backend_container, backend_candidate_ports)
        backend_host_port = find_responsive_port(backend_host_port_map, timeout_seconds=60)

        if not backend_host_port:
            backend_logs = get_logs(backend_container)
            raise RuntimeError(f"Backend unhealthy.\nBackend logs: {backend_logs[-500:]}")
        # Backend not exposed to host - only reachable via Docker network by name

        # ---------- Frontend ----------
        frontend_path = os.path.join(dest_dir, frontend_subdir)
        frontend_stack = detect_stack(dest_dir, subdirectory=frontend_subdir)

        hardcoded_localhost_findings = scan_hardcoded_localhost(frontend_path)

        frontend_env_vars = scan_env_vars(frontend_path)
        frontend_env_values, matched_api_var = generate_frontend_env_values(
            frontend_env_vars, "127.0.0.1", backend_host_port
        )
        with open(os.path.join(frontend_path, ".env"), "w") as f:
            for k, v in frontend_env_values.items():
                f.write(f"{k}={v}\n")

        frontend_gen = generate_dockerfile(frontend_path, frontend_stack)
        if frontend_gen["method"] == "failed":
            raise RuntimeError(f"Frontend: unsupported stack {frontend_stack}")

        if frontend_gen["method"] == "buildpack":
            build_result = run_with_timeout(build_with_buildpack, args=(frontend_path, frontend_container_name),
                                              kwargs={"timeout_seconds": context.timeout_seconds},
                                              timeout_seconds=context.timeout_seconds)
            if not build_result["success"]:
                raise RuntimeError(f"Frontend build failed: {build_result['logs'][-500:]}")
            frontend_image_id = frontend_container_name
        else:
            image, _ = run_with_timeout(build_image, args=(frontend_path, frontend_gen["dockerfile_path"], frontend_container_name),
                                          timeout_seconds=context.timeout_seconds)
            frontend_image_id = image.id

        frontend_default_port = frontend_stack.get("default_port") or 3000
        frontend_candidate_ports = list(set(COMMON_PORTS + [frontend_default_port]))
        frontend_container = run_container(frontend_image_id, frontend_container_name, frontend_candidate_ports,
                                             context, network_name=network_name)

        host_port_map = get_host_port_map(frontend_container, frontend_candidate_ports)
        host_port = find_responsive_port(host_port_map, timeout_seconds=60)

        if not host_port:
            frontend_logs = get_logs(frontend_container)
            backend_logs = get_logs(backend_container)
            raise RuntimeError(f"Frontend unhealthy.\nFrontend logs: {frontend_logs[-500:]}\nBackend logs: {backend_logs[-500:]}")

        return {
            "status": "running",
            "frontend_container": frontend_container,
            "backend_container": backend_container,
            "db_container": db_container,
            "network_name": network_name,
            "host_port": host_port,
            "backend_host_port": backend_host_port,
            "dest_dir": dest_dir,
            "frontend_image_tag": frontend_container_name,
            "backend_image_tag": backend_container_name,
            "backend_internal_host": backend_container_name,
            "backend_internal_port": backend_app_port,
            "api_url_injected": matched_api_var,
            "hardcoded_localhost_warnings": hardcoded_localhost_findings,
        }

    except Exception as e:
        full_cleanup(dest_dir, container=frontend_container, image_tag=frontend_container_name)
        if backend_container:
            stop_and_remove(backend_container)
        if db_container:
            teardown_database(db_container)
        if network_name:
            remove_network(network_name)
        return {"status": "error", "reason": str(e)}


def teardown_multi_service_sandbox(result: dict):
    full_cleanup(result.get("dest_dir"), container=result.get("frontend_container"), image_tag=result.get("frontend_image_tag"))
    if result.get("backend_container"):
        stop_and_remove(result["backend_container"])
        cleanup_docker_image(result["backend_image_tag"])
    if result.get("db_container"):
        teardown_database(result["db_container"])
    if result.get("network_name"):
        remove_network(result["network_name"])