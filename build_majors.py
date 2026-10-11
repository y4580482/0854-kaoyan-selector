# -*- coding: utf-8 -*-
"""
解析 majors_raw/*.txt 里的「全校分专业报录比」表 -> majors.json

一个文件 = 一所学校的一个年份，文件名建议 <学校>__<年份>.txt；
文件头用 # 注释写元信息（文件名里的年份只是习惯，真正生效的是 # year:）：
    # school: 南京邮电大学
    # year: 2026
    # source: https://yzb.njupt.edu.cn/...
    <正文：一行一个专业 —— 专业代码+名称 学位类型 学习方式 报考 录取 [报录比]>
    学院行单独一行：<学院代码><学院名称>

产出 majors.json（多年份）：
    { 学校名: { years: { "2026": {source, rows:[{college,ccode,code,name,degree,apply,admit,ratio}]},
                         "2025": {...}, "2024": {...} } } }
"""
import os, re, json, glob

BASE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(BASE, "majors_raw")

TOK = re.compile(
    r'(?P<ccode>\d{2,3})(?P<cname>[\u4e00-\u9fa5A-Za-z（）()·\-、，。；：～]{2,24}?'
    r'(?:学院|研究院|研究所|实验室|中心|学部|专项|基地))'
    r'|(?P<mcode>\d{4}[A-Z]?\d{0,2})(?P<mname>[\u4e00-\u9fa5A-Za-z（）()·\-、，。；：～]+?)[ \t]+'
    r'(?P<deg>学术学位|专业学位|学术型|专业型)[ \t]+(?P<mode>全日制|非全日制)[ \t]+'
    r'(?P<ap>\d+)[ \t]+(?P<ad>\d+)(?:[ \t]+(?P<ra>\d{1,3}(?:\.\d{1,2})?)(?=[ \t\n]|\Z))?'
)

def parse_file(path):
    txt = open(path, encoding="utf-8").read()
    school = year = source = None
    for line in txt.splitlines():
        if line.startswith("#"):
            m = re.match(r"#\s*(school|year|source)\s*[:：]\s*(.+)", line)
            if m:
                if m.group(1) == "school": school = m.group(2).strip()
                if m.group(1) == "year":   year = m.group(2).strip()
                if m.group(1) == "source": source = m.group(2).strip()
    if not school:
        school = os.path.splitext(os.path.basename(path))[0].split("__")[0]
    if not year:                                   # 兜底：从文件名 <学校>__<年>.txt 取
        base = os.path.splitext(os.path.basename(path))[0]
        mm = re.search(r"(\d{4})$", base)
        year = mm.group(1) if mm else "未知"

    rows, cur = [], None
    for m in TOK.finditer(txt):
        if m.group("ccode"):
            cur = {"ccode": m.group("ccode"), "college": m.group("cname")}
            continue
        if m.group("mcode"):
            ap = int(m.group("ap")); ad = int(m.group("ad"))
            ra = m.group("ra")
            ratio = float(ra) if ra else (round(ap / ad, 2) if ad else None)
            rows.append({
                "college": (cur or {}).get("college", ""),
                "ccode": (cur or {}).get("ccode", ""),
                "code": m.group("mcode"),
                "name": m.group("mname"),
                "degree": "学硕" if m.group("deg") in ("学术学位", "学术型") else "专硕",
                "apply": ap, "admit": ad, "ratio": ratio,
            })
    return school, year, source, rows


out = {}
for path in sorted(glob.glob(os.path.join(RAW, "*.txt"))):
    school, year, source, rows = parse_file(path)
    if not rows:
        print(f"⚠ 跳过（0 行）: {os.path.basename(path)}")
        continue
    out.setdefault(school, {"years": {}})
    out[school]["years"][year] = {"source": source, "rows": rows}
    print(f"{school} {year}: {len(rows)} 行")

# 年份按新→旧排序，方便前端直接取 [0] 作为默认年份
for school, v in out.items():
    v["years"] = dict(sorted(v["years"].items(), key=lambda kv: kv[0], reverse=True))
    print(f"  {school}: {list(v['years'])}")

json.dump(out, open(os.path.join(BASE, "majors.json"), "w", encoding="utf-8"),
          ensure_ascii=False, separators=(",", ":"))
print("生成 majors.json：", len(out), "所学校，",
      sum(len(v["years"]) for v in out.values()), "个学校-年份")
