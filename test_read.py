
import influxdb_client, os, time
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

token = os.environ.get("INFLUXDB_TOKEN")
org = "chromebook"
url = "http://localhost:8086"

client = influxdb_client.InfluxDBClient(url=url, token=token, org=org)
query_api = client.query_api()

query = """from(bucket: "health_data")
 |> range(start: -10m)
 |> filter(fn: (r) => r._measurement == "Health")"""
tables = query_api.query(query, org="chromebook")

for table in tables:
  for record in table.records:
    print(record)

