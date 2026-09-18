#!/usr/bin/env python3
"""
Bedrock Guardrails 弹幕审核 — 单条审核 Sample

用法:
    pip install boto3
    python3 sample_moderate.py --guardrail-id <ID> --region us-east-1
    # 审核自定义文本:
    python3 sample_moderate.py --guardrail-id <ID> --text "要审核的弹幕"

说明:
    - source 统一用 OUTPUT: 文本审核行为与 INPUT 一致, 且 PII 脱敏(ANONYMIZE)仅在 OUTPUT 方向生效
    - action == "NONE" 放行; "GUARDRAIL_INTERVENED" 命中(拦截或脱敏)
"""
import argparse
import json
import time

import boto3

# 内置多语言测试样例: (标签, 弹幕文本)
SAMPLES = [
    ("中文-正常", "这个视频太好看了，主角好帅！"),
    ("中文-辱骂", "主播就是个废物，全家都是垃圾去死吧"),
    ("中文-色情", "主播晚上加个微信开车吗，看你的裸照"),
    ("中文-暴力", "信不信我找人砍死你，把你打成残废"),
    ("中文-违法", "出售各种枪支弹药，需要的私聊我"),
    ("中文-导流", "联系方式：13812345678，邮箱 test@qq.com"),
    ("英文-正常", "This episode is amazing, love the plot twist!"),
    ("英文-辱骂", "You are a worthless piece of trash, kill yourself"),
    ("日文-正常", "この動画は最高です！主人公がかっこいい"),
    ("日文-辱骂", "お前はクズだ、死ね、消えろバカ野郎"),
    ("韩文-正常", "이 드라마 정말 재밌어요! 다음 편 기대돼요"),
    ("韩文-辱骂", "이 쓰레기 같은 놈아 꺼져버려 죽어라"),
    ("阿拉伯文-正常", "هذا الفيديو رائع جدا، أحب هذه القصة"),
    ("越南文-辱骂", "Mày là đồ rác rưởi, cút đi chết đi"),
    ("泰文-正常", "วิดีโอนี้สนุกมาก ชอบพระเอกสุดๆ"),
]


def moderate(client, guardrail_id: str, version: str, text: str) -> dict:
    """审核一条弹幕, 返回结构化结果."""
    t0 = time.time()
    resp = client.apply_guardrail(
        guardrailIdentifier=guardrail_id,
        guardrailVersion=version,
        source="OUTPUT",  # PII 脱敏仅 OUTPUT 生效
        content=[{"text": {"text": text}}],
    )
    latency_ms = int((time.time() - t0) * 1000)

    hits = []
    masked_text = None
    for assessment in resp.get("assessments", []):
        for f in assessment.get("contentPolicy", {}).get("filters", []):
            hits.append({"kind": "content", "type": f["type"], "confidence": f["confidence"]})
        for t in assessment.get("topicPolicy", {}).get("topics", []):
            hits.append({"kind": "topic", "type": t["name"], "confidence": "-"})
        for w in assessment.get("wordPolicy", {}).get("customWords", []):
            hits.append({"kind": "word", "type": w["match"], "confidence": "-"})
        for p in assessment.get("sensitiveInformationPolicy", {}).get("piiEntities", []):
            hits.append({"kind": "pii", "type": p["type"], "confidence": p["action"]})

    if resp["action"] == "GUARDRAIL_INTERVENED" and resp.get("outputs"):
        masked_text = resp["outputs"][0].get("text")

    return {
        "text": text,
        "action": resp["action"],          # NONE | GUARDRAIL_INTERVENED
        "hits": hits,                      # 命中的类别/置信度
        "masked_text": masked_text,        # PII 脱敏后的文本(若有)
        "latency_ms": latency_ms,
    }


def main():
    parser = argparse.ArgumentParser(description="Bedrock Guardrails danmaku moderation sample")
    parser.add_argument("--guardrail-id", required=True)
    parser.add_argument("--region", default="us-east-1")
    parser.add_argument("--version", default="DRAFT", help="guardrail version, 生产用正式版本号")
    parser.add_argument("--text", help="审核单条自定义文本; 不传则跑内置 15 条多语言样例")
    args = parser.parse_args()

    client = boto3.client("bedrock-runtime", region_name=args.region)

    if args.text:
        result = moderate(client, args.guardrail_id, args.version, args.text)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    print(f"{'样例':<12} {'判定':<22} {'命中':<40} 延迟")
    print("-" * 90)
    for label, text in SAMPLES:
        r = moderate(client, args.guardrail_id, args.version, text)
        hit_str = ", ".join(f"{h['type']}({h['confidence']})" for h in r["hits"]) or "-"
        print(f"{label:<12} {r['action']:<22} {hit_str:<40} {r['latency_ms']}ms")
        if r["masked_text"]:
            print(f"{'':<12} 脱敏结果: {r['masked_text']}")


if __name__ == "__main__":
    main()
