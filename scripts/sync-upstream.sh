#!/bin/bash
# 上游更新后的一键同步：拉取 → 变基本地化层 → 补全翻译键 → 报告待翻译文案。
# 用法：scripts/sync-upstream.sh [上游 remote 名，默认 upstream]
set -euo pipefail

cd "$(dirname "$0")/.."
REMOTE="${1:-upstream}"

echo "==> 拉取 $REMOTE/main"
git fetch "$REMOTE" main

echo "==> 把本地化层变基到最新上游"
git rebase "$REMOTE/main"

echo "==> 更新翻译表（保留旧译文，补新键，删失效键）"
python3 scripts/localization.py sync

echo "==> 检查待翻译文案"
python3 scripts/localization.py check

echo "完成。把新增译文填进 Localization/zh-Hans.lproj/Localizable.strings 后提交即可。"
echo "若 git push 受网络限制，可用 GitHub API 推送（参见仓库说明）。"
