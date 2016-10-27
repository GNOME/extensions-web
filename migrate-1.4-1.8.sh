#!/bin/sh

# Helper script to migrate pre-Django-1.8 installation to current

python manage.py migrate contenttypes --fake-initial
python manage.py migrate auth --fake-initial
python manage.py migrate admin --fake-initial
python manage.py migrate sites --fake-initial
python manage.py migrate django_comments --fake-initial
python manage.py migrate extensions --fake-initial
python manage.py migrate errorreports --fake-initial
python manage.py migrate ratings --fake-initial
python manage.py migrate registration --fake-initial
python manage.py migrate review --fake-initial
python manage.py migrate sessions --fake-initial
python manage.py syncdb
