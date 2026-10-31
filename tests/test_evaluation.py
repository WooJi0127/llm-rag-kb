import unittest

from scripts.evaluate import metrics


class EvaluationTests(unittest.TestCase):
    def test_document_deduplication_and_macro_metrics(self):
        rows = [
            {'relevant': ['a', 'b'], 'ranked': ['x#c0', 'a#c0', 'a#c1', 'b#c0']},
            {'relevant': ['c'], 'ranked': ['c#c0']},
            {'relevant': [], 'ranked': []},
            {'relevant': [], 'ranked': ['x#c0']},
        ]
        result = metrics(rows, 2)
        self.assertEqual(0.75, result['recall'])
        self.assertEqual(0.75, result['mrr'])
        self.assertEqual(1, result['zero_hit_total'])
        self.assertEqual(2, result['unanswerable_queries'])
        self.assertEqual(1, result['unanswerable_zero_hits'])
        self.assertEqual(0, result['answerable_zero_hits'])

    def test_answerable_miss_counts_zero(self):
        result = metrics([{'relevant': ['a'], 'ranked': []}], 1)
        self.assertEqual(0, result['recall'])
        self.assertEqual(0, result['mrr'])
        self.assertEqual(1, result['answerable_zero_hits'])
