#!/bin/sh

set -eu

url=https://github.com/P3TERX/GeoLite.mmdb/raw/download/GeoLite2-Country.mmdb
dir=/tmp/geoip
db=$dir/GeoLite2-Country.mmdb
tmp=$db.tmp

trap 'rm -f "$tmp"' EXIT

mkdir -p "$dir"
curl -fsSL --retry 3 --connect-timeout 10 --max-time 300 -o "$tmp" "$url"
mmdblookup --file "$tmp" --ip 1.1.1.1 > /dev/null
chmod 0644 "$tmp"
mv "$tmp" "$db"
