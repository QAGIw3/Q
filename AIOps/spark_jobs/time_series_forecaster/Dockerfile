# Use a PySpark base image.
FROM bitnami/spark:3.4.1

USER root

# Spark needs Hadoop, AWS SDK, and Delta Lake bundles to talk to S3-compatible storage.
ENV SPARK_EXTRA_CLASSPATH="/opt/bitnami/spark/jars/hadoop-aws-3.3.4.jar:/opt/bitnami/spark/jars/aws-java-sdk-bundle-1.12.262.jar:/opt/bitnami/spark/jars/delta-core_2.12-2.4.0.jar"

RUN apt-get update && apt-get install -y curl && \
    curl -o /opt/bitnami/spark/jars/hadoop-aws-3.3.4.jar https://repo1.maven.org/maven2/org/apache/hadoop/hadoop-aws/3.3.4/hadoop-aws-3.3.4.jar && \
    curl -o /opt/bitnami/spark/jars/aws-java-sdk-bundle-1.12.262.jar https://repo1.maven.org/maven2/com/amazonaws/aws-java-sdk-bundle/1.12.262/aws-java-sdk-bundle-1.12.262.jar && \
    curl -o /opt/bitnami/spark/jars/delta-core_2.12-2.4.0.jar https://repo1.maven.org/maven2/io/delta/delta-core_2.12/2.4.0/delta-core_2.12-2.4.0.jar

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

USER 1001

# Copy the job script into the container
WORKDIR /app
COPY job.py .
