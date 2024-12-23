import os
import influxdb_client
from influxdb_client.client.write_api import SYNCHRONOUS

# Configuration
INFLUXDB_URL = os.environ.get("INFLUXDB_URL", "http://localhost:8086")
INFLUXDB_TOKEN_FILE = os.environ.get("INFLUXDB_TOKEN_FILE", "/home/chromebook/.secrets/influx.txt")
INFLUXDB_ORG = os.environ.get("INFLUXDB_ORG", "chromebook")
INFLUXDB_BUCKET = os.environ.get("INFLUXDB_BUCKET", "health_data")

# Read the InfluxDB token from the file
try:
    with open(INFLUXDB_TOKEN_FILE, 'r') as token_file:
        INFLUXDB_TOKEN = token_file.read().strip()
except FileNotFoundError:
    print(f"Error: Token file '{INFLUXDB_TOKEN_FILE}' not found")
    exit(1)
except Exception as e:
    print(f"Error: Unable to read token file: {e}")
    exit(1)

# Validate the INFLUXDB_TOKEN
if not INFLUXDB_TOKEN:
    print("Error: INFLUXDB_TOKEN is empty or not set")
    exit(1)

# Initialize the InfluxDB client
client = influxdb_client.InfluxDBClient(url=INFLUXDB_URL, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG)
query_api = client.query_api()

# Query to fetch the last values for all health stats
query = f"""
from(bucket: "{INFLUXDB_BUCKET}")
  |> range(start: -10m)
  |> filter(fn: (r) => r._measurement == "Health" and (r._field == "bpm" or r._field == "spo2" or r._field == "battery" or r._field == "movement" or r._field == "pi"))
  |> last()
"""

# ASCII art for the stats
ascii_icons = {
    "bpm": "♥",         # Heart
    "spo2": "●",        # Circle
    "movement": ">>",   # Motion
    "pi": "%",           # Pi symbol
    "battery": "[+ -]",   # Battery
}

try:
    tables = query_api.query(query, org=INFLUXDB_ORG)
    if not tables:
        print("No data found.")
        exit(1)

    stats = {}
    for table in tables:
        for record in table.records:
            field = record.get_field()
            value = record.get_value()
            stats[field] = value

    output = []
    for key, icon in ascii_icons.items():
        if key in stats:
            output.append(f"{icon}_{stats[key]}")
        else:
            output.append(f"{icon} N/A")

    print("  ".join(output))

except Exception as e:
    print(f"Error querying InfluxDB: {e}")
    exit(1)

