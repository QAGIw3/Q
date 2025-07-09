# Use an official Flink image with Python support.
# Make sure the Flink version and Scala version match your cluster.
FROM flink:1.17-scala_2.12-java11

# The Flink Python base image provides a default workdir at /opt/flink
WORKDIR /opt/flink

# Copy the requirements file and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the Flink job script into the container
COPY job.py .

# The base image's entrypoint will handle running the job.
# We just need to provide the path to our script.
# This is usually done via the command in the deployment manifest.
# Example command:
# command: ["/opt/flink/bin/flink-run", "-py", "/opt/flink/job.py"] 