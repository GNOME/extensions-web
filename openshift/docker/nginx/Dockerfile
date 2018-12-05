FROM nginx:stable

MAINTAINER Yuri Konotopov <ykonotopov@gnome.org>

COPY nginx.conf /etc/nginx

RUN set -ex \
	&& mkdir -p /extensions-web/www \
	&& chmod g+rwX -R /extensions-web/www \
	&& chmod g+rwX -R /var/log/nginx \
	&& chmod g+rwX -R /var/cache/nginx \
	&& chmod g+rwX -R /var/run
