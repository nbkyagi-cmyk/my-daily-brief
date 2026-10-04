import shutil
import subprocess
import unittest
from pathlib import Path
from app import core


class PublicUITests(unittest.TestCase):
    def test_public_assets_and_safe_update_links(self):
        for name in ('app.js', 'index.html', 'style.css'):
            self.assertEqual((core.ROOT / 'docs' / name).read_bytes(), (core.ROOT / 'public' / name).read_bytes())
        html = (core.ROOT / 'docs/index.html').read_text(encoding='utf-8')
        self.assertIn('actions/workflows/daily.yml', html)
        self.assertIn('18:07 JST', html)
        self.assertNotIn('type="password"', html)
        script = (core.ROOT / 'docs/app.js').read_text(encoding='utf-8')
        self.assertNotIn('/api/update', script)
        for category in core.CATEGORIES:
            self.assertIn(category, script)

    @unittest.skipUnless(shutil.which('node'), 'Node is needed for UI behavior tests')
    def test_ui_behavior(self):
        subprocess.run(['node', 'tests/public_ui.cjs'], cwd=core.ROOT, check=True)
