import http.client
import json
import threading
import unittest
from unittest.mock import patch
from http.server import ThreadingHTTPServer

import app
from rag import generator


class HttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.build_index()
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), app.Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def request(self, method='POST', body=b'{}', headers=None, path='/ask'):
        c = http.client.HTTPConnection(*self.server.server_address, timeout=3)
        try:
            c.request(method, path, None if method == 'GET' else body, headers or {})
            r = c.getresponse()
            return r.status, r.read()
        finally:
            c.close()

    def test_malformed_payloads_are_4xx(self):
        bad = [b'{', b'\xff', b'[]', b'null', b'1', b'{}']
        bad.extend(json.dumps(p).encode() for p in [
            {'q': 7}, {'q': True}, {'q': []}, {'q': '   '}, {'q': 'x' * 2001},
            *({'q': 'MQTT', 'topk': k} for k in [True, 1.0, '5', 0, 21, None])])
        for raw in bad:
            with self.subTest(raw=raw[:100]):
                code, body = self.request(body=raw)
                self.assertTrue(400 <= code < 500, (code, body))
                self.assertIn('error', json.loads(body))

    def test_invalid_length_and_oversize(self):
        for length, expected in [('oops', 400), ('-1', 400), ('65537', 413)]:
            with self.subTest(length=length):
                # Check rejection at the headers, without racing a mismatched
                # two-byte body against the server's intentional early close.
                self.assertEqual(expected, self.request(body=b'', headers={'Content-Length': length})[0])

    def test_lone_surrogates_are_client_errors_but_non_bmp_text_is_valid(self):
        for value in (chr(0xd800), chr(0xdfff)):
            with self.subTest(codepoint=ord(value)):
                query = 'MQTT ' + value
                self.assertEqual(400, self.request(body=json.dumps({'q': query}).encode())[0])
                with self.assertRaises(ValueError):
                    app.ask(query)
        valid = 'MQTT ' + chr(0x1f680)
        code, body = self.request(body=json.dumps({'q': valid}).encode())
        self.assertEqual(200, code)
        self.assertEqual(valid, json.loads(body)['query'])

    def test_excessive_json_nesting_is_client_error(self):
        raw = b'{"q":' + b'[' * 1100 + b'0' + b']' * 1100 + b'}'
        self.assertEqual(400, self.request(body=raw)[0])

    def test_parser_recursion_failure_is_client_error(self):
        # Older supported Python parsers can raise this for deeply nested input.
        with patch('app.json.loads', side_effect=RecursionError):
            self.assertEqual(400, self.request(body=b'{"q":"MQTT"}')[0])

    def test_success_health_and_dashboard(self):
        with patch.object(generator, 'USE_LLM', False):
            code, body = self.request(body=json.dumps({'q': 'MQTT', 'topk': 2}).encode())
        self.assertEqual(200, code)
        self.assertTrue(json.loads(body)['evidence'])
        for path in ['/', '/health']:
            self.assertEqual(200, self.request(method='GET', path=path)[0])
        self.assertEqual(404, self.request(path='/unknown', body=b'')[0])

    def test_slow_model_does_not_block_health(self):
        entered, release = threading.Event(), threading.Event()
        response = []
        def slow_model(*args, **kwargs):
            entered.set()
            release.wait(2)
            raise TimeoutError()
        def query():
            response.append(self.request(body=b'{"q":"MQTT"}'))
        with patch.object(generator, 'USE_LLM', True), patch('urllib.request.urlopen', side_effect=slow_model):
            worker = threading.Thread(target=query)
            worker.start()
            try:
                self.assertTrue(entered.wait(1))
                self.assertEqual(200, self.request(method='GET', path='/health')[0])
                self.assertTrue(worker.is_alive())
            finally:
                release.set()
                worker.join(3)
        self.assertEqual('model_error', json.loads(response[0][1])['fallback_reason'])
