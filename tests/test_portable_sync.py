from pathlib import Path
import unittest
import json
import struct

from scripts.build_portable import render_index


class PortableSyncTests(unittest.TestCase):
    def test_public_index_matches_canonical_frontend(self):
        root = Path(__file__).resolve().parents[1]
        self.assertEqual((root / 'docs/index.html').read_text(), render_index(),
                         'Regenerate GitHub Pages with scripts/build_portable.py')

    def test_pwa_icon_assets(self):
        root = Path(__file__).resolve().parents[1]
        for name, size in [('icon-192.png', 192), ('icon-512.png', 512)]:
            data = (root / 'frontend/portable' / name).read_bytes()
            self.assertEqual(data, (root / 'docs' / name).read_bytes())
            self.assertEqual(data[:8], b'\\x89PNG\\r\\n\\x1a\\n')
            self.assertEqual(struct.unpack('>II', data[16:24]), (size, size))
            self.assertEqual(data[25], 6)  # RGBA, transparent corners
        manifest = (root / 'frontend/portable/manifest.webmanifest').read_text()
        self.assertEqual(manifest, (root / 'docs/manifest.webmanifest').read_text())
        self.assertEqual(json.loads(manifest)['icons'][0]['sizes'], '512x512')
        self.assertIn('manifest.webmanifest?v=3', (root / 'docs/index.html').read_text())
