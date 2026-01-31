#!/usr/bin/env bash

# 逐个运行 visualization 目录下的脚本，并记录日志
# 用法：直接在终端执行本脚本

set -u
set -o pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="${SCRIPT_DIR}/logs/retry_single"
mkdir -p "${LOG_DIR}"

source /home/ljt/miniconda3/bin/activate green_methanol_for_port_transportation

# OpenMP/BLAS 限制，尽量避免 SHM 相关错误
export KMP_SHM_DISABLE=1
export KMP_AFFINITY=disabled
export OMP_WAIT_POLICY=PASSIVE
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1

echo "Working dir: ${SCRIPT_DIR}"
echo "Logs dir: ${LOG_DIR}"

ok_count=0
fail_count=0

for f in "${SCRIPT_DIR}"/*.py; do
  bn="$(basename "${f}" .py)"
  log="${LOG_DIR}/${bn}.log"
  echo "==> Running ${f}"
  python "${f}" >"${log}" 2>&1
  code=$?
  if [ "${code}" -ne 0 ]; then
    echo "!! FAILED: ${f} (exit ${code})"
    tail -n 5 "${log}"
    fail_count=$((fail_count + 1))
  else
    echo "OK: ${f}"
    ok_count=$((ok_count + 1))
  fi
done

echo ""
echo "Done. OK=${ok_count}, FAILED=${fail_count}"
if [ "${fail_count}" -ne 0 ]; then
  echo "See logs in: ${LOG_DIR}"
fi
