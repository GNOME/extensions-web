#!/bin/bash

set -ex

XAPIAN_MODULES=( xapian-core xapian-bindings )
XAPIAN_BINDINGS_CONFIGURE_ARGS=( --with-python3 )
XAPIAN_BUILD_DIR="$(mktemp -d)"
XAPIAN_GPG_KEY=08E2400FF7FE8FEDE3ACB52818147B073BAD2B07
XAPIAN_ROOT=/tmp/xapian-root

export GNUPGHOME="$(mktemp -d)"

found='';
for server in \
	ha.pool.sks-keyservers.net \
	hkp://keyserver.ubuntu.com:80 \
	hkp://p80.pool.sks-keyservers.net:80 \
	pgp.mit.edu \
; do
	echo "Fetching GPG key $XAPIAN_GPG_KEY from $server"
	if gpg --batch --keyserver "$server" --recv-keys "$XAPIAN_GPG_KEY"; then
		found=yes
		break
	fi
done;

if test -z "$found"; then
	echo >&2 "error: failed to fetch GPG key $XAPIAN_GPG_KEY"
	exit 1
fi

pushd "${XAPIAN_BUILD_DIR}"
pip install Sphinx

for module in "${XAPIAN_MODULES[@]}"; do
	wget -O "${module}".tar.xz "https://oligarchy.co.uk/xapian/$XAPIAN_VERSION/${module}-$XAPIAN_VERSION.tar.xz"
	wget -O "${module}".tar.xz.asc "https://oligarchy.co.uk/xapian/$XAPIAN_VERSION/${module}-$XAPIAN_VERSION.tar.xz.asc"

	gpg --batch --verify "${module}".tar.xz.asc "${module}".tar.xz

	mkdir -p "${XAPIAN_BUILD_DIR}/${module}"
	tar -xJC "${XAPIAN_BUILD_DIR}/${module}" --strip-components=1 -f "${module}".tar.xz

	pushd "${XAPIAN_BUILD_DIR}/${module}"

	ARGUMENTS_VARIABLE="${module^^}_CONFIGURE_ARGS"
	ARGUMENTS_VARIABLE="${ARGUMENTS_VARIABLE/-/_}[@]"

	./configure "${!ARGUMENTS_VARIABLE}"
	make -j "$(nproc)"
	make install
	make DESTDIR="${XAPIAN_ROOT}" install

	ldconfig

	popd
done

if command -v gpgconf > /dev/null; then
	gpgconf --kill all
fi

#pip freeze > "${XAPIAN_BUILD_DIR}"/pip.txt
#pip uninstall -y -r "${XAPIAN_BUILD_DIR}"/pip.txt

#rm -r "$GNUPGHOME" "${XAPIAN_BUILD_DIR}"
#unset GNUPGHOME

find "${XAPIAN_ROOT}" -depth \
	\( \
		\( -type d -a \( -name test -o -name tests \) \) \
		-o \
		\( -type f -a \( -name '*.pyc' -o -name '*.pyo' \) \) \
	\) -print -exec rm -r '{}' \;
