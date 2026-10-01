import os
import sys


def _load_env_file(path):
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


if os.environ.get("ENV_FILE"):
    _load_env_file(os.environ["ENV_FILE"])


def setting(name):
    value = os.environ.get(name)
    if value in (None, ""):
        sys.exit(f"missing setting {name} (see .env.example)")
    return value
