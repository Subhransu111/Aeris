import docker

client = docker.from_env()

def build_image(repo_path: str, dockerfile_path: str, tag: str):
    dockerfile_name = dockerfile_path.split("/")[-1]
    image, logs = client.images.build(
        path=repo_path,
        dockerfile=dockerfile_name,
        tag=tag,
        timeout=600,
        rm=True
    )
    log_text = "\n".join(chunk.get("stream", "") for chunk in logs if "stream" in chunk)
    return image, log_text