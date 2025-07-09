# Use a specific Python version for reproducibility
FROM python:3.11-slim

# Set the working directory
WORKDIR /app

# Install git for editable installs of shared libraries
RUN apt-get update && apt-get install -y git

# Copy and install dependencies
COPY requirements.txt .
# The -e flag requires the source code to be present
COPY ./shared /app/shared
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY ./app /app/app
COPY ./config /app/config
COPY ./devops_agent.py /app/devops_agent.py
COPY ./job_templates /app/job_templates

# The entrypoint is the agent runner script
# The AGENT_PERSONALITY environment variable will be used to select the agent to run.
CMD ["python", "-m", "app.main"] 