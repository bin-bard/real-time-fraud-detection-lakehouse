# Custom Hive Metastore with S3A support
FROM apache/hive:3.1.3

USER root

# Copy pre-downloaded JARs to both Hive and Hadoop lib directories
COPY lib/*.jar /opt/hive/lib/
COPY lib/*.jar /opt/hadoop/share/hadoop/common/lib/
COPY core-site.xml /opt/hadoop/etc/hadoop/core-site.xml

USER hive
