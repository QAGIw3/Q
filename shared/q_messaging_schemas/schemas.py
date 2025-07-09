# shared/q_messaging_schemas/schemas.py
import fastavro

PROMPT_SCHEMA = fastavro.parse_schema({
    "namespace": "q.managerq", "type": "record", "name": "PromptMessage",
    "fields": [
        {"name": "id", "type": "string"},
        {"name": "prompt", "type": "string"},
        {"name": "model", "type": "string"},
        {"name": "timestamp", "type": "long"},
        {"name": "workflow_id", "type": ["null", "string"], "default": None},
        {"name": "task_id", "type": ["null", "string"], "default": None},
        {"name": "agent_personality", "type": ["null", "string"], "default": None},
    ]
})

RESULT_SCHEMA = fastavro.parse_schema({
    "namespace": "q.agentq", "type": "record", "name": "ResultMessage",
    "fields": [
        {"name": "id", "type": "string"},
        {"name": "result", "type": "string"},
        {"name": "llm_model", "type": "string"},
        {"name": "prompt", "type": "string"},
        {"name": "timestamp", "type": "long"},
        {"name": "workflow_id", "type": ["null", "string"], "default": None},
        {"name": "task_id", "type": ["null", "string"], "default": None},
        {"name": "agent_personality", "type": ["null", "string"], "default": None},
    ]
})

REGISTRATION_SCHEMA = fastavro.parse_schema({
    "namespace": "q.managerq", "type": "record", "name": "AgentRegistration",
    "fields": [{"name": "agent_id", "type": "string"}, {"name": "task_topic", "type": "string"}]
})

THOUGHT_SCHEMA = fastavro.parse_schema({
    "namespace": "q.agentq", "type": "record", "name": "ThoughtMessage",
    "fields": [
        {"name": "conversation_id", "type": "string"},
        {"name": "thought", "type": "string"},
        {"name": "timestamp", "type": "long"},
    ]
}) 