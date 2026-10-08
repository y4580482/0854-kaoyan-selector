# -*- coding: utf-8 -*-
"""
合并 8 个分组采集的 0854 电子信息考研数据 -> 清洗 -> 输出 all.json
"""
import json, glob, os, re

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")

FIELDS = ["school", "level", "province", "city", "college", "code",
          "direction", "score26", "score25", "plan26", "exam4", "source", "url", "note"]

# source 可信度权重，越大越可靠
SRC_RANK = {
    "官网": 5, "官网复试方案": 5, "院系官网": 4,
    "媒体整理": 2, "估算": 1, "未查到": 0,
}


def norm(v):
    if v is None:
        return ""
    return str(v).strip()


def load_all():
    rows = []
    for f in sorted(glob.glob(os.path.join(DATA, "*.json"))):
        d = json.load(open(f, encoding="utf-8"))
        rs = d if isinstance(d, list) else d.get("rows", [])
        for r in rs:
            o = {k: norm(r.get(k, "")) for k in FIELDS}
            rows.append(o)
    return rows


def clean(rows):
    out = []
    for r in rows:
        if not r["school"]:
            continue
        # 剔除明确无 0854 招生点的占位行
        if "无0854招生" in r["note"] or "无0854招生" in r["college"]:
            continue
        # 城市去"市"字
        r["city"] = re.sub(r"市$", "", r["city"]) or r["city"]
        # 分数转 int
        for k in ("score26", "score25"):
            v = r[k]
            m = re.search(r"\d{3}", v) if v else None
            r[k] = int(m.group()) if m else None
        # plan
        if not r["plan26"] or r["plan26"] in ("—", "-", "无", "null"):
            r["plan26"] = ""
        # 专业课空值归一
        if r["exam4"] in ("—", "-", "无", "null", "未公布", "不详"):
            r["exam4"] = ""
        # note 去 null
        if r["note"].lower() in ("null", "none"):
            r["note"] = ""
        # direction 去 null
        if r["direction"].lower() in ("null", "none", "—", "-"):
            r["direction"] = "不区分方向"
        # college 去 null
        if r["college"].lower() in ("null", "none"):
            r["college"] = "—"
        # code 规范化
        m = re.search(r"0854\d\d", r["code"])
        r["code"] = m.group() if m else "085400"
        # level 归一
        lv = r["level"]
        if "985" in lv:
            r["level"] = "985"
        elif "211" in lv:
            r["level"] = "211"
        elif "双一流" in lv:
            r["level"] = "双一流"
        else:
            r["level"] = "双非"
        out.append(r)
    return out


def dedup(rows):
    """按 school+college+code+direction 去重，优先保留有分数、source 可靠的"""
    buckets = {}
    for r in rows:
        key = (r["school"], r["college"], r["code"], r["direction"])
        score = (1 if r["score26"] else 0, SRC_RANK.get(r["source"], 0),
                 len(r["url"]), len(r["note"]))
        if key not in buckets or score > buckets[key][0]:
            buckets[key] = (score, r)
    return [v[1] for v in buckets.values()]


# 0854 细分方向中文名
DIR_MAP = {
    "085400": "电子信息(大类)",
    "085401": "新一代电子信息技术",
    "085402": "通信工程",
    "085403": "集成电路工程",
    "085404": "计算机技术",
    "085405": "软件工程",
    "085406": "控制工程",
    "085407": "仪器仪表工程",
    "085408": "光电信息工程",
    "085409": "生物医学工程",
    "085410": "人工智能",
    "085411": "大数据技术与工程",
    "085412": "网络与信息安全",
}

REGION = {
    "北京": "华北", "天津": "华北", "河北": "华北", "山西": "华北", "内蒙古": "华北",
    "辽宁": "东北", "吉林": "东北", "黑龙江": "东北",
    "上海": "华东", "江苏": "华东", "浙江": "华东", "安徽": "华东",
    "福建": "华东", "江西": "华东", "山东": "华东",
    "河南": "华中", "湖北": "华中", "湖南": "华中",
    "广东": "华南", "广西": "华南", "海南": "华南",
    "重庆": "西南", "四川": "西南", "贵州": "西南", "云南": "西南", "西藏": "西南",
    "陕西": "西北", "甘肃": "西北", "青海": "西北", "宁夏": "西北", "新疆": "西北",
}


def enrich(rows):
    for r in rows:
        r["dirName"] = DIR_MAP.get(r["code"], "电子信息")
        r["region"] = REGION.get(r["province"], "其他")
        if r["score26"] and r["score25"]:
            r["delta"] = r["score26"] - r["score25"]
        else:
            r["delta"] = None
        s = r["score26"]
        if not s:
            r["tier"] = "未知"
        elif s >= 380:
            r["tier"] = "极难"
        elif s >= 360:
            r["tier"] = "很难"
        elif s >= 340:
            r["tier"] = "较难"
        elif s >= 320:
            r["tier"] = "中等"
        elif s >= 300:
            r["tier"] = "一般"
        else:
            r["tier"] = "较易"
    return rows


def main():
    raw = load_all()
    print("原始行数:", len(raw))
    c = clean(raw)
    print("清洗后:", len(c))
    d = dedup(c)
    print("去重后:", len(d))
    d = enrich(d)
    d.sort(key=lambda r: (-(r["score26"] or 0), r["level"], r["school"], r["college"]))
    out = os.path.join(BASE, "all.json")
    json.dump(d, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    # 统计
    withscore = [r for r in d if r["score26"]]
    print("有26届分数:", len(withscore))
    print("学校数:", len({r["school"] for r in d}))
    from collections import Counter
    print("层次分布:", Counter(r["level"] for r in d))
    print("数据来源:", Counter(r["source"] for r in d))
    print("难度分布:", Counter(r["tier"] for r in d))
    print("输出:", out)


if __name__ == "__main__":
    main()
