#!/bin/bash
set -e

PORT=/dev/ttyUSB0
FQBN=arduino:avr:mega
QUIET=0

for arg in "$@"; do
    if [[ "$arg" == "--quiet" ]]; then
        QUIET=1
    else
        SKETCH="$arg"
    fi
done

if [[ $QUIET -eq 1 ]]; then
    arduino-cli compile --fqbn $FQBN $SKETCH > /dev/null 2>&1
    arduino-cli upload -p $PORT --fqbn $FQBN $SKETCH > /dev/null 2>&1
    stty -F $PORT 9600 cs8 -cstopb -parenb
    # discard until ready marker, then print everything after
    ready=0
    while IFS= read -r -t 5 line; do
        if [[ $ready -eq 0 ]]; then
            [[ "$line" == *"ready"* ]] && ready=1
        else
            echo "$line"
        fi
    done < $PORT
else
    arduino-cli compile --fqbn $FQBN $SKETCH
    arduino-cli upload -p $PORT --fqbn $FQBN $SKETCH
    arduino-cli monitor -p $PORT --config baudrate=9600
fi
