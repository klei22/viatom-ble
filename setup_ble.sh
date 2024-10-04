#!/bin/bash


hcitool dev
sudo hcitool lescan
# LE Scan ... find the address and use in gattool line
# DD:DD:DD:DD:DD:DD O2M 6922
sudo apt-get install --no-install-recommends bluetooth
sudo btmgmt le on

echo "type connect into the following interactive prompt"
echo "Then in the tool use the following prompts:"
echo "[DD:DD:DD:DD:DD:DD][LE]> connect"
echo "Attempting to connect to DD:DD:DD:DD:DD:DD"
echo "Connection successful"
echo "[DD:DD:DD:DD:DD:DD][LE]> quit"

# Start gattool interactive prompt
sudo gatttool -t random -b DD:DD:DD:DD:DD:DD -I

