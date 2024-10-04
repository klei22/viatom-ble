#!/bin/bash


hcitool dev
sudo hcitool lescan
# LE Scan ... find the address and use in gattool line
# DD:DD:DD:DD:DD:DD O2M 6922
sudo apt-get install --no-install-recommends bluetooth
sudo btmgmt le on

device_id="$(python3 -c 'from device_ids import device_ids; print(device_ids[0])')"
echo "# type connect into the following interactive prompt"
echo "# Then in the tool use the following prompts:"
echo "# [$device_id][LE]> connect"
echo "# Attempting to connect to $device_id"
echo "# Connection successful"
echo "# [$device_id[LE]> quit"

# Start gattool interactive prompt

sudo gatttool -t random -b "$device_id" -I

