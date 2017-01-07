#!/bin/bash

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd)"

EXPERIMENT_DIR="${SCRIPT_DIR}/.."

PROJECT_DIR="${SCRIPT_DIR}/../../.."

source "${PROJECT_DIR}/scripts/dbash.sh" || exit 1

dbash::cluster_cuda
dbash::mac_cuda

cd ${PROJECT_DIR}

set -x

${PYENV_BIN} experiments/faster_rcnn_knet_finetune/model/train.py  \
            --data_dir="${EXPERIMENT_DIR}/data/pascal_voc_2007/" \
            --log_dir="${EXPERIMENT_DIR}/logs/pascal_voc_2007/" \
            --pos_weight=100 \
            --optimizer_step=0.001 \
            --knet_hlayer_size=200 \
            --softmax_loss=False \
            --softmax_kernel=True \
            --n_kernels=50 \
            --start_from_scratch=True \
            --eval_step=50\
            --logging_to_stdout=False
