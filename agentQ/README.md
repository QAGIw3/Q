# 🤖 agentQ

## Overview

**Status:** This service has been refactored from a simple LLM wrapper into a stateful, tool-using autonomous agent.

`agentQ` is the core service for executing autonomous AI agents within the Q Platform. It is designed to be a scalable, message-driven service where each agent instance is an independent worker that can reason, maintain conversational memory, and use other Q Platform services as "tools" to accomplish complex tasks.

## Architecture: The ReAct Agent

The agent's core logic is built on a **ReAct (Reason, Act)** loop. Instead of simply responding to a prompt, the agent iteratively performs the following steps:

1.  **Reason (Thought)**: Based on the user's query and the conversation history, the LLM first generates a "thought" outlining its reasoning process and its plan to answer the user's request.
2.  **Act (Action)**: The LLM then chooses an action to take. This can be one of two things:
    *   `call_tool`: If the agent needs more information, it can call a tool from its toolbox (e.g., `search_knowledge_base`).
    *   `finish`: If the agent has enough information to provide a final answer, it exits the loop.
3.  **Observe**: The result of a tool call (an "observation") is fed back into the conversation history.
4.  **Repeat**: The agent takes this new information into account, generates a new thought and action, and continues the loop until it decides to `finish`.

This loop is supported by two key components:

-   **`Toolbox`**: A registry that holds all the tools the agent can use. The descriptions of these tools are dynamically injected into the agent's system prompt so it always knows what it's capable of.
-   **`ContextManager`**: A memory layer that connects to Apache Ignite to persist and retrieve conversation history, giving the agent a stateful "memory".

---

## 🚀 Getting Started

### 1. Dependencies

-   An running Apache Pulsar cluster.
-   A running Apache Ignite cluster.
-   A running `VectorStoreQ` service.
-   An OpenAI API key.

### 2. Installation & Configuration

1.  **Install Dependencies**: From the project root, install the required packages.

    ```bash
    # Install agent dependencies
    pip install -r agentQ/requirements.txt

    # Install required shared libraries
    pip install -e ./shared/q_vectorstore_client
    ```

2.  **Configure the Agent**: The agent is configured via `agentQ/config/agent.yaml`. Ensure the Pulsar and Ignite connection details are correct. You must also provide your OpenAI API key, typically by setting the `OPENAI_API_KEY` environment variable.

### 3. Running an Agent

Each agent is an independent worker process. You can run multiple instances.

```bash
# From the project root
export PYTHONPATH=$(pwd)
export OPENAI_API_KEY="your-key-here"

# Run an agent instance
python agentQ/app/main.py
```

The agent will start, register itself with the (future) `managerQ`, and begin listening for tasks on its unique Pulsar topic.
