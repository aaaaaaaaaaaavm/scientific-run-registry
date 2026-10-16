"""Content-addressed run registry with atomic updates on local POSIX filesystems."""
from contextlib import contextmanager
from hashlib import sha256
import json
import os
from pathlib import Path
import tempfile


def canonical_sha256(value) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return sha256(payload).hexdigest()


class Registry:
    def __init__(self, path: str | Path):
        self.path = Path(path).resolve()

    def load(self) -> dict:
        # Atomic replacement gives readers one complete snapshot.
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {"schema": "scientific-run-registry/v1", "runs": {}}

    @contextmanager
    def _writer_lock(self):
        try:
            import fcntl
        except ImportError as exc:
            raise RuntimeError("registry writes require POSIX flock support") from exc
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # Keep a stable lock inode: deleting the sidecar would split the lock.
        with self.path.with_name(self.path.name + ".lock").open("a+b") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)

    def register(self, inputs: dict, outputs: dict, claims: list[str],
                 parents: list[str] | None = None) -> dict:
        record = {"inputs": inputs, "outputs": outputs, "claims": sorted(set(claims)),
                  "parents": sorted(set(parents or []))}
        # Freeze caller data and reject NaN before any persistent mutation.
        record = json.loads(json.dumps(record, allow_nan=False))
        run_id = canonical_sha256(record)
        with self._writer_lock():
            data = self.load()
            existing = data["runs"].get(run_id)
            if existing is not None and existing != record:
                raise ValueError("run identifier collision")
            data["runs"][run_id] = record
            payload = json.dumps(data, indent=2, sort_keys=True, allow_nan=False) + "\n"
            temporary = None
            try:
                with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8",
                                                 dir=self.path.parent, delete=False) as out:
                    temporary = Path(out.name)
                    out.write(payload)
                    out.flush()
                    os.fsync(out.fileno())
                os.replace(temporary, self.path)
            finally:
                if temporary is not None:
                    temporary.unlink(missing_ok=True)
        return {"run_id": run_id, **record}

    def verify(self) -> list[str]:
        failures = []
        runs = self.load()["runs"]
        for run_id, record in runs.items():
            if canonical_sha256(record) != run_id:
                failures.append(f"changed: {run_id}")
            for parent in record.get("parents", []):
                if parent not in runs:
                    failures.append(f"missing parent: {parent}")
        return failures
