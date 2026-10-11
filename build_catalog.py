# -*- coding: utf-8 -*-
"""把研招网全量硕士专业目录 CSV（_data/majors_yzw.csv）聚合成 App 用的 catalog.json。

原始 CSV 获取（研招网 2026 届全量目录，经 freecho/yzw 汇总，约 33MB）：
  curl -L --ssl-no-revoke -H "Accept: application/octet-stream" -o _data/majors_yzw.csv \\
    https://api.github.com/repos/freecho/yzw/releases/assets/273381659
（_data/ 不入库；catalog.json 由本脚本生成并随仓库提交）
层级：学校 × 专业代码（合并院系/学习模式/招生人数/考试科目）。
输出字典压缩结构（尽量小，供 build_html.py 注入模板 __CATALOG__）：
{
  "src": 来源说明,
  "year": "2026",
  "provs": [省份...],
  "degs":  ["学硕","专硕"],
  "modes": ["全日制","非全日制"],
  "codes": {专业代码: 专业名称, ...},
  "exams": [考试科目串, ...],
  "schools": { 校名: [ [代码, 省idx, 学位idx, 学习模式idx串, 院系, 招生人数(int), 考试idx], ... ] }
}
"""
import csv, json, collections, os, re

BASE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(BASE, "_data", "majors_yzw.csv")
OUT = os.path.join(BASE, "catalog.json")

DEG = {"学术学位": "学硕", "专业学位": "专硕"}
MODES = ["全日制", "非全日制"]


def first_int(s):
    m = re.search(r"\d+", s or "")
    return int(m.group(0)) if m else -1


def build_groups():
    r = csv.reader(open(SRC, encoding="utf-8-sig", newline=""))
    hdr = next(r)
    I = {h: i for i, h in enumerate(hdr)}
    G = collections.defaultdict(lambda: {
        "name": "", "prov": "", "deg": "", "colleges": [], "modes": [],
        "plan": "", "exams": collections.Counter()})
    n = 0
    for row in r:
        if len(row) < len(hdr):
            continue
        s = row[I["学校名称"]].strip()
        c = row[I["专业代码"]].strip()
        if not s or not c:
            continue
        n += 1
        g = G[(s, c)]
        if not g["name"]:
            g["name"] = row[I["专业名称"]].strip()
            g["prov"] = row[I["省份"]].strip()
            g["deg"] = DEG.get(row[I["学位类型"]].strip(), row[I["学位类型"]].strip())
        col = row[I["院系"]].strip()
        if col and col not in g["colleges"]:
            g["colleges"].append(col)
        m = row[I["学习模式"]].strip()
        if m and m not in g["modes"]:
            g["modes"].append(m)
        pl = row[I["拟招生人数"]].strip()
        if pl and not g["plan"]:
            g["plan"] = pl
        ex = " | ".join(v for v in (row[I["考试科目1"]].strip(), row[I["考试科目2"]].strip(),
                                    row[I["考试科目3"]].strip(), row[I["考试科目4"]].strip()) if v)
        if ex:
            g["exams"][ex] += 1
    return n, G


def main():
    n, G = build_groups()
    provs = sorted({g["prov"] for g in G.values() if g["prov"]})
    pidx = {p: i for i, p in enumerate(provs)}
    didx = {"学硕": 0, "专硕": 1}
    midx = {m: i for i, m in enumerate(MODES)}
    codes = {}
    for (_, c), g in G.items():
        if g["name"]:
            codes[c] = g["name"]
    exset = {}
    for g in G.values():
        for ex in g["exams"]:
            exset.setdefault(ex, len(exset))
    exams = [""] * len(exset)
    for ex, i in exset.items():
        exams[i] = ex
    byschool = collections.defaultdict(list)
    for (s, c), g in G.items():
        college = " / ".join(g["colleges"])[:48]
        mode = "".join(str(midx.get(m, 0)) for m in g["modes"]) or "0"
        ex = g["exams"].most_common(1)[0][0] if g["exams"] else ""
        byschool[s].append([c, pidx.get(g["prov"], -1), didx.get(g["deg"], -1),
                            mode, college, first_int(g["plan"]), exset.get(ex, -1)])
    schoolsdata = {s: sorted(v, key=lambda x: x[0]) for s, v in sorted(byschool.items())}
    out = {
        "src": "研招网硕士专业目录(2026届)，经 freecho/yzw 汇总",
        "year": "2026",
        "provs": provs, "degs": ["学硕", "专硕"], "modes": MODES,
        "codes": codes, "exams": exams, "schools": schoolsdata,
    }
    js = json.dumps(out, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    open(OUT, "w", encoding="utf-8").write(js)
    size = os.path.getsize(OUT)
    print(f"原始行 {n} | 学校 {len(schoolsdata)} | 专业代码 {len(codes)} | (学校,专业) {len(G)}")
    print(f"省份 {len(provs)} | 唯一考试串 {len(exams)}")
    print(f"catalog.json: {size//1024} KB ({size/1024/1024:.2f} MB)")


if __name__ == "__main__":
    main()
