"""고정 시험 세트: 규칙·프롬프트를 바꾸기 전과 후의 통과·탈락을 비교한다 (유료, 4일치 약 $0.25).

실행:       python -m tests.fixture_run            # 기준(baseline.json)과 비교
기준 저장:  python -m tests.fixture_run --save     # 바꾼 결과를 새 기준으로 받아들일 때만

주의: Claude 판정은 매번 조금씩 다를 수 있고 원문 페이지도 바뀔 수 있다.
달라진 항목은 problems를 읽고 사람이 판단한다(자동 합격 기준 아님).
"""
import argparse
import json
import tempfile
from pathlib import Path

from agents import insta
from agents.common import Meter

FIX = Path(__file__).parent / "fixtures"
BASELINE = FIX / "baseline.json"


def run_all():
    results, total = {}, {"edit": 0.0, "verify": 0.0}
    edit = insta.edit_items
    for f in sorted((FIX / "ai-news").glob("*.json")):
        _, data, items = insta.load_items(f)
        meter, spent = Meter(), {}

        def timed_edit(*a, **k):  # 편집 단계 비용만 따로 잰다
            out = edit(*a, **k)
            spent["edit"] = meter.cost
            return out

        insta.edit_items = timed_edit
        try:
            with tempfile.TemporaryDirectory() as d:
                _, passed, report = insta.edit_and_verify(data, items, meter, d)
        finally:
            insta.edit_items = edit
        results[f.stem] = {r["title"]: ("통과" if r["ok"] else "탈락: " + "; ".join(r["problems"])[:160])
                           for r in report}
        total["edit"] += spent.get("edit", 0)
        total["verify"] += meter.cost - spent.get("edit", 0)
        print(f"{f.stem}: 통과 {len(passed)} / 검사 {len(report)}  (${meter.cost:.3f})")
    print(f"합계 편집 ${total['edit']:.3f}, 검증 ${total['verify']:.3f}")
    return results


def diff(old, new):
    changed = 0
    for day in sorted(set(old) | set(new)):
        for title in sorted(set(old.get(day, {})) | set(new.get(day, {}))):
            a, b = old.get(day, {}).get(title, "(없음)"), new.get(day, {}).get(title, "(없음)")
            if a.split(":")[0] != b.split(":")[0]:
                changed += 1
                print(f"  [{day}] {title}\n     기준: {a}\n     지금: {b}")
    print(f"통과/탈락이 달라진 항목 {changed}개" if changed else "기준과 통과/탈락이 같습니다")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--save", action="store_true")
    a = ap.parse_args()
    new = run_all()
    if a.save or not BASELINE.exists():
        BASELINE.write_text(json.dumps(new, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"기준 저장: {BASELINE}")
    else:
        diff(json.loads(BASELINE.read_text(encoding="utf-8")), new)
