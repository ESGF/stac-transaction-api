#!/usr/bin/env bash
set -euo pipefail

ENVIRONMENT=${1:-}
PROJECT="transaction-api"
REGION="us-east-1"
ENV_FILE=""

if [[ -z "$ENVIRONMENT" ]]; then
  echo "Usage: $0 <environment> [--env-file <path>]"
  exit 1
fi

shift
while [[ $# -gt 0 ]]; do
  case "$1" in
    --env-file)
      ENV_FILE="${2:-}"
      if [[ -z "$ENV_FILE" ]]; then
        echo "Error: --env-file requires a path argument"
        exit 1
      fi
      shift 2
      ;;
    *)
      echo "Unknown option: $1"
      echo "Usage: $0 <environment> [--env-file <path>]"
      exit 1
      ;;
  esac
done

if [[ -n "$ENV_FILE" ]]; then
  if [[ ! -f "$ENV_FILE" ]]; then
    echo "Error: .env file not found at $ENV_FILE"
    exit 1
  fi

  echo ""
  echo "Reading from $ENV_FILE..."

  while IFS= read -r LINE || [[ -n "$LINE" ]]; do
    [[ "$LINE" =~ ^\s*# ]] && continue
    [[ -z "${LINE// }" ]] && continue
    KEY="${LINE%%=*}"
    VALUE="${LINE#*=}"
    KEY="${KEY#"${KEY%%[![:space:]]*}"}"
    KEY="${KEY%"${KEY##*[![:space:]]}"}"
    if [[ "$VALUE" =~ ^\".*\"$ ]] || [[ "$VALUE" =~ ^\'.*\'$ ]]; then
      VALUE="${VALUE:1:${#VALUE}-2}"
    fi
    export "$KEY=$VALUE"
  done < "$ENV_FILE"

  REQUIRED=(
    BOOTSTRAP_SERVERS
    CONFLUENT_CLOUD_USERNAME
    CONFLUENT_CLOUD_PASSWORD
    GLOBUS_CLIENT_ID
    GLOBUS_CLIENT_SECRET
    TOPIC
  )

  MISSING=()
  for KEY in "${REQUIRED[@]}"; do
    if [[ -z "${!KEY:-}" ]]; then
      MISSING+=("$KEY")
    fi
  done

  if [[ ${#MISSING[@]} -gt 0 ]]; then
    echo "Error: missing required keys in $ENV_FILE:"
    for KEY in "${MISSING[@]}"; do
      echo "  - $KEY"
    done
    exit 1
  fi

  echo "  ✓ All required keys found"

else
  echo ""
  echo "Enter values for $PROJECT/$ENVIRONMENT secrets"
  echo "─────────────────────────────────────────────"

  read -p  "BOOTSTRAP_SERVERS:         " BOOTSTRAP_SERVERS
  read -p  "CONFLUENT_CLOUD_USERNAME:  " CONFLUENT_CLOUD_USERNAME
  read -sp "CONFLUENT_CLOUD_PASSWORD:  " CONFLUENT_CLOUD_PASSWORD; echo
  read -p  "GLOBUS_CLIENT_ID:          " GLOBUS_CLIENT_ID
  read -sp "GLOBUS_CLIENT_SECRET:      " GLOBUS_CLIENT_SECRET; echo
  read -p  "TOPIC:                     " TOPIC
fi

SECRET_NAME="${PROJECT}/${ENVIRONMENT}"

SECRET_JSON=$(jq -n \
  --arg bs  "$BOOTSTRAP_SERVERS" \
  --arg ccu "$CONFLUENT_CLOUD_USERNAME" \
  --arg ccp "$CONFLUENT_CLOUD_PASSWORD" \
  --arg gid "$GLOBUS_CLIENT_ID" \
  --arg gs  "$GLOBUS_CLIENT_SECRET" \
  --arg t   "$TOPIC" \
  '{
    BOOTSTRAP_SERVERS:        $bs,
    CONFLUENT_CLOUD_USERNAME: $ccu,
    CONFLUENT_CLOUD_PASSWORD: $ccp,
    GLOBUS_CLIENT_ID:         $gid,
    GLOBUS_CLIENT_SECRET:     $gs,
    TOPIC:                    $t
  }')

echo ""
echo "Writing to Secrets Manager..."

if aws secretsmanager describe-secret \
    --region "$REGION" \
    --secret-id "$SECRET_NAME" \
    --no-cli-pager &>/dev/null; then
  aws secretsmanager put-secret-value \
    --region "$REGION" \
    --secret-id "$SECRET_NAME" \
    --secret-string "$SECRET_JSON" \
    --no-cli-pager
  echo "  ✓ updated: $SECRET_NAME"
else
  aws secretsmanager create-secret \
    --region "$REGION" \
    --name "$SECRET_NAME" \
    --secret-string "$SECRET_JSON" \
    --no-cli-pager
  echo "  ✓ created: $SECRET_NAME"
fi

echo ""
echo "✅ Done. All secrets stored under:"
echo "   $SECRET_NAME"