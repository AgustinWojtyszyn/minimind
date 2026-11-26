import unittest
from types import SimpleNamespace
from unittest.mock import patch

from scripts import update_cloudflare


class UpdateAuthenticationTests(unittest.TestCase):
    def test_oauth_needs_free_plan_confirmation(self):
        with patch('sys.argv', ['update', '--oauth']), patch.dict('os.environ', {}, clear=True):
            with self.assertRaises(SystemExit):
                update_cloudflare.main()

    def test_oauth_does_not_use_stale_token(self):
        with patch('sys.argv', ['update', '--oauth', '--confirmed-free-plan']), patch.dict('os.environ', {'CLOUDFLARE_API_TOKEN': 'mock'}, clear=True):
            with self.assertRaises(SystemExit):
                update_cloudflare.main()

    def test_oauth_uploads_and_deploys_without_token(self):
        version = '12345678-1234-4321-abcd-123456789abc'
        with patch('sys.argv', ['update', '--oauth', '--confirmed-free-plan']), patch.dict('os.environ', {}, clear=True), patch.object(update_cloudflare.shutil, 'which', return_value='/mock/bin/wrangler'), patch.object(update_cloudflare.subprocess, 'run') as run, patch.object(update_cloudflare, 'verify_remote', return_value='ok'):
            run.side_effect = [None, SimpleNamespace(returncode=0, stdout='Worker Version ID: '+version), None]
            update_cloudflare.main()
            self.assertEqual(run.call_args_list[1].args[0][:3], ['/mock/bin/wrangler', 'versions', 'upload'])
            self.assertIn(version+'@100%', run.call_args_list[2].args[0])
            self.assertNotIn('triggers', run.call_args_list[2].args[0])

    def test_oauth_missing_wrangler_has_clear_error(self):
        with patch('sys.argv', ['update', '--oauth', '--confirmed-free-plan']), patch.dict('os.environ', {}, clear=True), patch.object(update_cloudflare.shutil, 'which', return_value=None):
            with self.assertRaisesRegex(SystemExit, 'Node 22'):
                update_cloudflare.main()
