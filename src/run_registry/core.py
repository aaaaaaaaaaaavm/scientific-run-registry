"""A tiny append-safe registry for reproducible computational runs."""
from hashlib import sha256
import json
from pathlib import Path

def canonical_sha256(value) -> str:
    payload=json.dumps(value,sort_keys=True,separators=(",",":"),allow_nan=False).encode()
    return sha256(payload).hexdigest()

class Registry:
    def __init__(self,path: str|Path):
        self.path=Path(path)

    def load(self) -> dict:
        return json.loads(self.path.read_text()) if self.path.exists() else {"schema":"scientific-run-registry/v1","runs":{}}

    def register(self, inputs: dict, outputs: dict, claims: list[str], parents: list[str]|None=None) -> dict:
        record={"inputs":inputs,"outputs":outputs,"claims":sorted(set(claims)),"parents":sorted(set(parents or []))}
        run_id=canonical_sha256(record)
        data=self.load()
        existing=data["runs"].get(run_id)
        if existing is not None and existing!=record: raise ValueError("run identifier collision")
        data["runs"][run_id]=record
        self.path.parent.mkdir(parents=True,exist_ok=True)
        self.path.write_text(json.dumps(data,indent=2,sort_keys=True)+"\n",encoding="utf-8")
        return {"run_id":run_id,**record}

    def verify(self) -> list[str]:
        failures=[]
        for run_id,record in self.load()["runs"].items():
            if canonical_sha256(record)!=run_id: failures.append(f"changed: {run_id}")
            for parent in record.get("parents",[]):
                if parent not in self.load()["runs"]: failures.append(f"missing parent: {parent}")
        return failures
