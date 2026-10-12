"""Metadata consolidation preserves evidence bytes and avoids hash self-reference."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from script.artifacts import (collect_output_hashes, metadata_bytes, read_metadata,
                              reference_json, reference_sha, write_metadata,
                              write_metadata_bytes)


class ArtifactTests(unittest.TestCase):
    def test_roundtrip_preserves_original_serialization_and_sections(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            contents = [b'{"price": 123}', b'{\n  "price": 123\n}\n',
                        '{"เหตุผล":"ไม่ทราบ"}\n'.encode()]
            for index, content in enumerate(contents):
                section = 'evidence_' + str(index)
                write_metadata_bytes(folder, section, content)
                self.assertEqual(metadata_bytes(folder, section), content)
                self.assertEqual(reference_sha(str(folder / 'metadata.json') + '#' + section),
                                 hashlib.sha256(content).hexdigest())
            self.assertEqual(len(list(folder.iterdir())), 1)
            self.assertEqual(reference_json(str(folder / 'metadata.json') + '#evidence_0'), {'price': 123})

    def test_rewriting_a_section_discards_old_serialization(self):
        with tempfile.TemporaryDirectory() as directory:
            write_metadata_bytes(directory, 'policy', b'{"old":true}')
            write_metadata(directory, 'policy', {'new': True})
            self.assertEqual(json.loads(metadata_bytes(directory, 'policy')), {'new': True})

    def test_hash_index_has_no_self_reference_and_legacy_remains_readable(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            (folder / 'summary.json').write_text('{"rows":4}')
            self.assertEqual(read_metadata(folder, 'summary'), {'rows': 4})
            write_metadata(folder, 'validation', {'valid': True})
            first = collect_output_hashes(folder)
            write_metadata(folder, 'hashes', first)
            write_metadata(folder, 'progress', {'phase': 'done'})
            self.assertEqual(collect_output_hashes(folder), first)
            self.assertNotIn('metadata.json#hashes', first)
