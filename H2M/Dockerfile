# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /usr/src/app

# Set PYTHONPATH to include the shared library directory
ENV PYTHONPATH "${PYTHONPATH}:/usr/src/app"

# Install dependencies
COPY ./H2M/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy all shared client library code
COPY ./shared/q_auth_parser ./shared/q_auth_parser
COPY ./shared/q_vectorstore_client ./shared/q_vectorstore_client
COPY ./shared/q_pulse_client ./shared/q_pulse_client

# Copy the application code into the container
COPY ./H2M/app ./app
COPY ./H2M/config ./config

# Expose the port the app runs on
EXPOSE 8002

# Command to run the application
CMD ["python", "app/main.py"] 