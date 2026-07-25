#!/bin/sh
set -eu

url=${NEWTON_CONTROL_URL:-http://127.0.0.1:18080}
package=${1:?usage: $0 /packages/path.pkg package-symbol}
symbol=${2:?usage: $0 /packages/path.pkg package-symbol}

curl -fsS -X POST "$url/install" --data-binary "$package"
curl -fsS -X POST "$url/newtonscript" --data-binary "GetRoot().|$symbol|:Open();"
