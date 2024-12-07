#!/bin/sh

python manage.py dumpdata \
    --verbosity 1 \
    --natural-foreign \
    --format jsonl \
    -o dump.jsonl.gz
