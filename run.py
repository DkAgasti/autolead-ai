import os
import subprocess
import sys

if __name__ == "__main__":
    env = os.environ.copy()
    env["PYTHONPATH"] = "backend"
    uvicorn_path = os.path.join("backend", "venv", "bin", "uvicorn")
    cmd = [uvicorn_path, "app.main:app", "--host", "127.0.0.1", "--port", "8000", "--reload"]
    try:
        subprocess.run(cmd, env=env)
    except KeyboardInterrupt:
        sys.exit(0)

