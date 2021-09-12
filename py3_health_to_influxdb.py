import time
import os
import sys
import getopt
import logging
import bluepy.btle as btle
from datetime import datetime
from influxdb import InfluxDBClient

BLE_ADDRESS = "AA:BB:CC:DD:EE:FF"  # replace with your device address


def send_data(bpm, spo2, pi, movement, battery, user="user"):

    host = "localhost"
    port = 8086
    user = "admin"
    password = "password"
    dbname = "demodb"
    json_body = [
        {
            "measurement": "Health",
            "tags": {
                "host": user,
            },
            "fields": {
                "bpm": bpm,
                "spo2": spo2,
                "pi": pi,
                "movement": movement,
                "battery": battery,
            },
        }
    ]

    client = InfluxDBClient(host, port, user, password, dbname)
    client.write_points(json_body)


def sleep(period):
    msperiod = period * 1000
    dt = datetime.now() - start_time
    ms = (dt.days * 24 * 60 * 60 + dt.seconds) * 1000 + dt.microseconds / 1000.0
    sleep = msperiod - (ms % msperiod)
    time.sleep(sleep / 1000)
    dt = datetime.now() - start_time
    ms = (dt.days * 24 * 60 * 60 + dt.seconds) * 1000 + dt.microseconds / 1000.0


class ReadDelegate(btle.DefaultDelegate):
    def __init__(self):
        btle.DefaultDelegate.__init__(self)

    def handleNotification(self, handle, data):
        global ble_fail_count
        global ble_next_reconnect_delay
        print("spo2: ")
        spo2 = data[7]
        print("bpm: ", data[8])
        bpm = data[8]
        print("PI: ", data[17])
        pi = data[17]
        print("movement: ", data[16])
        movement = data[16]
        print("battery: ", data[14])
        battery = data[14]

        send_data(bpm, spo2, pi, movement, battery)


class ScanDelegate(btle.DefaultDelegate):
    def __init__(self):
        btle.DefaultDelegate.__init__(self)

    def handleDiscovery(self, dev, isNewDev, isNewData):
        if isNewDev:
            print("Discovered device", dev.addr)
        elif isNewData:
            print("Received new data from", dev.addr)


def ble_scan():
    scanner = btle.Scanner().withDelegate(ScanDelegate())
    devices = scanner.scan(10.0)

    for dev in devices:
        print("Device %s (%s), RSSI=%d dB" % (dev.addr, dev.addrType, dev.rssi))
        for (adtype, desc, value) in dev.getScanData():
            print("  %s = %s" % (desc, value))


