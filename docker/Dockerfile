FROM python:2

MAINTAINER Yuri Konotopov <ykonotopov@gnome.org>

ENV PYTHONUNBUFFERED 1
ENV XAPIAN_VERSION 1.4.9
ENV GPG_KEY 08E2400FF7FE8FEDE3ACB52818147B073BAD2B07

RUN set -ex \
	&& pip install Sphinx \
	&& wget -O xapian-core.tar.xz "https://oligarchy.co.uk/xapian/$XAPIAN_VERSION/xapian-core-$XAPIAN_VERSION.tar.xz" \
	&& wget -O xapian-core.tar.xz.asc "https://oligarchy.co.uk/xapian/$XAPIAN_VERSION/xapian-core-$XAPIAN_VERSION.tar.xz.asc" \
	&& wget -O xapian-bindings.tar.xz "https://oligarchy.co.uk/xapian/$XAPIAN_VERSION/xapian-bindings-$XAPIAN_VERSION.tar.xz" \
	&& wget -O xapian-bindings.tar.xz.asc "https://oligarchy.co.uk/xapian/$XAPIAN_VERSION/xapian-bindings-$XAPIAN_VERSION.tar.xz.asc" \
	&& export GNUPGHOME="$(mktemp -d)" \
	&& \
	found=''; \
	for server in \
		ha.pool.sks-keyservers.net \
		hkp://keyserver.ubuntu.com:80 \
		hkp://p80.pool.sks-keyservers.net:80 \
		pgp.mit.edu \
	; do \
		echo "Fetching GPG key $GPG_KEY from $server"; \
		gpg --batch --keyserver $server --recv-keys "$GPG_KEY" && found=yes && break; \
	done; \
	test -z "$found" && echo >&2 "error: failed to fetch GPG key $GPG_KEY" && exit 1; \
	gpg --batch --verify xapian-core.tar.xz.asc xapian-core.tar.xz \
	&& gpg --batch --verify xapian-bindings.tar.xz.asc xapian-bindings.tar.xz \
	&& { command -v gpgconf > /dev/null && gpgconf --kill all || :; } \
	&& rm -r "$GNUPGHOME" xapian-core.tar.xz.asc xapian-bindings.tar.xz.asc \
	&& mkdir -p /usr/src/xapian-core \
	&& mkdir -p /usr/src/xapian-bindings \
	&& tar -xJC /usr/src/xapian-core --strip-components=1 -f xapian-core.tar.xz \
	&& rm xapian-core.tar.xz \
	&& tar -xJC /usr/src/xapian-bindings --strip-components=1 -f xapian-bindings.tar.xz \
	&& rm xapian-bindings.tar.xz \
	&& cd /usr/src/xapian-core \
	&& ./configure \
	&& make -j "$(nproc)" \
	&& make install \
	&& ldconfig \
	&& rm -r /usr/src/xapian-core \
	&& cd /usr/src/xapian-bindings \
	&& ./configure \
		--with-python \
	&& make -j "$(nproc)" \
	&& make install \
	&& find /usr/local -depth \
		\( \
			\( -type d -a \( -name test -o -name tests \) \) \
			-o \
			\( -type f -a \( -name '*.pyc' -o -name '*.pyo' \) \) \
		\) -exec rm -r '{}' + \
	&& rm -r /usr/src/xapian-bindings

RUN mkdir -p /extensions-web/app
WORKDIR /extensions-web/app
COPY --chown=www-data:www-data . /extensions-web/app
COPY --chown=www-data:www-data docker/wsgi.ini /extensions-web
RUN set -ex \
	&& pip install -r requirements.txt \
	&& pip install mysql-python \
	&& pip install uWSGI
