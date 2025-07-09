# Use a PySpark base image.
FROM bitnami/spark:3.4.1

USER root

# Spark needs Hadoop and AWS SDK bundles to talk to S3-compatible storage like MinIO.
ENV SPARK_EXTRA_CLASSPATH="/opt/bitnami/spark/jars/hadoop-aws-3.3.4.jar:/opt/bitnami/spark/jars/aws-java-sdk-bundle-1.12.262.jar"

RUN apt-get update && apt-get install -y curl && \
    curl -o /opt/bitnami/spark/jars/hadoop-aws-3.3.4.jar https://repo1.maven.org/maven2/org/apache/hadoop/hadoop-aws/3.3.4/hadoop-aws-3.3.4.jar && \
    curl -o /opt/bitnami/spark/jars/aws-java-sdk-bundle-1.12.262.jar https://repo1.maven.org/maven2/com/amazonaws/aws-java-sdk-bundle/1.12.262/aws-java-sdk-bundle-1.12.262.jar

USER 1001

# Copy job requirements and script
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY job.py .

# The entrypoint is configured by the base image to run spark-submit.
# The job script will be provided as an argument in the Kubernetes CronJob manifest. 