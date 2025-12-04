# Custom Hive Metastore with S3A support
FROM apache/hive:3.1.3

USER root

# Install PostgreSQL client for schema check
RUN apt-get update && apt-get install -y postgresql-client && rm -rf /var/lib/apt/lists/*

# Copy pre-downloaded JARs to both Hive and Hadoop lib directories
COPY lib/*.jar /opt/hive/lib/
COPY lib/*.jar /opt/hadoop/share/hadoop/common/lib/
COPY core-site.xml /opt/hadoop/etc/hadoop/core-site.xml

# Copy custom entrypoint script
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

USER hive

# Use custom entrypoint that handles schema initialization smartly
ENTRYPOINT ["/entrypoint.sh"]
