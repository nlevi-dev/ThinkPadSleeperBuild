#!/bin/bash
set -e

PORT=/dev/ttyUSB0
FQBN=arduino:avr:mega
SKETCH=$1

arduino-cli compile --fqbn $FQBN $SKETCH
arduino-cli upload -p $PORT --fqbn $FQBN $SKETCH
arduino-cli monitor -p $PORT --config baudrate=9600
