FROM nginx:stable

MAINTAINER Yuri Konotopov <ykonotopov@gnome.org>

COPY nginx.conf /tmp

RUN set -ex \
	&& envsubst < /tmp/nginx.conf > /etc/nginx/nginx.conf \
	&& rm /tmp/nginx.conf \
	&& mkdir -p /extensions-web/www \
	&& chmod g+rwX -R /extensions-web/www \
	&& chmod g+rwX -R /var/log/nginx \
	&& chmod g+rwX -R /var/cache/nginx \
	&& chmod g+rwX -R /var/run

CMD ["bash"]
