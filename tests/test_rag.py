import io
import unittest
from pathlib import Path
from unittest.mock import patch

import app
from rag import corpus, generator
from rag.retriever import BM25


class CorpusTests(unittest.TestCase):
    def test_long_unpunctuated_text_is_bounded_and_exactly_overlapped(self):
        text = ''.join(chr(0x4e00 + n) for n in range(999))
        chunks = corpus._chunk_text(text, 'long.txt')
        self.assertTrue(all(0 < len(t) <= 240 for _, t in chunks))
        self.assertEqual([i for i, _ in chunks], [f'long.txt#c{i}' for i in range(len(chunks))])
        for (_, left), (_, right) in zip(chunks, chunks[1:]):
            self.assertEqual(left[-40:], right[:40])
        self.assertEqual(text, chunks[0][1] + ''.join(t[40:] for _, t in chunks[1:]))
        self.assertEqual(chunks, corpus._chunk_text(text, 'long.txt'))

    def test_configuration_and_empty(self):
        for size, overlap in [(0, 0), (10, 10), (10, -1), (True, 0), (10, 1.5)]:
            with self.subTest(size=size, overlap=overlap), self.assertRaises(ValueError):
                corpus._chunk_text('abc', 'x', size, overlap)
        self.assertEqual([], corpus._chunk_text(' \n ', 'x'))
        self.assertEqual([('x#c0', 'abcd'), ('x#c1', 'cdef')], corpus._chunk_text('abcdef', 'x', 4, 2))

    def test_loading_is_sorted_and_empty_files_ignored(self):
        d = Path(__file__).parent / 'fixtures' / 'loading'
        self.assertEqual(['a.md#c0', 'z.txt#c0'], [i for i, _ in corpus.load_corpus(d)])


class RetrievalTests(unittest.TestCase):
    def index(self):
        bm = BM25()
        for i, text in [('a#c0', 'MQTT broker 传感器'), ('b#c0', 'MQTT broker 传感器'), ('c#c0', 'gardening flowers')]:
            bm.add(i, text)
        bm.build()
        return bm

    def test_ranking_ties_follow_insertion_order_and_languages(self):
        bm = self.index()
        self.assertEqual(['a#c0', 'b#c0'], [h['id'] for h in bm.search('MQTT')])
        self.assertEqual('a#c0', bm.search('传感器')[0]['id'])
        self.assertEqual('c#c0', bm.search('FLOWERS')[0]['id'])
        self.assertEqual([], bm.search('xyzzynonexistent'))

    def test_frequencies_are_cached(self):
        bm = self.index()
        self.assertEqual(1, bm.frequencies[0]['mqtt'])
        bm.docs[0] = None  # search must not rescan token arrays
        self.assertEqual('a#c0', bm.search('MQTT')[0]['id'])

    def test_topk_and_empty_corpus(self):
        bm = BM25()
        bm.add('empty', '')
        bm.build()
        self.assertEqual([], bm.search('MQTT'))
        self.assertEqual([], bm.search(''))
        for k in [0, -1, 21, True, 1.0, '5', None]:
            with self.subTest(k=k), self.assertRaises(ValueError):
                bm.search('', k)


class GenerationTests(unittest.TestCase):
    hits = [{'id': 'mqtt.md#c2', 'text': 'MQTT uses a broker.', 'score': 1.0}]

    def test_demo_cites_actual_chunk_and_api_keeps_fields(self):
        bm = BM25()
        bm.add(self.hits[0]['id'], self.hits[0]['text'])
        bm.build()
        with patch.object(app, '_bm', bm), patch.object(generator, 'USE_LLM', False):
            result = app.ask('MQTT')
        self.assertIn('[mqtt.md#c2]', result['answer'])
        self.assertEqual(self.hits[0]['id'], result['evidence'][0]['id'])
        self.assertEqual(self.hits[0]['text'], result['evidence'][0]['text'])
        self.assertEqual('demo', result['mode'])
        for field in ['query', 'answer', 'sources', 'hits', 'mode', 'doc_count']:
            self.assertIn(field, result)
        self.assertEqual(3, len(generator.generate('MQTT', self.hits)))

    def test_model_error_empty_invalid_and_success_report_actual_mode(self):
        for raw, reason in [(b'{"response":" "}', 'empty_response'), (b'{"response":123}', 'invalid_response')]:
            with self.subTest(raw=raw), patch.object(generator, 'USE_LLM', True), patch('urllib.request.urlopen', return_value=io.BytesIO(raw)):
                result = generator.generate_result('MQTT', self.hits)
                self.assertEqual('demo', result['mode'])
                self.assertEqual(reason, result['fallback_reason'])
        with patch.object(generator, 'USE_LLM', True), patch('urllib.request.urlopen', side_effect=TimeoutError):
            self.assertEqual('model_error', generator.generate_result('MQTT', self.hits)['fallback_reason'])
        with patch.object(generator, 'USE_LLM', True), patch('urllib.request.urlopen', return_value=io.BytesIO(b'{"response":"answer [mqtt.md#c2]"}')) as request:
            result = generator.generate_result('MQTT', self.hits)
            self.assertEqual('llm', result['mode'])
            self.assertIn('[mqtt.md#c2]', request.call_args.args[0].data.decode())

    def test_no_hits_does_not_call_model(self):
        with patch.object(generator, 'USE_LLM', True), patch('urllib.request.urlopen') as request:
            result = generator.generate_result('MQTT', [])
        request.assert_not_called()
        self.assertEqual('no_hits', result['fallback_reason'])
        self.assertIn('资料不足', result['answer'])
        self.assertEqual([], result['evidence'])

    def test_extractive_sources_only_contain_used_evidence(self):
        hits = [*self.hits, {'id': 'garden.md#c0', 'text': 'Flowers grow.', 'score': 0.1}]
        with patch.object(generator, 'USE_LLM', False):
            result = generator.generate_result('MQTT', hits)
        self.assertEqual(['mqtt.md'], result['sources'])
        self.assertEqual(['mqtt.md#c2'], [e['id'] for e in result['evidence']])

    def test_model_capacity_is_bounded(self):
        with patch.object(generator, 'USE_LLM', True):
            generator._MODEL_SLOTS.acquire()
            generator._MODEL_SLOTS.acquire()
            try:
                self.assertEqual('model_busy', generator.generate_result('MQTT', self.hits)['fallback_reason'])
            finally:
                generator._MODEL_SLOTS.release()
                generator._MODEL_SLOTS.release()


if __name__ == '__main__':
    unittest.main()
