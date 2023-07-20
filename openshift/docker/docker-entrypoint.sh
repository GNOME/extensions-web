#!/bin/bash

set -exo pipefail

python manage.py collectstatic --noinput
python manage.py migrate
python manage.py init_search

uwsgi --enable-threads --ini /extensions-web/wsgi.ini
