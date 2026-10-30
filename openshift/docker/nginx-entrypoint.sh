#!/bin/sh

set -eu

mkdir -p /tmp/geoip /tmp/nginx/client_body /tmp/nginx/proxy /tmp/nginx/fastcgi /tmp/nginx/uwsgi /tmp/nginx/scgi

sh /usr/local/bin/geoip-update.sh

envsubst '$EGO_NODE_ADDRESS' < /etc/nginx/templates/default.conf.template > /tmp/nginx/default.conf

(
    while :; do
        sleep 86400
        sh /usr/local/bin/geoip-update.sh || echo "GeoIP database refresh failed" >&2
    done
) &

exec "$@"
