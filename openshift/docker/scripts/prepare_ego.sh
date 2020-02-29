#!/bin/bash

set -ex \
	&& chown www-data:root -R /extensions-web/app \
	&& chown www-data:root /extensions-web/wsgi.ini \
	&& pip install -r requirements.txt \
	&& pip install -r requirements.ego.txt \
	&& EGO_SECRET_KEY=- python manage.py compilemessages \
	&& rm -rf /tmp/ego
