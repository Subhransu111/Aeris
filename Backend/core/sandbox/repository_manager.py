import subprocess
import os

def clone_repo(repo_url:str , dest_dir:str)-> str:
    if os.path.exists(dest_dir):
        raise FileExistsError(f"{dest_dir} already exists")
    subprocess.run(["git", "clone","--depth","1",repo_url,dest_dir], check=True , timeout=120)
    return dest_dir
