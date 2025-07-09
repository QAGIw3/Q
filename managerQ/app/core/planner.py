import logging
import json
import asyncio
from typing import Dict, Any, List, Optional

from pydantic import BaseModel, Field
from sentence_transformers import SentenceTransformer

from shared.q_pulse_client.client import QuantumPulseClient
from shared.q_pulse_client.models import QPChatRequest, QPChatMessage
from shared.q_knowledgegraph_client import kgq_client
from managerQ.app.models import Workflow
from managerQ.app.config import settings

logger = logging.getLogger(__name__)

# This client will be configured with the URL from settings
q_pulse_client = QuantumPulseClient(base_url=settings.qpulse_url)

# Load the sentence transformer model for finding relevant insights
embedding_model = SentenceTransformer("all-MiniLM-L6-v2")


# A Pydantic model for the output of the analysis phase
class PlanAnalysis(BaseModel):
    summary: str = Field(..., description="A concise summary of the user's intent.")
    is_ambiguous: bool = Field(..., description="A boolean flag indicating if the prompt is too vague to create a concrete plan.")
    clarifying_question: Optional[str] = Field(None, description="If ambiguous, a question to ask the user to get more detail.")
    high_level_steps: List[str] = Field(default_factory=list, description="A simple list of the major steps involved if the goal is clear.")

# A custom exception to signal that a goal needs clarification
class AmbiguousGoalError(ValueError):
    def __init__(self, message, clarifying_question: str):
        super().__init__(message)
        self.clarifying_question = clarifying_question


ANALYSIS_SYSTEM_PROMPT = """
You are a master AI strategist. Your first job is to analyze and deconstruct a user's request.
Do not create a full workflow yet. First, analyze the request for clarity, potential branching logic, and intent.

Respond with ONLY a single, valid JSON object that adheres to the `PlanAnalysis` schema.

**PlanAnalysis Schema:**
- `summary`: A concise summary of the user's intent.
- `is_ambiguous`: A boolean flag. Set to `true` if the request is vague, lacks specifics, or requires more information to create a concrete plan.
- `clarifying_question`: If `is_ambiguous` is `true`, provide a clear, single question to ask the user.
- `high_level_steps`: If `is_ambiguous` is `false`, provide a list of high-level steps to achieve the goal. **Include potential decision points or conditions.**

{insights}

**Example 1: Ambiguous Request**
User Request: "Make my app better."
Your JSON Response:
{
  "summary": "User wants to improve the application.",
  "is_ambiguous": true,
  "clarifying_question": "What specific area of the app would you like to improve? (e.g., performance, UI/UX, a specific feature, security)",
  "high_level_steps": []
}

**Example 2: Clear Request with a Condition**
User Request: "Analyze the performance impact of the last release. If it's bad, roll it back."
Your JSON Response:
{
  "summary": "User wants to analyze the performance of the last release and roll it back if performance is poor.",
  "is_ambiguous": false,
  "clarifying_question": null,
  "high_level_steps": [
    "Gather performance metrics for the latest release.",
    "Define 'poor performance' threshold.",
    "Decision: If performance is below threshold, then initiate rollback.",
    "If rollback is performed, notify the team."
  ]
}

**Past Lessons (if any):**
You should consider these lessons learned from similar, past tasks. They may help you create a better plan or avoid previous mistakes.
{lessons}
"""

