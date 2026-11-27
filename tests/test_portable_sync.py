from pathlib import Path
import unittest

from scripts.build_portable import render_index


class PortableSyncTests(unittest.TestCase):
    def test_public_index_matches_canonical_frontend(self):
        root = Path(__file__).resolve().parents[1]
        self.assertEqual((root / 'docs/index.html').read_text(), render_index(),
                         'Regenerate GitHub Pages with scripts/build_portable.py')
