#!/bin/sh
# 让显式 env 文件成为 Compose 插值的唯一应用配置来源，避免宿主导出变量覆盖发布标签。
set -eu

if [ "$#" -lt 3 ]; then
  echo "usage: compose.sh <env-file> <compose-file> <compose-args...>" >&2
  exit 64
fi

env_file=$1
compose_file=$2
shift 2

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
project_dir=$(CDPATH= cd -- "$script_dir/.." && pwd)
cd "$project_dir"

for name in \
  IMAGE_TAG DOMAIN ACME_EMAIL HTTP_PORT HTTPS_PORT APP_SUBNET CADDY_IPV4 \
  PASSWORD_HASH_FILE CSRF_KEY_FILE PYTHON_IMAGE NODE_IMAGE CADDY_IMAGE \
  COMPOSE_FILE COMPOSE_PROJECT_NAME COMPOSE_PROFILES COMPOSE_ENV_FILES
do
  unset "$name"
done

COMPOSE_DISABLE_ENV_FILE=1 exec docker compose \
  --project-directory "$project_dir" \
  --env-file "$env_file" \
  -f "$compose_file" \
  "$@"
