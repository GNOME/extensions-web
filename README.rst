==============
SweetTooth-Web
==============

**SweetTooth-Web** is a Django-powered web application that, in co-operation
with some GNOME Shell integration helper (`Browser extension`_)
allows users to install, upgrade and enable/disable their own Shell Extensions.
All operations with the Shell are done through a special helper which proxies
over to the Shell by DBus.

Since extensions can be dangerous, all extensions uploaded to the repository
must go through code review and testing.

.. _Browser extension: https://gitlab.gnome.org/GNOME/chrome-gnome-shell/

Requirements
------------


System Requirements:
  * `python`_ 3.9+
  * `xapian (xapian-core and xapian-bindings)`_

.. _python: https://www.python.org/
.. _xapian (xapian-core and xapian-bindings): https://www.xapian.org/

Python Requirements:
  * django_
  * django-autoslug_
  * django-registration_
  * pillow_
  * Pygments_

.. _django: https://www.djangoproject.com/
.. _django-autoslug: http://packages.python.org/django-autoslug/
.. _django-registration: https://pypi.org/project/django-registration
.. _pillow: https://github.com/python-pillow/Pillow
.. _Pygments: http://pygments.org/


Running with Docker
-------------------

Make sure you have both `Docker`_ and `Docker Compose`_ installed as well as runnning `Docker`_ instance.

You can start website with commands:
::

  $ git clone https://gitlab.gnome.org/Infrastructure/extensions-web.git
  $ cd extensions-web/openshift/docker
  $ docker-compose up --build

That's all! Website will be available as http://localhost:8080.

You also may want to create superuser account - look to virtualenv guide below for
apropriate command and `Docker`_ documentation for a way running command within running
`Docker`_ container.

.. _Docker: https://www.docker.com/
.. _Docker Compose: https://docs.docker.com/compose/


Running with virtualenv
-----------------------

You can get started developing the website with::

  $ git clone https://gitlab.gnome.org/Infrastructure/extensions-web.git
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
  $ python manage.py compilemessages
  $ python manage.py createsuperuser --username=joe --email=joe@email.com

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

If you want to quickly add extensions and/or reviews to them, there are two functions available, the extensions will use boilerplate data:
::

  $ python manage.py populate_extensions <number_of_extensions>

This function will create as many (very simple) extensions as you tell it to.

Then to add a given number of random ratings to all the extensions:
::

  $ python manage.py populate_reviews <number_of_ratings>

This function will create as many ratings into each extension as you tell it to, in this case, the username and the rating content gets randomly picked from a "Lorem Ipsum" string.

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


