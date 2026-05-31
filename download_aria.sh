#!/bin/bash
# download_qwen3_14b_4bit.sh
# جایگزینی Qwen3-14B-6bit → 4bit (مناسب M3 Pro 18GB)
#
# Why this script exists (aria2 instead of huggingface_hub.snapshot_download):
#
#  1. Parallel TCP streams. `--max-connection-per-server=16 --split=16` pulls
#     each multi-GB shard through 16 sockets at once. huggingface_hub uses one
#     connection per file, so on a throttled / high-latency link (typical here)
#     it leaves most of the bandwidth on the table. Empirically 5–10× faster
#     for the 9 GB Qwen3-14B-4bit checkpoint.
#
#  2. Survives flaky networks. `--continue=true --max-tries=0 --retry-wait=5`
#     plus the outer `until aria2c ...; do sleep 10; done` loop means a dropped
#     connection resumes from the last byte, indefinitely. snapshot_download
#     resumes too, but its retry budget is finite and a hard failure leaves
#     you re-running the whole Python entrypoint.
#
#  3. Explicit shard discovery. We parse model.safetensors.index.json and
#     download only the shards it lists — no risk of incidentally pulling
#     alternate weight formats (.gguf, .bin, fp16 copies) that some HF repos
#     ship alongside the MLX 4-bit set.
#
#  4. caffeinate -dimsu -w $$. Keeps the Mac awake for the multi-hour pull.
#     huggingface_hub does nothing here; lid-close mid-download = restart.
#
#  5. No Python at download time. Pure bash + curl + aria2c, runnable before
#     `uv sync` has finished installing mlx-lm.
#
# Prereq: `brew install aria2`. Run once; the speakloop runtime then loads
# the model from $HOME/.speakloop/models/... via the normal manifest path.
set -e

# Hugging Face read-token. Required even for public model repos because the
# Authorization header is sent on every request below; get one at
# https://huggingface.co/settings/tokens (Read scope is enough) and export it:
#   export HF_TOKEN=hf_xxx
TOKEN="${HF_TOKEN:?Set HF_TOKEN to a Hugging Face access token (https://huggingface.co/settings/tokens)}"
MODEL="mlx-community/Qwen3-14B-4bit"
OLD_DEST="$HOME/.speakloop/models/mlx-community__Qwen3-14B-6bit"
DEST="$HOME/.speakloop/models/mlx-community__Qwen3-14B-4bit"
BASE_URL="https://huggingface.co/$MODEL/resolve/main"

# ----- مرحله ۱: حذف مدل ۶-بیتی قدیمی -----
if [ -d "$OLD_DEST" ]; then
    OLD_SIZE=$(du -sh "$OLD_DEST" 2>/dev/null | cut -f1)
    echo "==> Deleting old 6-bit model ($OLD_SIZE)"
    rm -rf "$OLD_DEST"
    echo "    ok deleted"
fi

# ----- مرحله ۲: caffeinate -----
echo "==> Activating caffeinate"
caffeinate -dimsu -w $$ &
CAFFEINATE_PID=$!
trap "kill $CAFFEINATE_PID 2>/dev/null; exit" INT TERM EXIT

mkdir -p "$DEST"
cd "$DEST"

# ----- مرحله ۳: دانلود فایل‌های متادیتا (کوچیک، با curl) -----
echo ""
echo "==> Downloading metadata files"
META_FILES=(
    "config.json"
    "tokenizer.json"
    "tokenizer_config.json"
    "special_tokens_map.json"
    "vocab.json"
    "merges.txt"
    "added_tokens.json"
    "generation_config.json"
    "chat_template.jinja"
    "model.safetensors.index.json"
    "README.md"
)

for file in "${META_FILES[@]}"; do
    echo -n "    $file ... "
    if curl -L -f -s -o "$DEST/$file" \
         -H "Authorization: Bearer $TOKEN" \
         --retry 5 --retry-delay 3 \
         "$BASE_URL/$file"; then
        echo "ok"
    else
        echo "(not in repo, skipping)"
        rm -f "$DEST/$file"
    fi
done

# ----- مرحله ۴: کشف لیست shard ها از index.json -----
echo ""
if [ -f "$DEST/model.safetensors.index.json" ]; then
    SHARDS=$(python3 -c "
import json
with open('$DEST/model.safetensors.index.json') as f:
    data = json.load(f)
print('\n'.join(sorted(set(data['weight_map'].values()))))
")
else
    # اگه index نبود، یعنی فقط یه فایل safetensors هست
    SHARDS="model.safetensors"
fi

echo "==> Shards to download:"
echo "$SHARDS" | sed 's/^/    /'

# ----- مرحله ۵: دانلود shards با aria2 -----
echo ""
echo "==> Downloading shards (aria2, 16 threads)"
START_TIME=$(date +%s)

while IFS= read -r shard; do
    [ -z "$shard" ] && continue
    echo ""
    echo "==> $shard"
    
    until aria2c \
              --max-connection-per-server=16 \
              --split=16 \
              --min-split-size=1M \
              --continue=true \
              --max-tries=0 \
              --retry-wait=5 \
              --connect-timeout=30 \
              --header="Authorization: Bearer $TOKEN" \
              --out="$shard" \
              --dir="$DEST" \
              "$BASE_URL/$shard"; do
        echo "    !! Failed, retrying in 10s..."
        sleep 10
    done
    
    echo "    ok"
done <<< "$SHARDS"

END_TIME=$(date +%s)
ELAPSED=$((END_TIME - START_TIME))
HOURS=$((ELAPSED / 3600))
MINUTES=$(((ELAPSED % 3600) / 60))

echo ""
echo "================================================"
echo "=== Done in ${HOURS}h ${MINUTES}m ==="
echo "================================================"
ls -lh "$DEST"
echo ""
du -sh "$DEST"