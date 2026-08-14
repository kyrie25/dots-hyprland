#!/bin/bash

if [ "$#" -lt 2 ]; then
    exit 1
fi

COVER_URL=$1
COVER_PATH=$2
shift 2

if [ -n "$COVER_URL" ] && [ -n "$COVER_PATH" ]; then
    mkdir -p "$(dirname "$COVER_PATH")"
    if [ ! -s "$COVER_PATH" ]; then
        TEMP_PATH="${COVER_PATH}.part"
        rm -f "$TEMP_PATH"
        if curl --fail --location --silent --show-error --connect-timeout 3 --max-time 10 \
            --output "$TEMP_PATH" "$COVER_URL"; then
            mv -f "$TEMP_PATH" "$COVER_PATH"
        else
            rm -f "$TEMP_PATH"
        fi
    fi
fi

if [ -s "$COVER_PATH" ]; then
    exec notify-send -i "$COVER_PATH" "$@"
fi

exec notify-send "$@"
