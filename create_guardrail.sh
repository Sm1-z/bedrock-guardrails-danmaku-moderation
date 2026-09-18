#!/bin/bash
# Bedrock Guardrails 弹幕审核 — 一键创建 Guardrail (Standard Tier)
#
# 用法:
#   ./create_guardrail.sh                  # 默认 us-east-1
#   REGION=ap-northeast-1 ./create_guardrail.sh   # 东京 (亚太 profile, 数据不出亚太)
set -euo pipefail

REGION="${REGION:-us-east-1}"
NAME="${NAME:-danmaku-moderation}"

# 按 Region 选 guardrail profile: 美区 us. / 亚太 apac. / 欧洲 eu.
case "$REGION" in
  ap-*) PROFILE="apac.guardrail.v1:0" ;;
  eu-*) PROFILE="eu.guardrail.v1:0" ;;
  *)    PROFILE="us.guardrail.v1:0" ;;
esac

echo "Creating guardrail '$NAME' in $REGION (profile: $PROFILE) ..."

aws bedrock create-guardrail --region "$REGION" \
  --name "$NAME" \
  --description "Danmaku multilingual content moderation (Standard tier)" \
  --blocked-input-messaging "该弹幕包含违规内容，已被拦截" \
  --blocked-outputs-messaging "该内容包含违规信息，已被拦截" \
  --cross-region-config "{\"guardrailProfileIdentifier\": \"$PROFILE\"}" \
  --content-policy-config '{
    "tierConfig": {"tierName": "STANDARD"},
    "filtersConfig": [
      {"type": "HATE",       "inputStrength": "MEDIUM", "outputStrength": "MEDIUM"},
      {"type": "INSULTS",    "inputStrength": "MEDIUM", "outputStrength": "MEDIUM"},
      {"type": "SEXUAL",     "inputStrength": "MEDIUM", "outputStrength": "MEDIUM"},
      {"type": "VIOLENCE",   "inputStrength": "MEDIUM", "outputStrength": "MEDIUM"},
      {"type": "MISCONDUCT", "inputStrength": "MEDIUM", "outputStrength": "MEDIUM"}
    ]
  }' \
  --sensitive-information-policy-config '{
    "piiEntitiesConfig": [
      {"type": "PHONE", "action": "ANONYMIZE"},
      {"type": "EMAIL", "action": "ANONYMIZE"}
    ]
  }' \
  --output json

echo ""
echo "✅ 创建完成。记下上方 guardrailId, 然后运行:"
echo "   python3 sample_moderate.py --guardrail-id <guardrailId> --region $REGION"
