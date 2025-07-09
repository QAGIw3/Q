# UserProfileQ/app/config.py
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import List

class CassandraSettings(BaseSettings):
    hosts: List[str] = Field(["localhost"], env="CASSANDRA_HOSTS")
    keyspace: str = Field("userprofilesq", env="CASSANDRA_KEYSPACE")

class AppSettings(BaseSettings):
    cassandra: CassandraSettings = CassandraSettings()
    log_level: str = Field("INFO", env="LOG_LEVEL")
    otel_endpoint: str = Field("http://localhost:4317", env="OTEL_EXPORTER_OTLP_ENDPOINT")


    class Config:
        env_file = ".env"
        env_nested_delimiter = '__'

settings = AppSettings() 