import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import plan_animations as planner

class PlanTests(unittest.TestCase):
    def setUp(self):
        self.plan = copy.deepcopy(planner.EXAMPLE)
        self.story = 'EXACT contiguous passage copied from the input story\nANOTHER EXACT contiguous passage copied from the input story 1979'
        timeline = self.plan['clips'][1]
        timeline['source_excerpt'] += ' 1979'
        timeline['events'][0]['evidence_quote'] = 'ANOTHER EXACT'

    def test_valid(self):
        planner.validate(self.plan, self.story, 2)

    def test_rejects_invented_source_and_year(self):
        bad = copy.deepcopy(self.plan)
        bad['clips'][0]['source_excerpt'] = 'Fabricated narration'
        with self.assertRaisesRegex(ValueError, 'match the input'):
            planner.validate(bad, self.story, 2)
        bad = copy.deepcopy(self.plan)
        bad['clips'][1]['events'][1]['year'] = 1501
        with self.assertRaisesRegex(ValueError, 'appear in event evidence'):
            planner.validate(bad, self.story, 2)

    def test_rejects_bad_timing(self):
        self.plan['clips'][0]['duration'] = 13
        with self.assertRaisesRegex(ValueError, 'sum'):
            planner.validate(self.plan, self.story, 2)
        self.setUp()
        self.plan['clips'][1]['events'][1]['reveal'] = 0
        with self.assertRaisesRegex(ValueError, 'increase'):
            planner.validate(self.plan, self.story, 2)

    def test_rejects_fake_assets(self):
        self.plan['clips'][0]['scenes'][0]['image'] = '/invented/image.png'
        with self.assertRaisesRegex(ValueError, 'null'):
            planner.validate(self.plan, self.story, 2)

    def test_repairs_invalid_api_output(self):
        responses = [{'choices': [{'finish_reason': 'stop', 'message': {'content': '{}'}}]},
                     {'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps(self.plan)}}]}]
        with patch.object(planner, 'call_api', side_effect=responses) as mock:
            result = planner.generate(self.story, 'dummy-key', 'test-model')
        self.assertEqual(mock.call_count, 2)
        self.assertEqual(result['generation']['fact_check_status'], 'not_verified')

    def test_rejects_repeated_truncation(self):
        response = {'choices': [{'finish_reason': 'length', 'message': {'content': '{}'}}]}
        with patch.object(planner, 'call_api', return_value=response):
            with self.assertRaisesRegex(ValueError, 'after one repair'):
                planner.generate(self.story, 'dummy-key', 'test-model')

    def test_truncation_restarts_with_more_tokens_and_thinking_disabled(self):
        responses = [{'choices': [{'finish_reason': 'length', 'message': {'content': '{partial'}}]},
                     {'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps(self.plan)}}]}]
        with patch.object(planner, 'call_api', side_effect=responses) as mock:
            planner.generate(self.story, 'dummy-key', 'test-model', max_tokens=6000)
        first, second = [call.args[0] for call in mock.call_args_list]
        self.assertEqual(first['thinking'], {'type': 'disabled'})
        self.assertEqual(second['max_tokens'], 12000)
        self.assertEqual(len(second['messages']), 2)

    def test_unicode_output_and_env(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)/'plan.json'
            planner.write_plan(output, {'title': 'फ़ारस'})
            self.assertIn('फ़ारस', output.read_text())
            env = Path(temp)/'.env'
            env.write_text('export DEEPSEEK_API_KEY="test-only"\n')
            with patch.dict('os.environ', {}, clear=True):
                self.assertEqual(planner.load_key(env), 'test-only')

if __name__ == '__main__':
    unittest.main()
