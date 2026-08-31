#!/bin/bash
set -ex

DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
PYTHONPATH="${DIR}/../python/legion_linux" python3 -m unittest discover \
  -s "${DIR}/../python/legion_linux/tests" -v
