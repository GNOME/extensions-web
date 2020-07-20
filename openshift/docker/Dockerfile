FROM python:3.6-stretch

MAINTAINER Yuri Konotopov <ykonotopov@gnome.org>

ENV PYTHONUNBUFFERED=1 \
	XAPIAN_VERSION=1.4.11 \
	GPG_KEY=08E2400FF7FE8FEDE3ACB52818147B073BAD2B07

ADD build.sh /build.sh
RUN /build.sh && rm -f /build.sh

RUN set -ex \
	&& mkdir -p /extensions-web/app \
	&& mkdir -p /extensions-web/data \
	&& mkdir -p /extensions-web/www \
	&& chmod g+rwX -R /extensions-web/data \
	&& chmod g+rwX -R /extensions-web/www
WORKDIR /extensions-web/app
COPY . /extensions-web/app
COPY openshift/docker/wsgi.ini /extensions-web
RUN set -ex \
	&& chown www-data:root -R /extensions-web/app \
	&& chown www-data:root /extensions-web/wsgi.ini \
	&& pip install -r requirements.txt \
	&& pip install -r requirements.ego.txt \
	&& EGO_SECRET_KEY=- python manage.py compilemessages
