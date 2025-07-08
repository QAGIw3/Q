# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /usr/src/app

# Set PYTHONPATH to include the shared library directory
ENV PYTHONPATH "${PYTHONPATH}:/usr/src/app"

# Install dependencies
# Copy requirements first to leverage Docker layer caching
COPY ./VectorStoreQ/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the shared client library code
COPY ./shared/q_vectorstore_client ./shared/q_vectorstore_client

# Copy the application code into the container
COPY ./VectorStoreQ/app ./app
COPY ./VectorStoreQ/config ./config

# Expose the port the app runs on
EXPOSE 8001

# Command to run the application
CMD ["python", "app/main.py"] 