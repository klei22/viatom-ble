# viatom-ble

* [Compatability](#compatability)
* [Setup](#setup)
  * [BLE setup](#ble-setup)
  * [InfluxDB Setup](#influxdb-setup)
  * [Test Setup](#test-setup)
* [Todos](#todos)

Python script to read sensor values over BLE from Viatom wearable ring oxygen (SpO2) monitors.

Reads values once every 2 second and logs to console or log file. Also publishes values to an MQTT broker if so configured.

## Compatability

This branch works with the Wellue Wrist Wearable Sleep Monitor, but should theoretically maintain compatibility with
the Viatom ring oxygen monitors:

- PO1
- PO2 (Wellue O2Ring)
- PO3
- PO4
- PO1B.

## Setup

Install BluePy for BLE and InfluxDB

### BLE setup
```
sudo pip install blueply
```

Scan while wearing the device to determine it's BLE address.

*Note: Ensure the device is not connected to any other monitor (ie the mobile app) before scanning.*

```
sudo python viatom-ble.py -s
```

Look for a device with `Complete Local Name` that is associated with the ring monitor device and note its `Device` address (six colon-delimited octets, eg aa:bb:cc:11:22:33)

Edit the python script `viatom-ble.py` and enter the BLE address where the `ble_address` variable is initialized.


### InfluxDB Setup

Change the InfluxDB settings in `py3_health_to_influxdb.py` to match.

Optionally could setup visualizer like Grafana for seeing these in real time.


### Test Setup

Test BLE connectivity while wearing the device.

```
python viatom-ble.py -v -c
```

Start connection with Grafana/InfluxDB with the following:

```
python py3_health_to_influxdb.py -v -c
```

## Todos

Look to organize code, and test/validate the systemctl methods with the new influxdb integration.
