# 🤖 agentQ

## Overview

**Status:** This service is the core reasoning engine of the Q Platform. It has evolved into a stateful, multi-tool autonomous agent capable of complex, multi-step problem-solving.

`agentQ` is designed to be a scalable, message-driven service where each agent instance is an independent worker that can reason, plan, maintain conversational memory, and use the full suite of Q Platform services as "tools" to accomplish its goals.

## Architecture: The ReAct Agent

The agent's core logic is built on a **ReAct (Reason, Act)** loop. Instead of simply responding to a prompt, the agent iteratively performs the following steps until it can provide a final answer:

1.  **Reason (Thought)**: Based on the user's query and the full conversation history (including previous tool outputs), the LLM generates a "thought" outlining its reasoning process and its plan for the next action.
2.  **Act (Action)**: The LLM then chooses a single, specific action to take, formatted as JSON. This can be to call a tool or to finish the task.
3.  **Observe**: If a tool was called, the agent executes it and appends the resulting "observation" to the conversation history.
4.  **Repeat**: The agent takes this new information into account and re-evaluates, beginning the loop again.

This architecture allows the agent to break down complex problems, gather information from multiple sources, interact with external systems, and even ask for human help when it gets stuck.

## Agent Capabilities & Tools

The agent has access to a powerful toolbox composed of other Q Platform services:

-   **`search_knowledge_base`**: Performs a semantic search against **`VectorStoreQ`** to find unstructured information and answer "what is X" type questions.
-   **`query_knowledge_graph`**: Executes a Gremlin query against **`KnowledgeGraphQ`** to find structured data and answer "how is X related to Y" type questions.
-   **`delegate_to_quantumpulse`**: For very complex questions or "what-if" scenarios, it can delegate the task to the **`QuantumPulse`** deep inference service, effectively asking another powerful AI for help.
-   **`trigger_integration_flow`**: Triggers a pre-defined workflow in the **`IntegrationHub`**, allowing the agent to perform actions in the real world (e.g., send an email, create a calendar event).
-   **`ask_human_for_clarification`**: Pauses its execution and asks a clarifying question to the user via a message back through the platform.

## 🚀 Getting Started

### 1. Dependencies

-   A full, running Q Platform stack, including Pulsar, Ignite, `VectorStoreQ`, `KnowledgeGraphQ`, `IntegrationHub`, `managerQ`, and HashiCorp Vault.
-   Secrets (e.g., `OPENAI_API_KEY`) stored in Vault.

### 2. Running an Agent

Each agent is an independent worker process that is dispatched tasks by `managerQ`.

```bash
# From the project root, set the necessary environment variables
export PYTHONPATH=$(pwd)
export VAULT_ADDR="http://your-vault-address:8200"
export VAULT_TOKEN="your-vault-token"

# Run an agent instance
python agentQ/app/main.py
```

The agent will start, register itself with `managerQ`, and begin listening for tasks on its unique Pulsar topic.
