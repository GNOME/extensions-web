#!/bin/bash

set -ex \
	&& apt-get update \
	&& apt-get install --no-install-recommends --no-install-suggests -y \
		gettext \
	&& rm -r /var/lib/apt/lists/* \
	&& wget -O xapian-core.tar.xz "https://oligarchy.co.uk/xapian/$XAPIAN_VERSION/xapian-core-$XAPIAN_VERSION.tar.xz" \
	&& wget -O xapian-core.tar.xz.asc "https://oligarchy.co.uk/xapian/$XAPIAN_VERSION/xapian-core-$XAPIAN_VERSION.tar.xz.asc" \
	&& wget -O xapian-bindings.tar.xz "https://oligarchy.co.uk/xapian/$XAPIAN_VERSION/xapian-bindings-$XAPIAN_VERSION.tar.xz" \
	&& wget -O xapian-bindings.tar.xz.asc "https://oligarchy.co.uk/xapian/$XAPIAN_VERSION/xapian-bindings-$XAPIAN_VERSION.tar.xz.asc" \
	&& export GNUPGHOME="$(mktemp -d)" \
	&& \
	{ \
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
	test -z "$found" && { echo >&2 "error: failed to fetch GPG key $GPG_KEY" && exit 1; } || true; \
	} \
	&& gpg --batch --verify xapian-core.tar.xz.asc xapian-core.tar.xz \
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
	&& pip install Sphinx\<2.0.0 \
	&& ./configure \
		--with-python3 \
	&& make -j "$(nproc)" \
	&& make install \
	&& pip freeze > /tmp/pip.txt \
	&& pip uninstall -y -r /tmp/pip.txt \
	&& rm /tmp/pip.txt \
	&& find /usr/local -depth \
		\( \
			\( -type d -a \( -name test -o -name tests \) \) \
			-o \
			\( -type f -a \( -name '*.pyc' -o -name '*.pyo' \) \) \
		\) -exec rm -r '{}' + \
	&& rm -r /usr/src/xapian-bindings
