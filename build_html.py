# -*- coding: utf-8 -*-
"""把 all.json 注入 template.html，生成单文件 index.html"""
import json, os, html

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

out = tpl.replace("__DATA__", js).replace("__MAJORS__", mjs)
p = os.path.join(BASE, "index.html")
open(p, "w", encoding="utf-8").write(out)
print("生成:", p, os.path.getsize(p) // 1024, "KB /", len(rows), "行 /", len(majors), "所校报录比")
