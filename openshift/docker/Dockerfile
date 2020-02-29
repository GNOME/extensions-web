FROM python:3.6-stretch

MAINTAINER Yuri Konotopov <ykonotopov@gnome.org>

ENV PYTHONUNBUFFERED=1 \
	XAPIAN_VERSION=1.4.11 \
	GPG_KEY=08E2400FF7FE8FEDE3ACB52818147B073BAD2B07

COPY openshift/docker/scripts /tmp/ego

RUN /tmp/ego/build_xapian.sh
RUN /tmp/ego/prepare_dirs.sh

WORKDIR /extensions-web/app
COPY . /extensions-web/app
COPY openshift/docker/wsgi.ini /extensions-web

RUN /tmp/ego/prepare_ego.sh
