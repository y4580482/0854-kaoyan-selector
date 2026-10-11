# -*- coding: utf-8 -*-
"""把 all.json 注入 template.html，生成单文件 index.html。

大数据（研招网专业目录 catalog.json + 掌上考研明细 kao.json）合并后
gzip + base64 内联为 __BLOB__，由页面启动时用 DecompressionStream 解压，
从而在单文件体积可控的前提下装下全部明细。
"""
import json, os, gzip, base64

BASE = os.path.dirname(os.path.abspath(__file__))

rows = json.load(open(os.path.join(BASE, "all.json"), encoding="utf-8"))
tpl = open(os.path.join(BASE, "template.html"), encoding="utf-8").read()

# 紧凑 JSON，并阻断 </script> 注入
js = json.dumps(rows, ensure_ascii=False, separators=(",", ":"))
js = js.replace("</", "<\\/")

# 全校分专业报录比（可选）
mp = os.path.join(BASE, "majors.json")
majors = json.load(open(mp, encoding="utf-8")) if os.path.exists(mp) else {}
mjs = json.dumps(majors, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")

# 全量硕士专业目录（研招网 919 校 ∪ 掌上考研 930 校 -> 1047 校）
# 优先用 merge_catalog.py 产出的并集 catalog_merged.json，没有才回落到 catalog.json
cp = os.path.join(BASE, "catalog_merged.json")
if not os.path.exists(cp):
    cp = os.path.join(BASE, "catalog.json")
catalog = json.load(open(cp, encoding="utf-8")) if os.path.exists(cp) else {}

# 掌上考研明细：复试线 / 逐年招生 / 考试科目 / 参考书（可选）
kp = os.path.join(BASE, "kao.json")
kao = json.load(open(kp, encoding="utf-8")) if os.path.exists(kp) else {}

# 合并 -> gzip -> base64
raw = json.dumps({"cat": catalog, "kao": kao}, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
gz = gzip.compress(raw, 9)
bjs = json.dumps(base64.b64encode(gz).decode("ascii"))

out = tpl.replace("__DATA__", js).replace("__MAJORS__", mjs).replace("__BLOB__", bjs)
p = os.path.join(BASE, "index.html")
open(p, "w", encoding="utf-8").write(out)

tot = sum(len(v) for v in (catalog.get("schools") or {}).values())
krows = sum(len(v) for v in (kao.get("schools") or {}).values())
print("生成:", p, os.path.getsize(p) // 1024, "KB")
print("  %d 行方向 / %d 校报录比" % (len(rows), len(majors)))
print("  专业目录(%s): %d 校 / %d 条" % (os.path.basename(cp), len(catalog.get("schools") or {}), tot))
print("  掌上考研  : %d 校 / %d 条 (含复试线 %d)" % (
    len(kao.get("schools") or {}), krows,
    sum(1 for v in (kao.get("schools") or {}).values() for r in v if r[4] > 0)))
print("  内联数据  : 原始 %.2f MB -> gzip %.2f MB -> base64 %.2f MB" % (
    len(raw) / 1048576, len(gz) / 1048576, len(bjs) / 1048576))