PLANNER_SYSTEM_PROMPT = """
You are an expert planner and task decomposition AI. Your role is to take a summary of a goal and a list of high-level steps, and convert them into a structured, and potentially conditional, workflow of tasks that can be executed by other AI agents.

You must respond with ONLY a single, valid JSON object that adheres to the `Workflow` schema.

**Workflow Schema:**
The workflow contains a `shared_context` dictionary for passing data and a `tasks` list of `TaskBlock`s.

**`TaskBlock` Types:**

**1. `WorkflowTask`:** A single, specific task for an agent.
- `type`: Must be `"task"`.
- `task_id`: A unique identifier (e.g., "task_1").
- `agent_personality`: The agent best suited for the task. Choose from: 'default', 'devops', 'data_analyst', 'knowledge_engineer', 'reflector'.
- `prompt`: A clear, specific prompt. Use Jinja2 templates to access results from completed tasks via the `tasks` context object (e.g., `{{ tasks.task_1.some_key }}`).
- `dependencies`: A list of `task_id`s that must complete before this task starts.

**2. `ConditionalBlock`:** A block for creating adaptive workflows.
- `type`: Must be `"conditional"`.
- `task_id`: A unique identifier (e.g., "cond_1").
- `dependencies`: A list of `task_id`s that must complete before evaluation.
- `branches`: A list of `ConditionalBranch` objects. The first branch whose condition evaluates to true is executed.
    - `condition`: A Jinja2 template expression that evaluates to true or false. Access completed task results via the `tasks` object (e.g., `"{{ tasks.task_1.result.status == 'success' }}"` or `"{{ 'error' in tasks.task_2.result }}"`).
    - `tasks`: A list of `TaskBlock`s to run if the condition is met. This list can contain more `WorkflowTask`s or even nested `ConditionalBlock`s.

**Key Instructions:**
- **Think Step-by-Step:** Decompose the high-level steps into a graph of tasks.
- **Use Conditionals for Decisions:** If the high-level steps mention "if/then", "decision", or branching logic, you MUST use a `ConditionalBlock`.
- **Handle Failure:** Always consider failure paths. A final `condition: "true"` branch can act as an else/catch-all block.
- **Pass Data:** Structure task results as JSONs where possible so downstream tasks can access specific fields. For example, a task that checks something should return `{"status": "ok", "details": "..."}`.
- **Agent Selection:** Be thoughtful about which agent (`agent_personality`) is best for each task.

**Agent-Specific Tooling Notes:**
- The `devops` agent has access to tools like `list_kubernetes_pods`, `get_service_logs`, `restart_service`, and `rollback_deployment`. When generating a plan for DevOps tasks, prefer creating tasks that use these specific tools.
- The `data_analyst` agent can use `execute_sql_query` to query databases and `generate_visualization` to create charts. Delegate data-intensive questions to it.

**Example of a Conditional Workflow:**
Request: "Try to optimize the database query. If it's successful, re-deploy the service. If it fails, revert the changes and notify the database admin."

JSON Response:
{
  "original_prompt": "Try to optimize the database query...",
  "shared_context": {},
  "tasks": [
    {
      "task_id": "task_1",
      "type": "task",
      "agent_personality": "data_analyst",
      "prompt": "Analyze the query 'SELECT * FROM users' and create an optimized version. Your output must be a JSON object with `{\"optimization_successful\": true, \"new_query\": \"...\"}` on success, or `{\"optimization_successful\": false, \"error_message\": \"...\"}` on failure.",
      "dependencies": []
    },
    {
      "task_id": "cond_1",
      "type": "conditional",
      "dependencies": ["task_1"],
      "branches": [
        {
          "condition": "{{ tasks.task_1.optimization_successful == true }}",
          "tasks": [
            { "task_id": "task_2", "type": "task", "agent_personality": "devops", "prompt": "Deploy the new optimized query to production. Query: {{ tasks.task_1.new_query }}", "dependencies": [] }
          ]
        },
        {
          "condition": "true",
          "tasks": [
            { "task_id": "task_3", "type": "task", "agent_personality": "devops", "prompt": "Revert the attempted query optimization changes.", "dependencies": [] },
            { "task_id": "task_4", "type": "task", "agent_personality": "default", "prompt": "Notify the DBA team that the query optimization for 'SELECT * FROM users' failed. Reason: {{ tasks.task_1.error_message }}", "dependencies": ["task_3"] }
          ]
        }
      ]
    }
  ]
}
"""

