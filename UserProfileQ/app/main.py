# UserProfileQ/app/main.py
import logging
from fastapi import FastAPI
from contextlib import asynccontextmanager

from shared.observability.logging_config import setup_logging
from shared.opentelemetry.tracing import setup_tracing
from UserProfileQ.app.api.profiles import router as profiles_router
from UserProfileQ.app.core.cassandra_client import CassandraClient
from UserProfileQ.app.config import settings # Assuming a config file will be created

# Setup logging and tracing
setup_logging(service_name="UserProfileQ")
logger = logging.getLogger("UserProfileQ")

cassandra_client = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("UserProfileQ service starting up...")
    global cassandra_client
    cassandra_client = CassandraClient(
        hosts=settings.cassandra.hosts,
        keyspace=settings.cassandra.keyspace
    )
    try:
        cassandra_client.connect()
        logger.info("Successfully connected to Cassandra.")
    except Exception as e:
        logger.critical(f"Could not connect to Cassandra during startup: {e}", exc_info=True)
        # Depending on the strategy, you might want to exit here
        # For now, we log it as critical and let the app start.
    
    yield
    
    # Shutdown
    logger.info("UserProfileQ service shutting down...")
    if cassandra_client:
        cassandra_client.close()

# Create FastAPI app
app = FastAPI(
    title="UserProfileQ",
    description="Service for managing user profiles and preferences.",
    version="0.1.0",
    lifespan=lifespan
)

# Instrument FastAPI app with OpenTelemetry
setup_tracing(app, "UserProfileQ", settings.otel_endpoint)

# Include API routers
app.include_router(profiles_router, prefix="/api/v1/profiles", tags=["Profiles"])

@app.get("/health", tags=["Health"])
def health_check():
    # Simple health check. A more advanced one could check DB connectivity.
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 