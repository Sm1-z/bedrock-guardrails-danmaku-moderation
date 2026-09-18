# Bedrock Guardrails 弹幕内容审核 — Step-by-Step Tutorial

> 从零开始创建一个多语言弹幕审核 Guardrail 并完成测试与集成。全程约 30 分钟。
> 适用 Region：us-east-1 / us-west-2 / 东京 / 新加坡 / 首尔 等（Standard Tier 支持列表见附录）

## 前置条件

- 一个 AWS 账号，具备 Bedrock 权限（IAM 需要 `bedrock:CreateGuardrail`、`bedrock:ApplyGuardrail`）
- 本地已安装 AWS CLI v2 与 Python 3.9+（`pip install boto3`）
- 已配置凭证：`aws configure` 或环境变量

> **注意**：使用 Guardrails **不需要**申请任何基础模型的 Model Access——ApplyGuardrail 独立于模型调用。

---

## Step 1：创建 Guardrail（控制台方式）

1. 打开 AWS 控制台 → **Amazon Bedrock** → 左侧菜单 **Safeguards → Guardrails** → **Create guardrail**
2. **Step 1 - Provide guardrail details**：
   - Name：`danmaku-moderation`
   - Blocked message：填写拦截后返回的提示语，如 `该弹幕包含违规内容，已被拦截`
   - **展开 Cross-Region inference → 勾选启用**，选择对应的 guardrail profile（美区 `us.guardrail.v1:0`，亚太 `apac.guardrail.v1:0`）——这是使用 Standard Tier 的前提
3. **Step 2 - Configure content filters**：
   - **Tier 选择 Standard**（关键！Classic 不支持中文）
   - 打开 Hate / Insults / Sexual / Violence / Misconduct 五类，强度先全部设 **Medium**
   - Prompt attack 可保持关闭（弹幕不进入 LLM）
4. **Step 3 - Denied topics**（可选）：按需添加平台特有话题，如"赌博导流"，用自然语言写清定义 + 给几条示例弹幕
5. **Step 4 - Word filters**（可选，免费）：上传运营敏感词表（每行一词，≤10,000 词）
6. **Step 5 - Sensitive information filters**（可选）：添加 `Phone`、`Email` 类型，Behavior 选 **Anonymize**（用于弹幕导流脱敏）
7. Step 6 / Step 7 跳过（RAG 与合规校验场景用，弹幕审核不需要）
8. **Step 8 - Review and create** → 创建完成后记下 **Guardrail ID**（形如 `gr-example-id`）

## Step 1'：创建 Guardrail（CLI 方式，等效）

```bash
aws bedrock create-guardrail --region us-east-1 \
  --name "danmaku-moderation" \
  --blocked-input-messaging "该弹幕包含违规内容，已被拦截" \
  --blocked-outputs-messaging "该内容包含违规信息，已被拦截" \
  --cross-region-config '{"guardrailProfileIdentifier": "us.guardrail.v1:0"}' \
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
  }'
```

返回的 `guardrailId` 即后续 API 调用使用的 ID。

> 亚太区（东京/新加坡/首尔）把 `--region` 换成 `ap-northeast-1` 等，profile 换成 `apac.guardrail.v1:0`。

---

## Step 2：第一次审核调用（单条弹幕）

```bash
aws bedrock-runtime apply-guardrail \
  --region us-east-1 \
  --guardrail-identifier <你的GuardrailID> \
  --guardrail-version DRAFT \
  --source INPUT \
  --content '[{"text": {"text": "主播就是个废物，全家都是垃圾去死吧"}}]'
```

预期返回（节选）：

```json
{
  "action": "GUARDRAIL_INTERVENED",
  "assessments": [{
    "contentPolicy": {
      "filters": [
        {"type": "INSULTS", "confidence": "HIGH", "action": "BLOCKED"}
      ]
    }
  }]
}
```

- `action = NONE` → 放行
- `action = GUARDRAIL_INTERVENED` → 命中（拦截或脱敏），`assessments` 里有具体类别与置信度

用一条正常弹幕（如"这个视频太好看了"）再试一次，确认返回 `NONE`。

**两个关键参数说明**：

