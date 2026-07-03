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
from core.budget.timeout_watchdog import run_with_timeout, TimeoutException
from core.budget.cleanup_manager import full_cleanup
import docker

client = docker.from_env()

def create_sandbox(repo_url: str, context: ExecutionContext) -> dict:
    dest_dir = os.path.join(tempfile.gettempdir(), f"aegis_{uuid.uuid4().hex[:8]}")
    container_name = f"aegis-sandbox-{uuid.uuid4().hex[:8]}"
    container = None

    try:
        clone_repo(repo_url, dest_dir)
        stack = detect_stack(dest_dir)
        gen_result = generate_dockerfile(dest_dir, stack)

        if gen_result["method"] == "failed":
            full_cleanup(dest_dir)
            return {"status": "failed", "reason": "unsupported_stack_no_dockerfile", "stack": stack}

        if gen_result["method"] == "buildpack":
            build_result = run_with_timeout(
                build_with_buildpack, args=(dest_dir, container_name),
                kwargs={"timeout_seconds": context.timeout_seconds},
                timeout_seconds=context.timeout_seconds
            )
            if not build_result["success"]:
                full_cleanup(dest_dir, image_tag=container_name)
                return {"status": "build_failed", "method": "buildpack", "logs": build_result["logs"]}
            image_id = container_name
            candidate_ports = COMMON_PORTS
        else:
            dockerfile_path = gen_result["dockerfile_path"]
            image, build_logs = run_with_timeout(
                build_image, args=(dest_dir, dockerfile_path, container_name),
                timeout_seconds=context.timeout_seconds
            )
            image_id = image.id
            candidate_ports = [stack["default_port"]] if stack.get("default_port") else COMMON_PORTS

        container = run_container(image_id, container_name, candidate_ports, context)
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
            return {"status": "unhealthy", "runtime_logs": runtime_logs}

        return {
            "status": "running",
            "container": container,
            "container_id": container.id,
            "host_port": host_port,
            "stack": stack,
            "build_method": gen_result["method"],
            "dest_dir": dest_dir,
            "image_tag": container_name
        }

    except TimeoutException as e:
        full_cleanup(dest_dir, container=container, image_tag=container_name)
        return {"status": "timeout", "reason": str(e)}

    except Exception as e:
        full_cleanup(dest_dir, container=container, image_tag=container_name)
        return {"status": "error", "reason": str(e)}


def teardown_sandbox(result: dict):
    """Call this after tests finish on a successfully running sandbox."""
    full_cleanup(
        result.get("dest_dir"),
        container=result.get("container"),
        image_tag=result.get("image_tag")
    )