import os
import influxdb_client
from influxdb_client.client.write_api import SYNCHRONOUS

# Configuration
INFLUXDB_URL = os.environ.get("INFLUXDB_URL", "http://localhost:8086")
INFLUXDB_TOKEN = os.environ.get("INFLUXDB_TOKEN")
INFLUXDB_ORG = os.environ.get("INFLUXDB_ORG", "chromebook")
INFLUXDB_BUCKET = os.environ.get("INFLUXDB_BUCKET", "health_data")

# Validate the INFLUXDB_TOKEN
if not INFLUXDB_TOKEN:
    print("Error: INFLUXDB_TOKEN environment variable is not set")
    exit(1)

# Initialize the InfluxDB client
client = influxdb_client.InfluxDBClient(url=INFLUXDB_URL, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG)
query_api = client.query_api()

# Query to fetch the last BPM value
query = f"""
from(bucket: "{INFLUXDB_BUCKET}")
  |> range(start: -10m)
  |> filter(fn: (r) => r._measurement == "Health" and r._field == "bpm")
  |> last()
"""

try:
    tables = query_api.query(query, org=INFLUXDB_ORG)
    if not tables:
        print("No data found.")
        exit(1)

    for table in tables:
        for record in table.records:
            bpm = record.get_value()
            timestamp = record.get_time()
            print(f"Last BPM value: {bpm} at {timestamp}")

except Exception as e:
    print(f"Error querying InfluxDB: {e}")
    exit(1)

