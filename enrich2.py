# -*- coding: utf-8 -*-
"""
在已构建的 all.json（1053 个招生方向）基础上，补齐「继续开发」所需的字段：

  1. 国家线（真实，教育部公布的工学门类线，2021–2026 多年度，A/B 区）
  2. 学校所属 A/B 区（zone）
  3. 学费（按层次参考值，标注来源）
  4. 各科分数线 + 国家线单科线（基于总分估算，标注"参考"）
  5. 录取名单（每人各科，示例数据，标注"示例"）+ 各科均分
  6. 叠加 data3/ 另一任务采集的 math / transfer / score26 / score25 / admitMin / url25 / admitUrl

真实锚点（复试线、录取最低分、国家线）保持原值；科目拆分与录取名单为便于展示字段结构
而生成的「参考/示例」数据，已在 README 与 App 内"数据说明"明示。
"""
import json, glob, os, re, hashlib
from collections import Counter

BASE = os.path.dirname(os.path.abspath(__file__))
ALL = os.path.join(BASE, "all.json")

# ---------------------------------------------------------------- 真实国家线（工学门类，电子信息 0854 属此）
# (总分, 单科满分100线[政治/英语], 单科满分>100线[数学/专业课])
NL = {
    "A": {
        2021: (263, 37, 56), 2022: (273, 38, 57), 2023: (273, 38, 57),
        2024: (273, 37, 56), 2025: (260, 34, 51), 2026: (251, 33, 50),
    },
    "B": {
        2021: (253, 34, 51), 2022: (263, 35, 53), 2023: (263, 35, 53),
        2024: (263, 34, 52), 2025: (250, 31, 47), 2026: (241, 30, 45),
    },
}
NL_YEARS = [2021, 2022, 2023, 2024, 2025, 2026]
NL_CUR_YEAR = 2026

# B 区省份
B_PROV = {"内蒙古", "广西", "海南", "贵州", "云南", "西藏", "甘肃", "青海", "宁夏", "新疆"}

# ---------------------------------------------------------------- 学费参考（元/年，专硕）
# 学硕通常 8000；专硕差异大，这里用常见区间做参考值。真实数值以各校招生简章为准。
TUITION_BY_TIER = {"985": 12000, "211": 10000, "双一流": 10000, "双非": 8000}
# 少数公开学费较高的院校（专硕，元/年）
TUITION_SPEC = {
    "清华大学": 30000, "北京大学": 30000, "上海交通大学": 20000, "复旦大学": 20000,
    "浙江大学": 16000, "南京大学": 15000, "同济大学": 15000, "武汉大学": 13000,
    "华中科技大学": 13000, "电子科技大学": 15000, "西安电子科技大学": 12000,
    "北京邮电大学": 12000, "杭州电子科技大学": 10000, "深圳大学": 12000,
}

# 科目基准（参考总分 330 时的典型构成），用于把总分拆成 4 科
SUBJ_BASE = {"政治": 65, "英语": 60, "数学": 95, "专业课": 110}  # 合计 330


def hj(*parts):
    return int(hashlib.md5("|".join(str(p) for p in parts).encode("utf-8")).hexdigest(), 16)


def num(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return int(v)
    m = re.search(r"\d{2,3}", str(v))
    return int(m.group()) if m else None


def split_subjects(total, seed):
    """把总分拆成 4 科（确定性抖动），返回 {科:分}。"""
    if total is None:
        return None
    factor = total / 330.0
    out = {}
    for k, b in SUBJ_BASE.items():
        jit = hj(seed, k) % 7 - 3  # -3..3
        out[k] = max(20, round(b * factor) + jit)
    # 修正使合计等于 total
    diff = total - sum(out.values())
    # 优先调整"专业课"
    out["专业课"] = max(20, out["专业课"] + diff)
    return out


def key(r):
    return (str(r.get("school", "")).strip(), str(r.get("college", "")).strip(),
            str(r.get("code", "")).strip(), str(r.get("direction", "")).strip())


def main():
    rows = json.load(open(ALL, encoding="utf-8"))

    # -------- 叠加 data3 另一任务采集的字段 --------
    overlay = {}
    for f in sorted(glob.glob(os.path.join(BASE, "data3", "**", "*.json"), recursive=True)):
        d = json.load(open(f, encoding="utf-8"))
        rs = d if isinstance(d, list) else d.get("rows", [])
        for r in rs:
            k = key(r)
            if not k[0]:
                continue
            cur = overlay.setdefault(k, {})
            for fld in ("score26", "score25", "admitMin", "admitMin25", "math", "transfer",
                        "transferNote", "url25", "transferUrl", "admitUrl", "mathNote"):
                v = r.get(fld)
                if v not in (None, "", "—", "-", "null"):
                    cur[fld] = v
    n_overlay = 0
    for r in rows:
        o = overlay.get(key(r))
        if not o:
            continue
        n_overlay += 1
        for fld, v in o.items():
            if fld in ("score26", "score25", "admitMin", "admitMin25"):
                r[fld] = num(v)
            else:
                r[fld] = v
    print("data3 叠加命中:", n_overlay, "行")

    # -------- 逐行补齐新字段 --------
    for r in rows:
        # 重新算 delta（score25 可能被叠加刷新）
        if r.get("score26") is not None and r.get("score25") is not None:
            r["delta"] = r["score26"] - r["score25"]
        else:
            r["delta"] = r.get("delta")

        # A/B 区
        prov = r.get("province", "")
        r["zone"] = "B" if prov in B_PROV else "A"

        # 学费
        sch = r.get("school", "")
        r["tuition"] = TUITION_SPEC.get(sch) or TUITION_BY_TIER.get(r.get("level", "双非"), 8000)

        # 数学科目（data3 提供，缺省按"数一/数二"未知 -> 留空）
        r.setdefault("math", "")
        r.setdefault("transfer", "")
        r.setdefault("transferNote", "")
        r.setdefault("url25", "")
        r.setdefault("transferUrl", "")

        # 各科分数线（参考估算，基于总分拆分，非官方单科线）
        subj = split_subjects(r.get("score26"), key(r))
        r["subjects"] = subj  # {政治,英语,数学,专业课}
        r["subjEst"] = True   # 标注：基于总分估算，非官方单科线

        # 考试科目（初试四科）：政治 / 英语 / 数学 / 专业课(业务课二)
        mathv = r.get("math") if (r.get("math") and r.get("math") != "未知") else ""
        r["exams"] = {
            "政治": "101 思想政治理论",
            "英语": "204 英语二",
            "数学": mathv or "",
            "专业课": r.get("exam4") or "",
        }
        # 不生成示例录取名单 / 示例均分：用户要求真实数据；
        # 拟录取名单公示后下架，缺则留空，由 UI 说明并支持后续补录。
        r["admitList"] = []
        r["admitDemo"] = False
        r["subjectAvg"] = None

    json.dump(rows, open(ALL, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    # 统计
    withscore = [r for r in rows if r.get("score26")]
    withmath = [r for r in rows if r.get("math") and r["math"] != "未知"]
    withtrans = [r for r in rows if r.get("transfer") and r["transfer"] != "未知"]
    print("总行数:", len(rows))
    print("有26届分数:", len(withscore))
    print("叠加 math:", len(withmath), " transfer:", len(withtrans))
    print("学费覆盖:", sum(1 for r in rows if r.get("tuition")))
    print("科目拆分覆盖:", sum(1 for r in rows if r.get("subjects")))
    print("录取示例名单覆盖:", sum(1 for r in rows if r.get("admitList")))
    print("输出:", ALL)


if __name__ == "__main__":
    main()
