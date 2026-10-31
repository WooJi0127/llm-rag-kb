import os
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]


class CliTests(unittest.TestCase):
    def run_cli(self, args):
        env = {**os.environ, 'PYTHONUTF8': '0', 'PYTHONIOENCODING': 'cp1252',
               'USE_LLM': '0', 'RAG_PORT': '0'}
        return subprocess.run([sys.executable, *args], cwd=ROOT, env=env,
                              capture_output=True, timeout=10)

    def test_ask_redirected_output_is_utf8_even_with_legacy_environment(self):
        result = self.run_cli(['run.py', 'ask', 'MQTT'])
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn('[回答]', result.stdout.decode('utf-8'))

    def test_serve_startup_redirected_output_is_utf8(self):
        # Run the actual entrypoint and startup; only terminate the serving loop.
        for entry in ['run.py', 'app.py']:
            with self.subTest(entry=entry):
                code = ("import runpy\nfrom unittest.mock import patch\n"
                        "with patch('http.server.ThreadingHTTPServer.serve_forever', side_effect=KeyboardInterrupt):\n"
                        f"    runpy.run_path({entry!r}, run_name='__main__')\n")
                result = self.run_cli(['-c', code])
                self.assertEqual(0, result.returncode, result.stderr)
                self.assertIn('本地知识库已启动', result.stdout.decode('utf-8'))

    def test_evaluation_redirected_output_is_utf8(self):
        result = self.run_cli(['scripts/evaluate.py', '--k', '3'])
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn('设备发布温度消息', result.stdout.decode('utf-8'))
