# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /usr/src/app

# Set PYTHONPATH to include the shared library directory
ENV PYTHONPATH "${PYTHONPATH}:/usr/src/app"

# Install dependencies
COPY ./AuthQ/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the shared auth parser library code
COPY ./shared/q_auth_parser ./shared/q_auth_parser

# Copy the application code into the container
COPY ./AuthQ/app ./app
COPY ./AuthQ/config ./config

# Expose the port the app runs on
EXPOSE 8004

# Command to run the application using uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8004"] 