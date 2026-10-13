#!/bin/bash

set -exo pipefail

exec uwsgi --enable-threads --ini /extensions-web/wsgi.ini
