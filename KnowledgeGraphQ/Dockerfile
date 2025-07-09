# Use a specific Python version for reproducibility
FROM python:3.11-slim

# Set the working directory
WORKDIR /app

# Copy and install dependencies
# We copy them separately to leverage Docker layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY ./app /app/app
COPY ./shared /app/shared

# Expose the port the app runs on
EXPOSE 8000

# Command to run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"] 