"""Generate missing local secrets without replacing existing values."""
import argparse
import os
import secrets
from pathlib import Path
from cryptography.fernet import Fernet


def initialize(path: Path) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    generated = {
        "ADMIN_PASSWORD": lambda: secrets.token_urlsafe(32),
        "SESSION_SECRET": lambda: secrets.token_urlsafe(48),
        "APP_ENCRYPTION_KEY": lambda: Fernet.generate_key().decode(),
        "DB_PASSWORD": lambda: secrets.token_urlsafe(32),
    }
    try:
        previous = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        previous = ""
    existing = {line.split("=", 1)[0].strip() for line in previous.splitlines()
                if "=" in line and not line.lstrip().startswith("#")}
    missing = {key: produce() for key, produce in generated.items() if key not in existing}
    if not missing:
        return False
    # Exclusive creation, or append-only update. Existing values never appear in output.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        if previous and not previous.endswith("\n"):
            stream.write("\n")
        for key, value in missing.items():
            stream.write(f"{key}={value}\n")
    path.chmod(0o600)
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create local .env without replacing existing values")
    parser.add_argument("path", nargs="?", type=Path, default=Path(__file__).resolve().parents[1] / ".env")
    args = parser.parse_args()
    print("Added missing local secrets" if initialize(args.path) else "Existing local secrets preserved")