| 参数 | 说明 |
|------|------|
| `guardrail-version` | `DRAFT` 为草稿版（测试用）；生产请先发布正式版本（Step 5） |
| `source` | `INPUT`/`OUTPUT` 均可审文本。**若开启 PII 脱敏（ANONYMIZE），必须用 `OUTPUT`**，INPUT 方向不执行脱敏（实测验证） |

---

## Step 3：批量测试（Python 脚本）

使用配套的 `sample_moderate.py`（见 sample code 目录）：

```bash
pip install boto3
python3 sample_moderate.py --guardrail-id <你的GuardrailID> --region us-east-1
```

脚本会跑内置的 7 语言 15 条样例并输出判定结果。替换 `samples` 列表为自己的真实弹幕样本即可做 POC 评测。

---

## Step 4：批量合并降本（生产推荐）

弹幕平均 20-50 字符，但计费按 Text Unit（1,000 字符）取整——逐条送审浪费 95% 额度。生产集成用"聚合送审、命中回溯"模式：

1. 攒一批弹幕（或 200ms 时间窗），用**换行符**拼接成一段文本
2. 整批送 ApplyGuardrail：`NONE` → 全部放行（1 个 TU 审完一批）
3. `GUARDRAIL_INTERVENED` → 对该批**逐条复检**定位违规条目

> ⚠️ **稀释效应（实测发现）**：一条违规弹幕混入过多正常弹幕会被"稀释"漏检。实测 **8 条以上/批偶发 miss**；**5 条/批**在多违规类型 × 多位置组合下 12/12 全部检出。因此推荐 **BATCH_SIZE = 5** 起步（低拦截率下综合成本约为逐条的 **1/4 ~ 1/5**），POC 阶段用真实弹幕样本验证检出率后再决定是否调大。

参考实现见 `sample_batch_moderate.py`（已内置 5 条/批上限）。

---

## Step 5：发布正式版本 + 生产集成

```bash
# 发布不可变版本（生产环境不要用 DRAFT）
aws bedrock create-guardrail-version \
  --guardrail-identifier <你的GuardrailID> \
  --description "v1 - 上线基线"
# 返回 version 号（如 "1"），生产代码引用该版本
```

生产要点清单：

- [ ] IAM 最小权限：审核服务角色只授 `bedrock:ApplyGuardrail`（可用 resource ARN 限定到具体 guardrail）
- [ ] 限流处理：默认 100 RPS / Content Filter 200 TU/s；收到 `ThrottlingException` 用指数退避 + jitter 重试；量大提前在 Service Quotas 申请提升
- [ ] 分级处置：HIGH 置信度直接拦截，MEDIUM 转人工复审（`assessments` 里逐类别返回置信度）
- [ ] 监控：CloudWatch 指标 `InvocationsIntervened` / `InvocationLatency`，按类别统计命中率
- [ ] 迭代：调整过滤强度后重新发布 version，灰度切换

---

## 常见问题（FAQ）

**Q: 需要开通/申请哪些模型？**
不需要。ApplyGuardrail 不调用任何基础模型，开通 Bedrock 服务即可用。

**Q: 中文繁体支持吗？**
Standard Tier 下简体 = Optimized（最高级别），繁体 = Supported（已测试未专门调优）。繁体内容建议 POC 阶段重点验证。

**Q: 数据会出境吗？**
Standard Tier 使用跨区域推理，数据在**同一地理分区内**多 Region 处理（亚太 profile 不出亚太、美区 profile 不出美国）。数据不用于模型训练。

**Q: 一次请求最多传多少文本？**
单请求 content 建议控制在几个 Text Unit 内（每 1,000 字符 = 1 TU 计费）；配额瓶颈通常在 TU/s 而非请求数。

**Q: 想按自己的类别体系（如"剧透""引战"）审核怎么办？**
用 Denied Topics 自然语言定义（每条 ≤1,000 字符 + 示例句），语义级匹配。超出 30 个话题或需要更细分类时，可叠加小模型分类器处理长尾。

---

## 附录

- Standard Tier 支持 Region（部分）：us-east-1、us-east-2、us-west-2、东京、首尔、新加坡、雅加达、悉尼、孟买、法兰克福、爱尔兰等
- 官方文档：
  - ApplyGuardrail API: https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails-use-independent-api.html
  - 支持语言: https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails-supported-languages.html
  - Tier 说明: https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails-tiers.html
  - 定价: https://aws.amazon.com/bedrock/pricing/
