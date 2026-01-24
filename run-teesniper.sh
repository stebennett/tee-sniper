#!/bin/bash

source .env

go run cmd/tee-sniper/main.go \
    -u ${TS_USERNAME} \
    -p ${TS_PIN} \
    -b ${TS_BASEURL} \
    -d 5 \
    -t 11:15 -e 18:20 \
    -r 60 \
    -a ${APPRISE_URL}
