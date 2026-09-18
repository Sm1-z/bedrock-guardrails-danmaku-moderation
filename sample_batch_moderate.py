#!/usr/bin/env python3
"""
Bedrock Guardrails 弹幕审核 — 批量合并降本 Sample（生产推荐模式）

原理:
    计费按 Text Unit(1,000 字符)取整, 弹幕平均 20-50 字符, 逐条送审浪费 95% 额度。
    本脚本演示 "聚合送审 + 命中回溯" 模式:
      1. 把一批弹幕拼成块整块送审(块内所有弹幕合计 1 个 TU)
      2. 块判定 NONE → 全部放行(1 次调用审完一批)
      3. 块判定 INTERVENED → 仅对该块逐条复检, 定位具体违规弹幕

⚠️ 稀释效应(实测):
    违规弹幕混入过多正常弹幕会被"稀释"漏检——实测 8 条以上/批偶发 miss,
    5 条/批在多违规类型 × 多位置组合下 12/12 全部检出。
    因此默认 BATCH_SIZE=5(降本约 5 倍且可靠); 调大前请用真实样本验证检出率。

用法:
    python3 sample_batch_moderate.py --guardrail-id <ID> --region us-east-1
    # 从文件读弹幕(每行一条):
    python3 sample_batch_moderate.py --guardrail-id <ID> --input danmaku.txt
"""
import argparse
import time

import boto3

MAX_CHUNK_CHARS = 950  # 留余量, 确保 1 个 Text Unit
BATCH_SIZE = 5         # 每块弹幕条数上限; 实测 >8 条有稀释漏检风险, 调大前先验证


def apply(client, guardrail_id, version, text):
    """调用 ApplyGuardrail, 返回 (action, hits)."""
    resp = client.apply_guardrail(
        guardrailIdentifier=guardrail_id,
        guardrailVersion=version,
        source="OUTPUT",
        content=[{"text": {"text": text}}],
    )
    hits = [
        f"{f['type']}({f['confidence']})"
        for a in resp.get("assessments", [])
        for f in a.get("contentPolicy", {}).get("filters", [])
    ]
    return resp["action"], hits


def chunk_comments(comments, max_chars=MAX_CHUNK_CHARS, batch_size=BATCH_SIZE):
    """把弹幕列表拼成块: 每块 <= batch_size 条且 <= max_chars 字符."""
    chunks, cur, cur_len = [], [], 0
    for c in comments:
        c = c.strip()
        if not c:
            continue
        if cur and (len(cur) >= batch_size or cur_len + len(c) + 1 > max_chars):
            chunks.append(cur)
            cur, cur_len = [], 0
        cur.append(c)
        cur_len += len(c) + 1
    if cur:
        chunks.append(cur)
    return chunks


def moderate_batch(client, guardrail_id, version, comments):
    """批量审核。返回 (results, api_calls): results 为每条弹幕的 (text, verdict, hits)."""
    results = []
    api_calls = 0
    for batch in chunk_comments(comments):
        api_calls += 1
        action, _ = apply(client, guardrail_id, version, "\n".join(batch))
        if action == "NONE":
            results += [(c, "PASS", []) for c in batch]
            continue
        # 块命中 → 逐条复检定位
        for c in batch:
            api_calls += 1
            a, hits = apply(client, guardrail_id, version, c)
            results.append((c, "PASS" if a == "NONE" else "BLOCK", hits))
    return results, api_calls


DEMO_COMMENTS = [
    "这个视频太好看了，主角好帅！", "更新太慢了啊，等不及下一集",
    "背景音乐叫什么名字，好听", "This episode is amazing!",
    "この動画は最高です", "이 드라마 정말 재밌어요",
    "前排围观~", "主播就是个废物，全家都是垃圾去死吧",  # <- 违规
    "太甜了太甜了", "求第二季！！",
    "画质真不错", "弹幕护体",
    "哈哈哈哈哈笑死我了", "泪目…这段看一次哭一次",
    "已三连，冲了",
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--guardrail-id", required=True)
    parser.add_argument("--region", default="us-east-1")
    parser.add_argument("--version", default="DRAFT")
    parser.add_argument("--input", help="弹幕文件, 每行一条; 不传用内置 demo 数据")
    args = parser.parse_args()

    if args.input:
        with open(args.input, encoding="utf-8") as f:
            comments = f.readlines()
    else:
        comments = DEMO_COMMENTS

    client = boto3.client("bedrock-runtime", region_name=args.region)
    t0 = time.time()
    results, api_calls = moderate_batch(client, args.guardrail_id, args.version, comments)
    elapsed = time.time() - t0

    blocked = [r for r in results if r[1] == "BLOCK"]
    print(f"共 {len(results)} 条弹幕 | API 调用 {api_calls} 次 | 拦截 {len(blocked)} 条 | 耗时 {elapsed:.1f}s")
    print(f"(逐条模式需 {len(results)} 次调用/{len(results)} TU; 本次约 {api_calls} TU)")
    print("-" * 70)
    for text, verdict, hits in results:
        mark = "🚫" if verdict == "BLOCK" else "✅"
        hit_str = f"  <- {', '.join(hits)}" if hits else ""
        print(f"{mark} {text[:40]}{hit_str}")


if __name__ == "__main__":
    main()
