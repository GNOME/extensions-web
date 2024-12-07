#!/bin/sh

python manage.py loaddata \
    --exclude auth.permission \
    --exclude contenttypes \
    --verbosity 3 \
    dump.jsonl.gz
