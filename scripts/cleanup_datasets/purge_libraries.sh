#!/bin/sh

cd "$(dirname "$0")"/../..
python ./scripts/cleanup_datasets/cleanup_datasets.py -d 60 -4 -r "$@" >> ./scripts/cleanup_datasets/purge_libraries.log
