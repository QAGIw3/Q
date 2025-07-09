import unittest
import asyncio
from unittest.mock import patch, MagicMock
import subprocess
import os

from managerQ.app.core.planner import Planner

class TestFeedbackLoop(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        # This script path is relative to the root of the project
        self.ingest_script_path = "KnowledgeGraphQ/scripts/ingest_insight.py"
        # Ensure the script exists before running tests
        if not os.path.exists(self.ingest_script_path):
            raise FileNotFoundError(f"Ingestion script not found at {self.ingest_script_path}")

    @patch('managerQ.app.core.planner.kgq_client')
    async def test_insight_retrieval_e2e(self, mock_kgq_client):
        """
        Tests that an ingested insight is retrieved by the planner for a similar prompt.
        """
        # 1. Define the test insight and prompt
        lesson = "When a service deployment fails, always check the service logs first."
        workflow_id = "wf_test_feedback_1"
        original_prompt = "The deployment for 'WebAppQ' failed."
        final_status = "FAILED"
        
        similar_prompt = "My web application deployment isn't working."

        # 2. Mock the external 'ingest_insight.py' script execution
        # We are not testing the script itself, but that the planner *would* find its result.
        # So we will mock the return value from the knowledge graph client.
        
        # Simulate that the KG contains our lesson
        mock_kgq_client.execute_gremlin_query.return_value = {
            "data": [lesson]
        }

        # 3. Instantiate the planner and call create_plan
        planner = Planner()
        
        # We need to get the internal analysis, so we'll call the private method directly
        # In a real-world scenario, you might have integration tests that check the full behavior
        analysis = await planner._analyze_prompt(similar_prompt, insights=[lesson]) # We pass the insight directly for this test

        # 4. Assert that the retrieved insight is in the analysis prompt context
        # This is a bit of a white-box test, but it's the most direct way to check.
        # The ideal test would mock the call to q_pulse_client and inspect the prompt sent to it.
        
        # Let's mock the LLM call to isolate the test to just the insight retrieval part.
        with patch.object(planner, '_call_qpulse') as mock_call_qpulse:
            mock_call_qpulse.return_value = '{"summary": "test", "is_ambiguous": false, "high_level_steps": []}'
            
            # Re-run the analysis part of the planning
            await planner.create_plan(similar_prompt)
            
            # Get the prompt that was sent to the LLM for analysis
            analysis_prompt_sent_to_llm = mock_call_qpulse.call_args[0][0]
            
            # Check that our lesson is present in the prompt
            self.assertIn(lesson, analysis_prompt_sent_to_llm)

if __name__ == '__main__':
    unittest.main() 