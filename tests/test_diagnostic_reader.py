import copy
import importlib.util
from pathlib import Path
import plistlib
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


def reader():
    spec = importlib.util.spec_from_file_location("nx_reader_test", ROOT / "tools/read_diagnostic.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DiagnosticReaderContracts(unittest.TestCase):
    def test_numeric_bridge_and_receiver_share_exact_closed_vocabulary(self):
        native = (ROOT / "Sources/Native/NoticeXDiagnostics.m").read_text()
        pairs = re.findall(r'case (\d+): return "([a-z_]+)";', native)
        codes = [int(code) for code, _ in pairs]
        names = [name for _, name in pairs]
        self.assertEqual(len(codes), len(set(codes)))
        self.assertEqual(len(names), len(set(names)))
        self.assertEqual(set(names), reader().ALLOWED_PHASES)
        swift = (ROOT / "Sources/Support/NoticeDiagnostics.swift").read_text()
        declared = re.findall(r"case (\w+) = (\d+)", swift)
        mapping = dict(pairs)
        for case, code in declared:
            words = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", case)
            words = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", words).lower()
            self.assertEqual(mapping[code], words)
        self.assertLessEqual(len(codes), 96)

    def test_rejects_wrong_types_content_unknown_keys_and_stale_builds(self):
        module = reader()
        base = {"snapshot": {"schema": 1, "build": module.BUILD, "generation": 1,
                             "sequence": 1, "resetConfirmed": True, "trace": ["runtime_start"]}}
        valid = plistlib.dumps(base, fmt=plistlib.FMT_BINARY)
        self.assertEqual(module.validate(valid), base["snapshot"])
        mutations = []
        for key, value in (("schema", True), ("generation", True), ("sequence", True),
                           ("resetConfirmed", 1), ("resetConfirmed", False),
                           ("generation", -1), ("build", "old-build"),
                           ("trace", ["runtime_start", "private-content"]),
                           ("trace", ["runtime_start", "runtime_start"]),
                           ("trace", ["callback_layout"]), ("unexpected", "private-content")):
            item = copy.deepcopy(base)
            item["snapshot"][key] = value
            mutations.append(item)
        mutations.extend([{}, {**base, "unexpected": "private-content"}])
        for item in mutations:
            with self.subTest(item=item):
                with self.assertRaises(ValueError):
                    module.validate(plistlib.dumps(item, fmt=plistlib.FMT_BINARY))
        for raw in (b"", b"invalid", b"x" * 16385):
            with self.assertRaises(ValueError):
                module.validate(raw)


if __name__ == "__main__":
    unittest.main()
