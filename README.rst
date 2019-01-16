==============
SweetTooth-Web
==============

**SweetTooth-Web** is a Django-powered web application that, in co-operation
with some GNOME Shell integration helper (`NPAPI plugin`_ or `Browser extension`_)
allows users to install, upgrade and enable/disable their own Shell Extensions.
All operations with the Shell are done through a special helper which proxies
over to the Shell by DBus.

Since extensions can be dangerous, all extensions uploaded to the repository
must go through code review and testing.

.. _NPAPI plugin: http://git.gnome.org/browse/gnome-shell/tree/browser-plugin
.. _Browser extension: https://git.gnome.org/browse/chrome-gnome-shell/

Requirements
------------

Python Requirements:
  * django_
  * django-autoslug_
  * Pygments_
  * django-registration_
  * pillow_

.. _django: http://www.djangoproject.com/
.. _django-autoslug: http://packages.python.org/django-autoslug/
.. _Pygments: http://www.pygments.org/
.. _south: http://south.aeracode.org/
.. _django-registration: http://pypi.python.org/pypi/django-registration
.. _pillow: https://github.com/python-pillow/Pillow


System-wide Requirements:
  * `xapian (xapian-core and xapian-bindings)`_

.. _xapian (xapian-core and xapian-bindings): http://www.xapian.org/ 


Getting Started
---------------
Make sure that you have xapian (xapian-core and xapian-bindings) installed in your system.

You can get started developing the website with::

  $ git clone https://git.gnome.org/browse/extensions-web
  $ cd extensions-web
  $ virtualenv --system-site-packages ./venv

I use `--system-site-packages` because we require Xapian, which doesn't have
its Python bindings in PyPI.
::

  $ . ./venv/bin/activate
  $ pip install -r ../requirements.txt

This will get all the needed PyPi packages in our virtual environment.

Create file "local_settings.py" (in the project root folder) and add the following settings:
::
    SECRET_KEY = 'super-random-secret-passphrase'
    ALLOWED_HOSTS = ['*']
    DEBUG = True

Once you've done that, proceed with the database migrations:
::
  $ python manage.py migrate
  $ python mange.py createsuperuser --username=joe --email=joe@email.com

After above steps your database should be initialized and almost ready to run.

You should manually specify your site's domain with SQL update:
::

  UPDATE `django_site`
  SET `domain` = 'your.domain.name',
      `name` = 'your.domain.name'
  WHERE `django_site`.`id` = 1;

And to start the webserver:
::

  $ python manage.py runserver

Log in using superuser account. You should be able to upload and review extensions.

.. _virtualenv: http://www.virtualenv.org/
.. _pip: http://www.pip-installer.org/

Testing with the Shell
======================

If you have GNOME Shell, and you want to test the installation system, you're
going to have to hack your system. For security reasons, the browser plugin and
GNOME Shell both ping the URL https://extensions.gnome.org directly. The
easiest way to get around this is to make a development environment with the
proper things that it needs. Since the Django development server doesn't
natively support SSL connections, we need to install Apache. Follow the
instructions above to get a proper SweetTooth checkout, and then::

  # Install Apache
  $ sudo yum install httpd mod_wsgi mod_ssl

  # Generate a self-signed cert
  $ openssl req -new -nodes -out ego.csr -keyout extensions.gnome.org.key
  # Answer questions. The only one required is the Common Name. You must put
  # extensions.gnome.org -- the hostname -- as the answer.

  $ openssl x509 -req -in ego.csr -signkey extensions.gnome.org.key -out extensions.gnome.org.crt
  $ rm ego.csr
  $ chmod 600 extensions.gnome.org.key

  # Install it on your system.
  $ sudo cp extensions.gnome.org.crt /etc/pki/tls/certs/
  $ sudo cp --preserve=mode extensions.gnome.org.key /etc/pki/tls/private/

  # The shell will look for a special file called 'extensions.gnome.org.crt',
  # for development purposes. Otherwise it will use your system's CA bundle.
  $ mkdir -p ~/.local/share/gnome-shell
  $ cp extensions.gnome.org.crt ~/.local/share/gnome-shell/

  # Configure Apache.
  $ cp etc/sweettooth.wsgi.example ./sweettooth.wsgi
  $ $EDITOR ./sweettooth.wsgi

  $ cp etc/sweettooth.httpd.conf.example ./sweettooth.httpd.conf
  $ $EDITOR ./sweettooth.httpd.conf
  $ sudo cp sweettooth.httpd.conf /etc/httpd/conf.d/sweettooth.conf

  # Edit /etc/hosts
  $ sudo tee -a /etc/hosts <<< 'extensions.gnome.org 127.0.0.1'


