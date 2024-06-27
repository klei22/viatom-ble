import os
import sys
import time
import logging
from datetime import datetime
import bluepy.btle as btle
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS

# InfluxDB configuration
INFLUXDB_URL = os.environ.get("INFLUXDB_URL", "http://localhost:8086")
INFLUXDB_TOKEN = os.environ.get("INFLUXDB_TOKEN")
INFLUXDB_ORG = os.environ.get("INFLUXDB_ORG", "chromebook")
INFLUXDB_BUCKET = os.environ.get("INFLUXDB_BUCKET", "health_data")

# BLE configuration
BLE_ADDRESS = os.environ.get("BLE_ADDRESS", "DE:C7:8C:52:03:93")
BLE_TYPE = btle.ADDR_TYPE_RANDOM
BLE_READ_PERIOD = 2
BLE_RECONNECT_DELAY = 1
BLE_INACTIVITY_TIMEOUT = 300
BLE_INACTIVITY_DELAY = 130

# Logging configuration
logging.basicConfig(
    format="%(asctime)s.%(msecs)03d [%(process)d] %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

class HealthMonitor:
    def __init__(self):
        self.influx_client = InfluxDBClient(url=INFLUXDB_URL, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG)
        self.write_api = self.influx_client.write_api(write_options=SYNCHRONOUS)
        self.peripheral = btle.Peripheral()
        self.start_time = datetime.now()

    def send_data(self, bpm, spo2, pi, movement, battery, user="user"):
        point = (
            Point("Health")
            .tag("host", user)
            .field("bpm", bpm)
            .field("spo2", spo2)
            .field("pi", pi)
            .field("movement", movement)
            .field("battery", battery)
        )
        self.write_api.write(bucket=INFLUXDB_BUCKET, record=point)

    def sleep(self, period):
        msperiod = period * 1000
        dt = datetime.now() - self.start_time
        ms = (dt.days * 24 * 60 * 60 + dt.seconds) * 1000 + dt.microseconds / 1000.0
        sleep_time = msperiod - (ms % msperiod)
        time.sleep(sleep_time / 1000)

    def run(self):
        while True:
            try:
                logger.info(f"BLE: Connecting to device {BLE_ADDRESS}...")
                self.peripheral.connect(BLE_ADDRESS, BLE_TYPE)
                logger.info(f"BLE: Connected to device {BLE_ADDRESS}")
                self.peripheral.setDelegate(ReadDelegate(self))
                self.setup_ble_service()
                self.read_data()
            except btle.BTLEException as e:
                logger.warning(f"BTLEException: {e}")
            except Exception as e:
                logger.error(f"Exception: {e}")
            finally:
                logger.info(f"BLE: Waiting {BLE_RECONNECT_DELAY} seconds to reconnect...")
                time.sleep(BLE_RECONNECT_DELAY)

    def setup_ble_service(self):
        ble_uuid = "14839ac4-7d7e-415c-9a42-167340cf2339"
        ble_write_uuid_prefix = "8b00ace7"
        ble_notify_uuid_prefix = "00002902"
        write_bytes = b"\xaa\x17\xe8\x00\x00\x00\x00\x1b"
        subscribe_bytes = b"\x01\x00"

        service = self.peripheral.getServiceByUUID(ble_uuid)
        if service is None:
            raise ValueError("BLE service not found")

        self.write_handle = None
        self.subscribe_handle = None

        for desc in service.getDescriptors():
            str_uuid = str(desc.uuid).lower()
            if str_uuid.startswith(ble_write_uuid_prefix):
                self.write_handle = desc.handle
            elif str_uuid.startswith(ble_notify_uuid_prefix):
                self.subscribe_handle = desc.handle

        if self.write_handle is None or self.subscribe_handle is None:
            raise ValueError("Required BLE handles not found")

        self.peripheral.writeCharacteristic(self.subscribe_handle, subscribe_bytes, withResponse=True)
        self.peripheral.writeCharacteristic(self.write_handle, write_bytes, withResponse=True)

    def read_data(self):
        logger.info("Reading from device...")
        while True:
            self.peripheral.waitForNotifications(1.0)
            self.sleep(BLE_READ_PERIOD)

class ReadDelegate(btle.DefaultDelegate):
    def __init__(self, health_monitor):
        super().__init__()
        self.health_monitor = health_monitor

    def handleNotification(self, handle, data):
        spo2 = data[7]
        bpm = data[8]
        pi = data[17]
        movement = data[16]
        battery = data[14]
        logger.info(f"SPO2: {spo2}, BPM: {bpm}, PI: {pi}, Movement: {movement}, Battery: {battery}")
        self.health_monitor.send_data(bpm, spo2, pi, movement, battery)

if __name__ == "__main__":
    if not INFLUXDB_TOKEN:
        logger.error("INFLUXDB_TOKEN environment variable is not set")
        sys.exit(1)

    health_monitor = HealthMonitor()
    try:
        health_monitor.run()
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt, exiting")
        sys.exit(0)
