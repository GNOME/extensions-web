ARG PYTHON_VERSION

FROM python:$PYTHON_VERSION

LABEL author="Yuri Konotopov <ykonotopov@gnome.org>"

ENV PYTHONUNBUFFERED=1

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

COPY . /extensions-web/app
COPY openshift/docker/wsgi.ini /extensions-web
COPY openshift/docker/docker-entrypoint.sh /

RUN set -ex \
	&& ldconfig \
	&& chown www-data:root -R /extensions-web/app \
	&& chown www-data:root /extensions-web/wsgi.ini \
	&& pip install -r requirements.txt \
	&& EGO_SECRET_KEY=- python manage.py compilemessages

ENTRYPOINT []
CMD [ "/docker-entrypoint.sh" ]
