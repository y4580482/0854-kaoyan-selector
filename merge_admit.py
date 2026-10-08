# -*- coding: utf-8 -*-
"""
把 data2/*.json 里采集到的「录取最低分」合并进 all.json
匹配主键：school + college + code + direction
"""
import json, glob, os, re

BASE = os.path.dirname(os.path.abspath(__file__))
ALL = os.path.join(BASE, "all.json")


def num(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return int(v)
    m = re.search(r"\d{3}", str(v))
    return int(m.group()) if m else None


def key(r):
    return (str(r.get("school", "")).strip(), str(r.get("college", "")).strip(),
            str(r.get("code", "")).strip(), str(r.get("direction", "")).strip())


def main():
    rows = json.load(open(ALL, encoding="utf-8"))
    idx = {}
    for i, r in enumerate(rows):
        idx.setdefault(key(r), []).append(i)

    hit = miss = filled = 0
    for f in sorted(glob.glob(os.path.join(BASE, "data2", "*.json"))):
        name = os.path.basename(f)
        if name.startswith("_") or name == "worklist.json":
            continue
        d = json.load(open(f, encoding="utf-8"))
        rs = d if isinstance(d, list) else d.get("rows", [])
        for r in rs:
            k = key(r)
            am = num(r.get("admitMin"))
            if am is None:
                continue
            if k not in idx:
                miss += 1
                continue
            hit += 1
            for i in idx[k]:
                t = rows[i]
                t["admitMin"] = am
                av = num(r.get("admitAvg"))
                t["admitAvg"] = av
                ac = r.get("admitCount")
                if ac and str(ac) not in ("—", "-", "无"):
                    t["admitCount"] = str(ac)
                if r.get("srcUrl"):
                    t["admitUrl"] = str(r["srcUrl"])
                if r.get("note"):
                    old = t.get("note", "")
                    t["note"] = (old + "；" if old else "") + "录取数据：" + str(r["note"])
                filled += 1

    json.dump(rows, open(ALL, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    n = sum(1 for r in rows if r.get("admitMin"))
    print(f"匹配命中 {hit} 条 / 未匹配 {miss} 条 -> 已写入 {filled} 行")
    print(f"all.json 现有录取最低分：{n} / {len(rows)} 行")

    from collections import Counter
    c = Counter(r["school"] for r in rows if r.get("admitMin"))
    print("覆盖学校:", dict(c))


if __name__ == "__main__":
    main()
