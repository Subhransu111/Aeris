import shutil
import os
import docker

client = docker.from_env()

def cleanup_repo_dir(dest_dir: str):
    if os.path.exists(dest_dir):
        shutil.rmtree(dest_dir, ignore_errors=True)

def cleanup_docker_image(tag: str):
    try:
        client.images.remove(tag, force=True)
    except docker.errors.ImageNotFound:
        pass
    except Exception:
        pass  # don't let cleanup failure crash the run

def full_cleanup(dest_dir: str, container=None, image_tag: str = None):
    """Call this in a finally block after every sandbox run, regardless of outcome."""
    if container:
        try:
            container.stop(timeout=5)
            container.remove(force=True)
        except Exception:
            pass
    if image_tag:
        cleanup_docker_image(image_tag)
    cleanup_repo_dir(dest_dir)