class Planner:
    """
    Uses an LLM to decompose a user prompt into a structured workflow
    using a two-step "analyze then plan" process.
    """
    async def _call_qpulse(self, prompt: str, model: str = "gpt-4-turbo", max_tokens: int = 2048) -> str:
        """Helper to make calls to the QuantumPulse service."""
        try:
            messages = [QPChatMessage(role="user", content=prompt)]
            request = QPChatRequest(model=model, messages=messages, max_tokens=max_tokens)
            response = await q_pulse_client.get_chat_completion(request)
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Error calling QuantumPulse: {e}", exc_info=True)
            raise

    async def _get_relevant_insights(self, user_prompt: str, top_k: int = 3) -> List[str]:
        """Finds relevant 'lessons learned' from the knowledge graph based on prompt similarity."""
        logger.info("Searching for relevant insights in the knowledge graph.")
        try:
            # 1. Embed the user's prompt
            prompt_embedding = embedding_model.encode(user_prompt).tolist()

            # 2. Formulate a vector search query for the Gremlin endpoint.
            # This query finds the top_k Insight vertices closest to the prompt's embedding.
            # This assumes the JanusGraph instance is configured with an indexing backend
            # that supports vector search, like Elasticsearch. The query syntax might vary
            # based on the specific indexing plugin used (e.g., janusgraph-es-geoshape).
            # The query below is a conceptual representation.
            query = f"""
            g.V().hasLabel('Insight')
                 .has('embedding')
                 .order()
                 .by(__.map(values('embedding')).map(l -> 점.l.stream().mapToDouble(d -> d.doubleValue()).toArray()), 
                     T.closeTo, {json.dumps(prompt_embedding)})
                 .limit({top_k})
                 .values('lesson')
            """
            
            # Execute the query against the KnowledgeGraphQ service
            response = await kgq_client.execute_gremlin_query(query)
            
            # Assuming the client returns a list of results under a 'data' key
            # and handles the raw response parsing.
            insights = response.get("data", [])

            if insights:
                logger.info(f"Found {len(insights)} relevant insights from the knowledge graph.")
            else:
                logger.info("No relevant insights found in the knowledge graph for this prompt.")
            return insights

        except Exception as e:
            logger.error(f"Failed to retrieve insights from knowledge graph: {e}", exc_info=True)
            # Do not fail the whole planning process if insight retrieval fails.
            # Returning an empty list is a safe fallback.
            return []


    async def _analyze_prompt(self, user_prompt: str, insights: List[str]) -> PlanAnalysis:
        """
        Phase 1: Analyzes the user's prompt for ambiguity, informed by past insights.
        """
        logger.info("Phase 1: Analyzing prompt for ambiguity.")
        
        insights_section = ""
        if insights:
            lessons_str = "\n".join(f"- {i}" for i in insights)
            insights_section = f"\n\n**Past Lessons (if any):**\n{lessons_str}"

        prompt = f"{ANALYSIS_SYSTEM_PROMPT.format(insights=insights_section, lessons=lessons_str)}\n\n**User Request:**\n{user_prompt}"
        
        response_str = await self._call_qpulse(prompt)
        
        try:
            analysis_json = json.loads(response_str)
            analysis = PlanAnalysis(**analysis_json)
            logger.info("Successfully analyzed prompt.")
            return analysis
        except (json.JSONDecodeError, TypeError) as e:
            logger.error(f"Failed to decode or validate analysis response: {e}\nResponse: {response_str}", exc_info=True)
            raise ValueError("The planner failed to create a valid analysis.") from e

    async def _generate_workflow(self, user_prompt: str, analysis: PlanAnalysis) -> Workflow:
        """
        Phase 2: Generates the detailed workflow from the analysis.
        """
        logger.info("Phase 2: Generating detailed workflow.")
        steps_str = "\n".join(f"- {step}" for step in analysis.high_level_steps)
        prompt = (
            f"{PLANNER_SYSTEM_PROMPT}\n\n"
            f"**Goal Summary:**\n{analysis.summary}\n\n"
            f"**High-Level Steps:**\n{steps_str}\n\n"
            f"**Original User Request:**\n{user_prompt}"
        )
        
        response_str = await self._call_qpulse(prompt)
        
        try:
            plan_json = json.loads(response_str)
            # Ensure the original prompt is passed through
            plan_json["original_prompt"] = user_prompt
            workflow = Workflow(**plan_json)
            logger.info(f"Successfully created workflow '{workflow.workflow_id}' with {len(workflow.tasks)} tasks.")
            return workflow
        except (json.JSONDecodeError, TypeError) as e:
            logger.error(f"Failed to decode or validate workflow response: {e}\nResponse: {response_str}", exc_info=True)
            raise ValueError("The planner failed to create a valid workflow JSON.") from e

    async def create_plan(self, user_prompt: str) -> Workflow:
        """
        Generates a workflow plan from a user prompt.
        Can raise AmbiguousGoalError if the prompt is unclear.
        """
        logger.info(f"Starting planning process for prompt: '{user_prompt}'")

        # Phase 0: Get relevant insights from past experience
        insights = await self._get_relevant_insights(user_prompt)

        # Phase 1: Analyze
        analysis = await self._analyze_prompt(user_prompt, insights)

        if analysis.is_ambiguous:
            question = analysis.clarifying_question or "The goal is unclear, but the AI did not provide a clarifying question. Please provide more detail."
            logger.warning(f"Prompt is ambiguous. Raising error with question: {question}")
            raise AmbiguousGoalError(
                message="The user's goal is ambiguous and requires clarification.",
                clarifying_question=question,
            )

        # Phase 2: Plan
        logger.info("Prompt is clear. Generating detailed workflow.")
        workflow = await self._generate_workflow(user_prompt, analysis)
        return workflow

    async def replan_with_clarification(self, original_prompt: str, user_clarification: str) -> Workflow:
        """
        Takes an original prompt and a user's clarifying answer and attempts to create a new plan.
        """
        logger.info(f"Re-planning with clarification: '{user_clarification}'")
        
        # Combine the original prompt with the user's answer to form a new, more detailed prompt.
        # This is a simple but effective strategy.
        new_prompt = (
            f"Original Goal: {original_prompt}\n"
            f"My Clarifying Answer: {user_clarification}"
        )
        
        # Use the main create_plan method to run the full analysis and planning pipeline
        # on the new, clarified prompt.
        return await self.create_plan(new_prompt)


# Singleton instance
planner = Planner() 