if __name__ == "__main__":

    # ble config params
    # ble address of device
    ble_address = BLE_ADDRESS
    ble_type = btle.ADDR_TYPE_RANDOM
    # seconds to wait between reads
    ble_read_period = 2
    # seconds to wait between btle reconnection attempts
    ble_reconnect_delay = 1
    # seconds of btle inactivity (not worn/calibrating) before force-disconnect
    ble_inactivity_timeout = 300
    # seconds to wait after inactivity timeout before reconnecting resumes
    ble_inactivity_delay = 130

    # other params
    ble_next_reconnect_delay = ble_reconnect_delay
    ble_fail_count = 0
    logfile = "viatom-ble.log"
    console = False
    verbose = False

    try:
        opts, args = getopt.getopt(sys.argv[1:], "hvcsa:m:", ["address=", "mqtt="])
    except getopt.GetoptError:
        print("viatom-ble.py -v -a <ble_address>")
        sys.exit(2)
    for opt, arg in opts:
        if opt == "-h":
            print("viatom-ble.py -v -a <ble_address>")
            sys.exit()
        elif opt == "-v":
            verbose = True
        elif opt == "-c":
            console = True
        elif opt == "-s":
            if os.geteuid() != 0:
                print("Must be root to perform scan")
                sys.exit(3)
            ble_scan()
            sys.exit()
        elif opt in ("-a", "--address"):
            ble_address = arg

    # initialize logger
    if not console or logfile == "":
        print("Logging to " + logfile)
        logging.basicConfig(
            format="%(asctime)s.%(msecs)03d [%(process)d] %(levelname)s %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
            filename=logfile,
            level=logging.DEBUG,
        )
    else:
        print("Logging to console")
        logging.basicConfig(
            format="%(asctime)s.%(msecs)03d [%(process)d] %(levelname)s %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
            level=logging.DEBUG,
        )
    logger = logging.getLogger()

    logger.info("Starting...")

    # Connect to BLE device and write/read infinitely
    peripheral = btle.Peripheral()
    while True:
        try:
            last_time = datetime.now()
            start_time = datetime.now()
            ble_fail_count = 0
            logger.info("BLE: Connecting to device " + ble_address + "...")
            # Connect to the peripheral
            peripheral.connect(ble_address, ble_type)
            logger.info("BLE: Connected to device " + ble_address)
            # Set the notification delegate
            peripheral.setDelegate(ReadDelegate())
            write_handle = None
            subscribe_handle = None
            # magic stuff for the Viatom GATT service
            ble_uuid = "14839ac4-7d7e-415c-9a42-167340cf2339"
            ble_write_uuid_prefix = "8b00ace7"
            write_bytes = b"\xaa\x17\xe8\x00\x00\x00\x00\x1b"

            # this is general magic GATT stuff
            # notify handles will have a UUID that begins with this
            ble_notify_uuid_prefix = "00002902"
            # these are the byte values that we need to write to subscribe/unsubscribe for notifications
            subscribe_bytes = b"\x01\x00"
            # unsubscribe_bytes = b'\x00\x00'

            # find the desired service
            service = peripheral.getServiceByUUID(ble_uuid)
            if service is not None:
                logger.debug("Found service: " + str(service))

                descs = service.getDescriptors()
                # this is the important part-
                # find the handles that we will write to and subscribe for notifications
                for desc in descs:
                    str_uuid = str(desc.uuid).lower()
                    if str_uuid.startswith(ble_write_uuid_prefix):
                        write_handle = desc.handle
                        logger.debug("*** Found write handle: " + str(write_handle))
                    elif str_uuid.startswith(ble_notify_uuid_prefix):
                        subscribe_handle = desc.handle
                        logger.debug(
                            "*** Found subscribe handle: " + str(subscribe_handle)
                        )

            if write_handle is not None and subscribe_handle is not None:
                # we found the handles that we need
                logger.debug("Found both required handles")

                # now that we're subscribed for notifications, waiting for TX/RX...
                logger.info("Reading from device...")
                while True:
                    # this call performs the subscribe for notifications
                    response = peripheral.writeCharacteristic(
                        subscribe_handle, subscribe_bytes, withResponse=True
                    )

                    # this call performs the request for data
                    response = peripheral.writeCharacteristic(
                        write_handle, write_bytes, withResponse=True
                    )

                    peripheral.waitForNotifications(1.0)
                    sleep(ble_read_period)

        except btle.BTLEException as e:
            logger.warning("BTLEException: " + str(e))

        except IOError as e:
            logger.error("IOError: " + str(e))

        except KeyboardInterrupt:
            logger.info("KeyboardInterrupt, exiting")
            sys.exit()

        except:
            e = sys.exc_info()[0]
            logger.error("Exception: " + str(e))

        try:
            logger.info(
                "BLE: Waiting "
                + str(ble_next_reconnect_delay)
                + " seconds to reconnect..."
            )
            time.sleep(ble_next_reconnect_delay)
            ble_next_reconnect_delay = ble_reconnect_delay
        except KeyboardInterrupt:
            logger.info("KeyboardInterrupt, exiting")
            sys.exit()
        except:
            e = sys.exc_info()[0]
            logger.error("Exception: " + str(e))

        logger.info("Exiting...")
