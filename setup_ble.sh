#!/bin/bash


hcitool dev
sudo hcitool lescan
# LE Scan ...
# DE:C7:8C:52:03:93 O2M 6922
sudo apt-get install --no-install-recommends bluetooth
sudo btmgmt le on

echo "type connect into the following interactive prompt"
sudo gatttool -t random -b DE:C7:8C:52:03:93 -I

#[DE:C7:8C:52:03:93][LE]> connect
# Attempting to connect to DE:C7:8C:52:03:93
# Connection successful
#[DE:C7:8C:52:03:93][LE]> quit
