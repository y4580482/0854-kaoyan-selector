# -*- coding: utf-8 -*-
"""
数据更新工具 —— 用 Excel 编辑 all.csv，再一键回写生成新页面

用法：
    python update.py export    # all.json  ->  all.csv（用 Excel 打开编辑）
    python update.py import    # all.csv   ->  all.json + 重新生成 index.html
    python update.py check     # 校验 all.csv 有没有填错（分数越界、学校名空白等）
"""
import json, csv, os, sys, re

BASE = os.path.dirname(os.path.abspath(__file__))
JSON_P = os.path.join(BASE, "all.json")
CSV_P = os.path.join(BASE, "all.csv")
TPL_P = os.path.join(BASE, "template.html")
HTML_P = os.path.join(BASE, "index.html")

# CSV 列顺序：前 8 列是"身份列"（尽量不要改），后面是可维护的数据列
COLS = ["school", "level", "province", "city", "college", "code", "direction",
        "score26", "score25", "plan26", "exam4", "source", "url", "note",
        "region", "dirName", "delta", "tier"]   # 后 4 列只读，自动生成

DIR_MAP = {
    "085400": "电子信息(大类)", "085401": "新一代电子信息技术", "085402": "通信工程",
    "085403": "集成电路工程", "085404": "计算机技术", "085405": "软件工程",
    "085406": "控制工程", "085407": "仪器仪表工程", "085408": "光电信息工程",
    "085409": "生物医学工程", "085410": "人工智能", "085411": "大数据技术与工程",
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


def num(v):
    """从任意字符串里取出第一个 3 位分数"""
    if v is None:
        return None
    m = re.search(r"\d{3}", str(v))
    return int(m.group()) if m else None


def enrich(r):
    r["score26"] = num(r.get("score26"))
    r["score25"] = num(r.get("score25"))
    r["delta"] = (r["score26"] - r["score25"]) if (r["score26"] and r["score25"]) else None
    r["dirName"] = DIR_MAP.get(r.get("code", ""), "电子信息")
    r["region"] = REGION.get(r.get("province", ""), "其他")
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
    return r


def do_export():
    rows = json.load(open(JSON_P, encoding="utf-8"))
    with open(CSV_P, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=COLS, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            row = {k: ("" if r.get(k) is None else r.get(k)) for k in COLS}
            w.writerow(row)
    print(f"✅ 已导出 {len(rows)} 行 -> all.csv")
    print("   用 Excel / WPS 打开编辑，改完保存后运行：python update.py import")


def do_check():
    if not os.path.exists(CSV_P):
        print("❌ 没有 all.csv，先运行 python update.py export")
        return
    rows = list(csv.DictReader(open(CSV_P, encoding="utf-8-sig")))
    err = []
    for i, r in enumerate(rows, start=2):   # 表头占第 1 行
        if not r.get("school", "").strip():
            err.append(f"第{i}行：学校名为空")
        for k in ("score26", "score25"):
            v = (r.get(k) or "").strip()
            if v:
                n = num(v)
                if n is None:
                    err.append(f"第{i}行：{k} 不是数字 -> {v}")
                elif not (200 <= n <= 500):
                    err.append(f"第{i}行：{k}={n} 超出合理范围(200~500)")
        code = (r.get("code") or "").strip()
        if code and not re.fullmatch(r"0854\d\d", code):
            err.append(f"第{i}行：专业代码格式不对 -> {code}")
        if (r.get("level") or "").strip() not in ("985", "211", "双一流", "双非"):
            err.append(f"第{i}行：层次必须是 985/211/双一流/双非 -> {r.get('level')}")
    print(f"检查 {len(rows)} 行，", end="")
    if err:
        print(f"发现 {len(err)} 个问题：")
        for e in err[:30]:
            print("  ⚠️", e)
        if len(err) > 30:
            print(f"  ...还有 {len(err)-30} 条")
    else:
        print("✅ 全部正常，可以 import")


def do_import():
    if not os.path.exists(CSV_P):
        print("❌ 没有 all.csv，先运行 python update.py export")
        return
    rows = list(csv.DictReader(open(CSV_P, encoding="utf-8-sig")))
    out = []
    for r in rows:
        if not (r.get("school") or "").strip():
            continue                      # 空行跳过
        o = {k: (r.get(k) or "").strip() for k in COLS}
        # 空值归一
        for k in ("plan26", "exam4", "note", "url"):
            if o[k] in ("—", "-", "无", "null"):
                o[k] = ""
        if o["level"] not in ("985", "211", "双一流", "双非"):
            o["level"] = "双非"
        if not re.fullmatch(r"0854\d\d", o["code"] or ""):
            o["code"] = "085400"
        out.append(enrich(o))
    out.sort(key=lambda r: (-(r["score26"] or 0), r["level"], r["school"], r["college"]))
    json.dump(out, open(JSON_P, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"✅ all.json 已更新：{len(out)} 行（有分数线 {sum(1 for r in out if r['score26'])} 行）")

    # 顺手重新生成页面
    js = json.dumps(out, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    tpl = open(TPL_P, encoding="utf-8").read()
    open(HTML_P, "w", encoding="utf-8").write(tpl.replace("__DATA__", js))
    print(f"✅ index.html 已重新生成：{os.path.getsize(HTML_P)//1024} KB")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "export":
        do_export()
    elif cmd == "import":
        do_import()
    elif cmd == "check":
        do_check()
    else:
        print(__doc__)
