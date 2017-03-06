#!/bin/bash

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd)"

EXPERIMENT_DIR="${SCRIPT_DIR}/.."

PROJECT_DIR="${SCRIPT_DIR}/../../.."

source "${PROJECT_DIR}/scripts/dbash.sh" || exit 1

dbash::cluster_cuda
dbash::mac_cuda

cd ${PROJECT_DIR}

set -x

${PYENV_BIN} experiments/kitti_ms_cnn/model/train.py  \
            --data_dir="${EXPERIMENT_DIR}/data/" \
            --root_log_dir="${EXPERIMENT_DIR}/logs/" \
            --config_path="${SCRIPT_DIR}/config_cluster.yml"
