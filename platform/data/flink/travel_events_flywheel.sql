-- Flink SQL reference for enterprise flywheel streaming pipeline.
-- This is a template aligned with current event topics and lakehouse design.

-- Source (Pulsar)
CREATE TABLE pulsar_travel_events (
  topic STRING,
  payload STRING,
  ts BIGINT,
  WATERMARK FOR ts AS TO_TIMESTAMP_LTZ(ts, 3) - INTERVAL '5' SECOND
) WITH (
  'connector' = 'pulsar',
  'topic' = 'travel-agent.events',
  'service-url' = 'pulsar://pulsar-broker:6650',
  'admin-url' = 'http://pulsar-broker:8080',
  'format' = 'json'
);

-- Sink (Iceberg bronze)
CREATE TABLE iceberg_bronze_travel_events (
  topic STRING,
  payload STRING,
  ts BIGINT
) WITH (
  'connector' = 'iceberg',
  'catalog-name' = 'travel_catalog',
  'catalog-type' = 'hive',
  'warehouse' = 's3://travel-lakehouse/warehouse',
  'uri' = 'thrift://hive-metastore:9083',
  'database' = 'bronze',
  'table-name' = 'travel_events'
);

INSERT INTO iceberg_bronze_travel_events
SELECT topic, payload, ts
FROM pulsar_travel_events;

