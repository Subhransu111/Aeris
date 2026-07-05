import docker

client = docker.from_env()

def build_image(repo_path: str, dockerfile_path: str, tag: str):
    dockerfile_name = dockerfile_path.split("/")[-1]
    try:
        image, logs = client.images.build(
            path=repo_path,
            dockerfile=dockerfile_name,
            tag=tag,
            timeout=600,
        rm=True
        )
        log_text = "\n".join(chunk.get("stream", "") for chunk in logs if "stream" in chunk)
        return image, log_text
    except docker.errors.BuildError as e:
            # e.build_log is a generator of dicts - same shape as the success case's `logs`
            log_text = "\n".join(chunk.get("stream", "") for chunk in e.build_log if "stream" in chunk)
            raise RuntimeError(f"Docker build failed:\n{log_text}") from None