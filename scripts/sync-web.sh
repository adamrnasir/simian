#!/bin/sh
# Copies the shared Simian modules and tests from the website repository.
# web/index.html, shell.css, and main.cjs are specific to the Electron app.
set -eu
site=${1:-"$(dirname "$0")/../../adamrnasir.github.io"}
root="$(dirname "$0")/.."
for file in engine.mjs renderer.mjs app.mjs aim.mjs clock.mjs gravity.mjs simian.css; do
  cp "$site/experiments/simian/$file" "$root/web/$file"
done
cp "$site/theme.js" "$site/grain.svg" "$site/favicon.svg" "$root/web/"
sed "s#'\.\./experiments/simian/#'../web/#" "$site/tests/simian.test.mjs" > "$root/tests/simian.test.mjs"
