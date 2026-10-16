import concurrent.futures
import json
import multiprocessing
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from run_registry import Registry


def write_runs(args):
    path, worker = args
    registry = Registry(path)
    for i in range(12):
        registry.register({'worker': worker, 'i': i}, {'value': i}, [])
    registry.register({'shared': True}, {}, [])


@unittest.skipUnless(os.name == 'posix', 'writer locking is supported on POSIX')
class AtomicRegistryTests(unittest.TestCase):
    def test_concurrent_processes_keep_all_unique_runs(self):
        with tempfile.TemporaryDirectory() as folder:
            path = str(Path(folder) / 'nested' / 'runs.json')
            with concurrent.futures.ProcessPoolExecutor(max_workers=6,
                    mp_context=multiprocessing.get_context('spawn')) as pool:
                list(pool.map(write_runs, [(path, i) for i in range(6)]))
            registry = Registry(path)
            self.assertEqual(len(registry.load()['runs']), 73)
            self.assertEqual(registry.verify(), [])

    def test_replace_failure_preserves_previous_file(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'runs.json'
            registry = Registry(path)
            registry.register({'a': 1}, {}, [])
            original = path.read_bytes()
            with patch('run_registry.core.os.replace', side_effect=OSError('injected failure')):
                with self.assertRaises(OSError):
                    registry.register({'b': 2}, {}, [])
            self.assertEqual(path.read_bytes(), original)
            self.assertEqual(sorted(p.name for p in path.parent.iterdir()), ['runs.json', 'runs.json.lock'])

    def test_invalid_json_number_does_not_mutate_registry(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'runs.json'
            with self.assertRaises(ValueError):
                Registry(path).register({'x': float('nan')}, {}, [])
            self.assertFalse(path.exists())
