import json
import sys

def parse_fast(path):
    records = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            d = json.loads(line)
            records[d["id"]] = {
                "id": d["id"],
                "answer": str(d.get("answer") or "").strip(),
                "exact_match": float(d.get("exact_match") or 0.0),
                "semantic_exact_match": float(d.get("semantic_exact_match") or 0.0),
                "f1": float(d.get("f1") or 0.0),
                "is_ambiguous": d.get("is_ambiguous") is True or (isinstance(d.get("ambiguity"), dict) and d["ambiguity"].get("is_ambiguous") is True),
                "ambiguity_status": (d.get("ambiguity") or {}).get("status") if isinstance(d.get("ambiguity"), dict) else d.get("ambiguity_status"),
            }
    return records

oueg = parse_fast("data/results/hybridqa-shard02-100cases-oueg-1024-20260928.jsonl")
direct = parse_fast("data/results/hybridqa-shard02-100cases-direct-llm-1024-20260928.jsonl")

common = [k for k in oueg if k in direct]

oueg_empty = {k for k in common if not oueg[k]["answer"]}
direct_empty = {k for k in common if not direct[k]["answer"]}
ambiguous = {k for k in common if oueg[k]["is_ambiguous"]}

print(f"Total samples: {len(common)}")
print(f"Total Ambiguous samples: {len(ambiguous)} ({len(ambiguous)/len(common)*100:.1f}%)")
print(f"Total Unambiguous samples: {len(common) - len(ambiguous)} ({(len(common)-len(ambiguous))/len(common)*100:.1f}%)\n")

print("=== 1. TỶ LỆ GÁN CỜ AMBIGUITY CỦA CÁC CASE RỖNG ===")
print(f"OUEG có {len(oueg_empty)} case rỗng:")
oueg_empty_amb = oueg_empty & ambiguous
oueg_empty_unamb = oueg_empty - ambiguous
print(f"  - Thuộc nhóm Ambiguous: {len(oueg_empty_amb)} / {len(oueg_empty)} ({len(oueg_empty_amb)/len(oueg_empty)*100:.1f}%)")
print(f"  - Thuộc nhóm Unambiguous: {len(oueg_empty_unamb)} / {len(oueg_empty)} ({len(oueg_empty_unamb)/len(oueg_empty)*100:.1f}%)")

print(f"\nDirect LLM có {len(direct_empty)} case rỗng:")
direct_empty_amb = direct_empty & ambiguous
direct_empty_unamb = direct_empty - ambiguous
print(f"  - Thuộc nhóm Ambiguous: {len(direct_empty_amb)} / {len(direct_empty)} ({len(direct_empty_amb)/len(direct_empty)*100:.1f}%)")
print(f"  - Thuộc nhóm Unambiguous: {len(direct_empty_unamb)} / {len(direct_empty)} ({len(direct_empty_unamb)/len(direct_empty)*100:.1f}%)")

print("\n=== 2. KẾT QUẢ KHI LOẠI BỎ CÁC CASE RỖNG ===")

# Cách A: Xét riêng từng phương pháp trên tập có câu trả lời (Answered only)
oueg_ans = [oueg[k] for k in common if k not in oueg_empty]
direct_ans = [direct[k] for k in common if k not in direct_empty]

em_oueg_ans = sum(r["exact_match"] for r in oueg_ans) / len(oueg_ans) * 100
f1_oueg_ans = sum(r["f1"] for r in oueg_ans) / len(oueg_ans) * 100

em_dir_ans = sum(r["exact_match"] for r in direct_ans) / len(direct_ans) * 100
f1_dir_ans = sum(r["f1"] for r in direct_ans) / len(direct_ans) * 100

print(f"A. Trên tập tự trả lời (Mỗi bên chỉ tính trên các case mình KHÔNG rỗng):")
print(f"  - OUEG (N={len(oueg_ans)}/100):       EM = {em_oueg_ans:.2f}% | F1 = {f1_oueg_ans:.2f}%")
print(f"  - Direct LLM (N={len(direct_ans)}/100): EM = {em_dir_ans:.2f}% | F1 = {f1_dir_ans:.2f}%")

# Cách B: Xét trên tập giao (Cả 2 cùng trả lời được, loại tất cả case rỗng của cả 2)
both_ans = [k for k in common if k not in oueg_empty and k not in direct_empty]
both_oueg = [oueg[k] for k in both_ans]
both_dir = [direct[k] for k in both_ans]

em_both_oueg = sum(r["exact_match"] for r in both_oueg) / len(both_ans) * 100
f1_both_oueg = sum(r["f1"] for r in both_oueg) / len(both_ans) * 100

em_both_dir = sum(r["exact_match"] for r in both_dir) / len(both_ans) * 100
f1_both_dir = sum(r["f1"] for r in both_dir) / len(both_ans) * 100

print(f"\nB. Trên tập chung (CẢ 2 ĐỀU KHÔNG RỖNG, N={len(both_ans)}):")
print(f"  - OUEG:       EM = {em_both_oueg:.2f}% | F1 = {f1_both_oueg:.2f}%")
print(f"  - Direct LLM: EM = {em_both_dir:.2f}% | F1 = {f1_both_dir:.2f}%")
print(f"  - Chênh lệch (OUEG - Direct): {em_both_oueg - em_both_dir:+.2f}% EM | {f1_both_oueg - f1_both_dir:+.2f}% F1")

# Phân rã Ambiguous vs Unambiguous trên tập chung
both_amb = [k for k in both_ans if k in ambiguous]
both_unamb = [k for k in both_ans if k not in ambiguous]

em_oueg_b_amb = sum(oueg[k]["exact_match"] for k in both_amb) / len(both_amb) * 100
f1_oueg_b_amb = sum(oueg[k]["f1"] for k in both_amb) / len(both_amb) * 100
em_dir_b_amb = sum(direct[k]["exact_match"] for k in both_amb) / len(both_amb) * 100
f1_dir_b_amb = sum(direct[k]["f1"] for k in both_amb) / len(both_amb) * 100

em_oueg_b_un = sum(oueg[k]["exact_match"] for k in both_unamb) / len(both_unamb) * 100
f1_oueg_b_un = sum(oueg[k]["f1"] for k in both_unamb) / len(both_unamb) * 100
em_dir_b_un = sum(direct[k]["exact_match"] for k in both_unamb) / len(both_unamb) * 100
f1_dir_b_un = sum(direct[k]["f1"] for k in both_unamb) / len(both_unamb) * 100

print(f"\n  * Chi tiết tập chung - Unambiguous (N={len(both_unamb)}):")
print(f"    - OUEG:       EM = {em_oueg_b_un:.2f}% | F1 = {f1_oueg_b_un:.2f}%")
print(f"    - Direct LLM: EM = {em_dir_b_un:.2f}% | F1 = {f1_dir_b_un:.2f}%")
print(f"  * Chi tiết tập chung - Ambiguous (N={len(both_amb)}):")
print(f"    - OUEG:       EM = {em_oueg_b_amb:.2f}% | F1 = {f1_oueg_b_amb:.2f}%")
print(f"    - Direct LLM: EM = {em_dir_b_amb:.2f}% | F1 = {f1_dir_b_amb:.2f}%")
