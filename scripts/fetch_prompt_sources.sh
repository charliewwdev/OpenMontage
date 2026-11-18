#!/usr/bin/env bash
# Fetch third-party prompt sources at pinned revisions into prompts/library/sources (not committed).
# Used by scripts/import_prompts.py to rebuild studio/config/prompt_library.
set -euo pipefail
cd "$(dirname "$0")/../prompts/library"
mkdir -p sources && cd sources
VB=fd18b3d055cb0fc6f066ca90fe2c3c8cbb698490
LICH=ac5b61177a81343e958f63212c4df7f25dc4c265
RAPI=51fd4dfc8b7ca886328dfb0f95497bd8ec5a19e2
PCHAT=be0e61647a60dac415f7639453f351ce1b4ed585
gh=https://raw.githubusercontent.com
curl -fsSL -o vbench_all_dimension.txt    $gh/Vchitect/VBench/$VB/prompts/all_dimension.txt
curl -fsSL -o vbench_all_dimension_cn.txt $gh/Vchitect/VBench/$VB/prompts/all_dimension_cn.txt
curl -fsSL -o vb_en_human_action.txt      $gh/Vchitect/VBench/$VB/prompts/prompts_per_dimension/human_action.txt
curl -fsSL -o vb_en_temporal_style.txt    $gh/Vchitect/VBench/$VB/prompts/prompts_per_dimension/temporal_style.txt
curl -fsSL -o vb_en_appearance_style.txt  $gh/Vchitect/VBench/$VB/prompts/prompts_per_dimension/appearance_style.txt
curl -fsSL -o vbench_LICENSE              $gh/Vchitect/VBench/$VB/LICENSE
curl -fsSL -o lich_prompts.json           $gh/LichAmnesia/awesome-ad-video-prompts/$LICH/prompts.json
curl -fsSL -o lich_LICENSE                $gh/LichAmnesia/awesome-ad-video-prompts/$LICH/LICENSE
curl -fsSL -o rapidata.parquet https://huggingface.co/datasets/Rapidata/text-2-video-human-preferences-veo3/resolve/$RAPI/data/train-00000-of-00001.parquet
curl -fsSL -o promptschat.csv  https://huggingface.co/datasets/fka/prompts.chat/resolve/$PCHAT/prompts.csv
echo "sources fetched"
