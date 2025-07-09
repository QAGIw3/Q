from pydantic_settings import BaseSettings

class WorkerConfig(BaseSettings):
    PULSAR_SERVICE_URL: str = "pulsar://localhost:6650"
    LOG_LEVEL: str = "INFO"

    # Input Topics
    AGENT_TASK_TOPIC: str = "persistent://public/default/q.tasks.dispatch"
    CONDITIONAL_TOPIC: str = "persistent://public/default/q.tasks.conditional"

    # Output Topics
    TASK_STATUS_UPDATE_TOPIC: str = "persistent://public/default/q.tasks.status.update"

    # Subscription Names
    AGENT_TASK_SUBSCRIPTION: str = "workflow-worker-tasks-sub"
    CONDITIONAL_SUBSCRIPTION: str = "workflow-worker-conditionals-sub"
    
    # Dead Letter Topic
    DEAD_LETTER_TOPIC: str = "persistent://public/default/q.tasks.dead-letter"
    MAX_REDELIVER_COUNT: int = 5

    class Config:
        env_file = ".env"
        env_file_encoding = 'utf-8'

settings = WorkerConfig() 