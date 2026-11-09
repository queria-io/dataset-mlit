#!/usr/bin/env bash
# 入札結果の原本は data/assets に置く。fdl commit がリポジトリに無いものを assets/<sha256> に上げる
mkdir -p data/assets
export FDL_ASSETS="${FDL_ASSETS:-$PWD/data/assets}"
exec "$(dirname "$0")/../shared/scripts/build-fdl.sh" "$@"
