# Danmaku Content Moderation with Amazon Bedrock Guardrails

弹幕（bullet-chat）多语言内容审核 Sample —— 基于 Amazon Bedrock Guardrails 独立 `ApplyGuardrail` API，**无需调用任何大模型**即可对任意短文本做多语言内容审核。

Multilingual short-text content moderation for bullet-chat comments using the standalone `ApplyGuardrail` API — no foundation model invocation required.

## 特性

- **84 种语言**一套配置（Guardrails Standard Tier，中文简体为 Optimized 最高支持级别）
- **零训练零词库**：托管 ML 分类器覆盖仇恨/侮辱/色情/暴力/不当行为 5 大类，返回置信度
- **PII 检测与脱敏**：手机号/邮箱等自动替换为 `{PHONE}` 占位符（防导流场景）
- **批量合并降本**：5 条/批聚合送审 + 命中回溯，成本约为逐条的 1/4~1/5
- 按量计费：Content Filter $0.15 / 1,000 Text Units（1 TU = 1,000 字符），无固定成本

## 内容

| 文件 | 说明 |
|------|------|
| [`TUTORIAL.md`](./TUTORIAL.md) | Step-by-Step 教程：创建 Guardrail（控制台 + CLI）→ 首次调用 → 批量测试 → 降本模式 → 生产集成 checklist |
| [`create_guardrail.sh`](./create_guardrail.sh) | 一键创建 Standard Tier Guardrail（按 Region 自动选择 guardrail profile） |
| [`sample_moderate.py`](./sample_moderate.py) | 单条审核 sample，内置 7 语言 15 条测试弹幕，可替换为真实样本做 POC 评测 |
| [`sample_batch_moderate.py`](./sample_batch_moderate.py) | 批量合并降本 sample（5 条/批 + 命中回溯），生产推荐模式 |

## 快速开始

```bash
# 0. 前置：AWS CLI v2 已配置凭证；IAM 需要 bedrock:CreateGuardrail / bedrock:ApplyGuardrail
pip install boto3

# 1. 创建 Guardrail（记下返回的 guardrailId）
./create_guardrail.sh                        # 默认 us-east-1
# REGION=ap-northeast-1 ./create_guardrail.sh  # 东京（亚太 profile，数据不出亚太）

# 2. 跑 7 语言 15 条样例测试
python3 sample_moderate.py --guardrail-id <guardrailId> --region us-east-1

# 3. 体验批量降本模式
python3 sample_batch_moderate.py --guardrail-id <guardrailId> --region us-east-1
```

## 实测结论（2026-09）

- 中/英/日/韩/越/阿/泰 7 语言 15 条弹幕样例判定 **15/15 正确**，单条端到端延迟 ~0.9s（服务端 300-500ms）
- 违规样例（辱骂/色情/暴力/违法交易）全部拦截且多数 HIGH 置信度，正常弹幕零误杀
- ⚠️ **批量稀释效应**：违规弹幕混入过多正常弹幕会被"稀释"漏检——实测 >8 条/批偶发 miss，**5 条/批 12/12 全部检出**。批量参数调大前请用真实样本验证检出率
- ⚠️ PII 脱敏（ANONYMIZE）仅在 `source=OUTPUT` 方向生效

## 注意事项

- Standard Tier 必须启用跨区域推理（CRIS）：数据在同一地理分区内多 Region 处理（亚太 profile 不出亚太），请确认符合您的数据合规要求
- 默认配额：ApplyGuardrail 100 RPS / Content Filter 200 Text Units/s（可通过 Service Quotas 申请提升）
- 生产环境请发布正式 Guardrail version，不要使用 DRAFT

## 参考文档

- [ApplyGuardrail API](https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails-use-independent-api.html)
- [支持语言列表](https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails-supported-languages.html)
- [Safeguard Tiers](https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails-tiers.html)
- [Bedrock 定价](https://aws.amazon.com/bedrock/pricing/)

## License

MIT-0
