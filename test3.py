import os
import argparse
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

# Argument parser
parser = argparse.ArgumentParser(description="Fetch health stat from InfluxDB.")
parser.add_argument("stat", choices=["bpm", "spo2", "battery", "movement", "pi"], help="The health stat to fetch.")
args = parser.parse_args()

# Initialize the InfluxDB client
client = influxdb_client.InfluxDBClient(url=INFLUXDB_URL, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG)
query_api = client.query_api()

# Query to fetch the last value for the specified health stat
query = f"""
from(bucket: "{INFLUXDB_BUCKET}")
  |> range(start: -10m)
  |> filter(fn: (r) => r._measurement == "Health" and r._field == "{args.stat}")
  |> last()
"""

try:
    tables = query_api.query(query, org=INFLUXDB_ORG)
    if not tables:
        print("No data found.")
        exit(1)

    value = None
    for table in tables:
        for record in table.records:
            value = record.get_value()
            break

    if value is not None:
        print(value)
    else:
        print("N/A")

except Exception as e:
    print(f"Error querying InfluxDB: {e}")
    exit(1)

