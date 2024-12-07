#!/bin/bash

set -exo pipefail

pip-compile --allow-unsafe --generate-hashes --output-file=requirements.txt "${@}"
pip-compile --allow-unsafe --constraint=requirements.txt --extra=dev --generate-hashes --output-file=requirements.dev.txt "${@}"
