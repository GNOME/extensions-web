ARG PYTHON_IMAGE=python
ARG PYTHON_VERSION=3.9

FROM $PYTHON_IMAGE:$PYTHON_VERSION as xapian

ARG XAPIAN_VERSION=1.4.19
ENV PYTHONUNBUFFERED=1

COPY openshift/docker/scripts/ /tmp/scripts/
RUN /tmp/scripts/install-xapian.sh

FROM $PYTHON_IMAGE:$PYTHON_VERSION

LABEL author="Yuri Konotopov <ykonotopov@gnome.org>"

RUN set -ex \
	&& apt-get update \
	&& apt-get install \
		--no-install-recommends \
		--no-install-suggests \
		-y \
		gettext \
	&& rm -r /var/lib/apt/lists/* \
	&& mkdir -p /extensions-web/app \
	&& mkdir -p /extensions-web/data \
	&& mkdir -p /extensions-web/www \
	&& chmod g+rwX -R /extensions-web/data \
	&& chmod g+rwX -R /extensions-web/www

WORKDIR /extensions-web/app

COPY --from=xapian /tmp/xapian-root /
COPY . /extensions-web/app
COPY openshift/docker/wsgi.ini /extensions-web

RUN set -ex \
	&& chown www-data:root -R /extensions-web/app \
	&& chown www-data:root /extensions-web/wsgi.ini \
	&& pip install -r requirements.txt \
	&& pip install -r requirements.ego.txt \
	&& EGO_SECRET_KEY=- python manage.py compilemessages
