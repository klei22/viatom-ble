import os
import sys
import time
import logging
from datetime import datetime
import bluepy.btle as btle
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS

# Configuration
INFLUXDB_URL = os.environ.get("INFLUXDB_URL", "http://localhost:8086")
INFLUXDB_TOKEN = os.environ.get("INFLUXDB_TOKEN")
INFLUXDB_ORG = os.environ.get("INFLUXDB_ORG", "chromebook")
INFLUXDB_BUCKET = os.environ.get("INFLUXDB_BUCKET", "health_data")
BLE_ADDRESS = os.environ.get("BLE_ADDRESS", "DE:C7:8C:52:03:93")
BLE_TYPE = btle.ADDR_TYPE_RANDOM
BLE_READ_PERIOD = 2
RETRY_DELAY = 10
BLE_RECONNECT_DELAY = 5
INITIAL_RECONNECT_DELAY = 1
MAX_RECONNECT_DELAY = 60

# Logging configuration
logging.basicConfig(
    format="%(asctime)s.%(msecs)03d [%(process)d] %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

class HealthMonitor:
    def __init__(self):
        self.influx_client = None
        self.write_api = None
        self.peripheral = None
        self.start_time = datetime.now()
        self.reconnect_delay = INITIAL_RECONNECT_DELAY

    def connect_influxdb(self):
        logger.info("Status: Connecting to InfluxDB...")
        try:
            self.influx_client = InfluxDBClient(url=INFLUXDB_URL, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG)
            self.write_api = self.influx_client.write_api(write_options=SYNCHRONOUS)
            logger.info("Status: Successfully connected to InfluxDB")
        except Exception as e:
            logger.error(f"Status: Failed to connect to InfluxDB: {e}")
            time.sleep(RETRY_DELAY)
            self.connect_influxdb()

    def send_data(self, data_dict, user="user"):
        if not self.write_api:
            logger.error("Status: InfluxDB client is not initialized")
            return

        point = Point("Health").tag("host", user)
        for key, value in data_dict.items():
            point = point.field(key, value)

        try:
            self.write_api.write(bucket=INFLUXDB_BUCKET, record=point)
            logger.info(f"Status: Successfully wrote data to InfluxDB: {data_dict}")
        except Exception as e:
            logger.error(f"Status: Failed to write data to InfluxDB: {e}")
            time.sleep(RETRY_DELAY)
            self.reconnect_influxdb()

    def reconnect_influxdb(self):
        logger.info("Status: Attempting to reconnect to InfluxDB...")
        try:
            if self.influx_client:
                self.influx_client.close()
            self.connect_influxdb()
        except Exception as e:
            logger.error(f"Status: Failed to reconnect to InfluxDB: {e}")
            time.sleep(RETRY_DELAY)

    def connect_ble(self):
        logger.info(f"Status: Connecting to BLE device {BLE_ADDRESS}...")
        try:
            self.peripheral = btle.Peripheral(BLE_ADDRESS, BLE_TYPE)
            logger.info(f"Status: Connected to BLE device {BLE_ADDRESS}")
            self.peripheral.setDelegate(ReadDelegate(self))
            self.setup_ble_service()
            self.reconnect_delay = INITIAL_RECONNECT_DELAY
        except Exception as e:
            logger.error(f"Status: Failed to connect to BLE device: {e}")
            self.reconnect_delay = min(self.reconnect_delay * 2, MAX_RECONNECT_DELAY)
            logger.info(f"Status: Retrying in {self.reconnect_delay} seconds...")
            time.sleep(self.reconnect_delay)
            self.connect_ble()

    def setup_ble_service(self):
        logger.info("Status: Setting up BLE service...")
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
        logger.info("Status: BLE service setup completed")

    def run(self):
        while True:
            try:
                logger.info("Status: Starting health monitoring...")
                self.connect_influxdb()
                self.connect_ble()
                self.read_data()
            except KeyboardInterrupt:
                logger.info("Status: KeyboardInterrupt, exiting")
                self.cleanup()
                break
            except Exception as e:
                logger.error(f"Status: Unexpected error: {e}")
                logger.info(f"Status: Reconnecting in {self.reconnect_delay} seconds...")
                time.sleep(self.reconnect_delay)
                self.reconnect_delay = min(self.reconnect_delay * 2, MAX_RECONNECT_DELAY)

    def read_data(self):
        logger.info("Status: Reading data from BLE device...")
        while True:
            time.sleep(2)
            try:
                self.setup_ble_service()
                if self.peripheral.waitForNotifications(1.0):
                    continue
                time.sleep(BLE_READ_PERIOD)
            except btle.BTLEDisconnectError:
                logger.warning("Status: BLE device disconnected")
                time.sleep(BLE_RECONNECT_DELAY)
                self.connect_ble()
            except Exception as e:
                logger.error(f"Status: Error while reading data: {e}")
                time.sleep(RETRY_DELAY)

    def cleanup(self):
        logger.info("Status: Cleaning up resources...")
        if self.influx_client:
            self.influx_client.close()
        if self.peripheral:
            self.peripheral.disconnect()

class ReadDelegate(btle.DefaultDelegate):
    def __init__(self, health_monitor):
        super().__init__()
        self.health_monitor = health_monitor

    def handleNotification(self, handle, data):
        logger.debug(f"Status: Received data: {data.hex()}")
        data_dict = {}

        try:
            if len(data) >= 8:
                data_dict['spo2'] = int(data[7])
            if len(data) >= 9:
                data_dict['bpm'] = int(data[8])
            if len(data) >= 15:
                data_dict['battery'] = int(data[14])
            if len(data) >= 17:
                data_dict['movement'] = int(data[16])
            if len(data) >= 18:
                data_dict['pi'] = int(data[17])

            if data_dict:
                logger.info(f"Status: Processed data: {data_dict}")
                self.health_monitor.send_data(data_dict)
            else:
                logger.warning(f"Status: Received data is too short to process: {len(data)} bytes")
        except Exception as e:
            logger.error(f"Status: Error processing data: {e}")
            logger.debug(f"Status: Data causing error: {data.hex()}")
            self.retry_read_notification()

if __name__ == "__main__":
    if not INFLUXDB_TOKEN:
        logger.error("Status: INFLUXDB_TOKEN environment variable is not set")
        sys.exit(1)

    logger.info("Status: Initializing Health Monitor")
    health_monitor = HealthMonitor()
    health_monitor.run()

