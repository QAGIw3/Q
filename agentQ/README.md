# 🤖 agentQ

## Overview

**Status:** This service has evolved into a stateful, multi-tool autonomous agent capable of complex reasoning.

`agentQ` is the core service for executing autonomous AI agents within the Q Platform. Each agent instance is an independent, stateful worker that can reason, plan, and use a variety of tools to accomplish complex, multi-step tasks.

## Architecture: The ReAct Agent

The agent's core logic is built on a **ReAct (Reason, Act)** loop. Instead of simply responding to a prompt, the agent iteratively performs the following steps until it can provide a final answer:

1.  **Reason (Thought)**: Based on the user's query and the full conversation history (including previous tool outputs), the LLM generates a "thought" outlining its reasoning and its plan for the next action.
2.  **Act (Action)**: The LLM then chooses a single, specific action to take, formatted as JSON.
3.  **Observe**: If the action was a tool call, the agent executes the tool and appends the resulting "observation" to the conversation history.
4.  **Repeat**: The agent takes this new information into account and re-evaluates, beginning the loop again.

This architecture is supported by three key components:

-   **`Toolbox`**: A registry that holds all the tools the agent can use. The descriptions of these tools are dynamically injected into the agent's system prompt.
-   **`ContextManager`**: A memory layer that connects to Apache Ignite to persist and retrieve conversation history, giving the agent a stateful "memory" across turns.
-   **Secret Management**: The agent securely fetches necessary secrets, like API keys, from a central HashiCorp Vault instance at startup.

---

## Agent Capabilities & Tools

The agent has access to the following tools:

-   **`search_knowledge_base`**: Performs a semantic search against `VectorStoreQ` to find information and answer questions.
-   **`ask_human_for_clarification`**: Pauses execution and asks the user a clarifying question when it is stuck or needs a subjective opinion. This works by sending a message to a Pulsar topic that a UI can listen to.
-   **`trigger_integration_flow`**: Triggers a pre-defined workflow in the `IntegrationHub`. This allows the agent to perform actions in external systems, such as sending emails or posting messages to Slack.

---

## 🚀 Getting Started

### 1. Dependencies

-   An running Apache Pulsar, Ignite, `VectorStoreQ`, `IntegrationHub`, and HashiCorp Vault cluster.
-   Secrets (e.g., `OPENAI_API_KEY`) stored in Vault at the path `secret/data/openai`.

### 2. Installation & Configuration

1.  **Install Dependencies**: From the project root, install the required packages.
    ```bash
    pip install -r agentQ/requirements.txt
    pip install -e ./shared/q_vectorstore_client
    ```
2.  **Configure the Agent**: The agent is configured via `agentQ/config/agent.yaml`. Ensure the Pulsar and Ignite connection details are correct.
3.  **Set Vault Environment Variables**: The agent's `VaultClient` authenticates using environment variables.
    ```bash
    export VAULT_ADDR="http://your-vault-address:8200"
    export VAULT_TOKEN="your-vault-token"
    ```

### 3. Running an Agent

Each agent is an independent worker process.

```bash
# From the project root
export PYTHONPATH=$(pwd)

# Run an agent instance
python agentQ/app/main.py
```
