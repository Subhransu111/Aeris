import json
import os

DB_SIGNATURES = {
    "mongoose": {"type": "mongodb", "image": "mongo:7", "port": 27017, "uri_env_hint": "mongodb://{host}:27017/testdb"},
    "mongodb": {"type": "mongodb", "image": "mongo:7", "port": 27017, "uri_env_hint": "mongodb://{host}:27017/testdb"},
    "pg": {"type": "postgres", "image": "postgres:16", "port": 5432, "uri_env_hint": "postgresql://postgres:postgres@{host}:5432/testdb"},
    "sequelize": {"type": "postgres", "image": "postgres:16", "port": 5432, "uri_env_hint": "postgresql://postgres:postgres@{host}:5432/testdb"},
    "mysql2": {"type": "mysql", "image": "mysql:8", "port": 3306, "uri_env_hint": "mysql://root:root@{host}:3306/testdb"},
    "redis": {"type": "redis", "image": "redis:7", "port": 6379, "uri_env_hint": "redis://{host}:6379"},
}

def detect_db_dependency(repo_path: str) -> dict:
    pkg_path = os.path.join(repo_path, "package.json")
    if not os.path.exists(pkg_path):
        return None
    with open(pkg_path) as f:
        pkg = json.load(f)
    deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
    for dep_name, db_info in DB_SIGNATURES.items():
        if dep_name in deps:
            return db_info
    return None