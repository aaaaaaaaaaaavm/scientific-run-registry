import json
import tempfile
import unittest
from pathlib import Path
from run_registry import Registry

class CoreTests(unittest.TestCase):
    def test_register_is_content_addressed_and_idempotent(self):
        with tempfile.TemporaryDirectory() as folder:
            registry=Registry(Path(folder)/"runs.json")
            a=registry.register({"x":1},{"y":2},["C1"])
            b=registry.register({"x":1},{"y":2},["C1"])
            self.assertEqual(a["run_id"],b["run_id"])
            self.assertEqual(registry.verify(),[])
    def test_tamper_is_detected(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"runs.json"; registry=Registry(path)
            run=registry.register({"x":1},{"y":2},[])
            data=json.loads(path.read_text()); data["runs"][run["run_id"]]["outputs"]["y"]=3
            path.write_text(json.dumps(data))
            self.assertEqual(registry.verify(),[f"changed: {run['run_id']}"])

if __name__ == "__main__": unittest.main()
