# -*- coding: utf-8 -*-
"""把「研招网专业目录(catalog.json)」与「掌上考研(kao.json)」并集，生成 catalog_merged.json。

为什么要并集：
  两个数据源各有缺失，且**学校名写法不一致**（全角/半角括号，如
  `中国地质大学（武汉）` vs `中国地质大学(武汉)`），直接按名字取会以为"查不到"。
  实测：掌上考研独有的 139 所里有 69 所只是写法不同；归一化后仍有 5,101 条
  「学校×专业」只在掌上考研、4,547 条只在研招网（多为兵器/航天院所）。

规则：
  - 学校名先归一化（全角括号→半角、去空白）再配对；配对成功沿用**研招网的名字**，
    否则新增一所学校（用掌上考研的名字 + 掌上考研给的省份）。
  - 同一 (学校, 专业代码) 已存在则不重复添加；研招网的行保留原状。
  - 新增行按 catalog 的行格式合成：[代码, 省idx, 学位idx, 学习方式串, 院系, 招生人数, 考试idx(-1)]。
    （考试科目/复试线/参考书 由掌上考研明细在详情浮层里给出，不再重复存进 exams 池。）
"""
import json, os, re

BASE = os.path.dirname(os.path.abspath(__file__))
CATP = os.path.join(BASE, "catalog.json")
KAOP = os.path.join(BASE, "kao.json")
OUTP = os.path.join(BASE, "catalog_merged.json")


def norm_school(s):
    s = str(s or "")
    s = s.replace("（", "(").replace("）", ")")
    s = re.sub(r"[\s\u3000]+", "", s)
    s = s.replace("·", "").replace("\u00b7", "")
    return s


def main():
    cat = json.load(open(CATP, encoding="utf-8"))
    kao = json.load(open(KAOP, encoding="utf-8"))

    provs = list(cat.get("provs") or [])
    pidx = {p: i for i, p in enumerate(provs)}
    codes = dict(cat.get("codes") or {})
    exams = list(cat.get("exams") or [])
    schools = cat.get("schools") or {}     # 直接引用并原地 append（省内存），故先记下原始校数
    cat_sch_cnt = len(schools)

    # 研招网学校名 -> 归一化键
    by_norm = {}
    for nm in schools:
        by_norm.setdefault(norm_school(nm), nm)

    def prov_idx(p):
        p = (p or "").strip()
        if not p:
            return -1
        if p not in pidx:
            pidx[p] = len(provs)
            provs.append(p)
        return pidx[p]

    kao_codes = kao.get("codes") or {}
    kao_prov = kao.get("prov") or {}
    added_rows = 0
    new_schools = 0
    merged_into = 0

    for ks, krows in (kao.get("schools") or {}).items():
        key = norm_school(ks)
        target = by_norm.get(key)
        if target is None:
            target = ks
            by_norm[key] = ks
            schools.setdefault(ks, [])
            new_schools += 1
        else:
            if target != ks:
                merged_into += 1
        rows = schools.setdefault(target, [])
        have = {r[0] for r in rows}
        pi = prov_idx(kao_prov.get(ks))
        for r in krows:
            code = r[0]
            if code in have:
                continue
            have.add(code)
            deg_i = r[1] if r[1] in (0, 1) else -1
            mode_s = str(r[2]) if r[2] in (0, 1) else "0"
            plan = r[8][0][1] if r[8] else -1
            rows.append([code, pi, deg_i, mode_s, r[3], plan, -1])
            added_rows += 1
            if code not in codes:
                codes[code] = kao_codes.get(code) or ""

    for nm in schools:
        schools[nm].sort(key=lambda x: (str(x[0]), str(x[4])))

    out = {
        "src": "研招网硕士专业目录(2026届) ＋ 掌上考研(2027届) 并集",
        "year": cat.get("year") or "2026",
        "provs": provs,
        "degs": cat.get("degs") or ["学硕", "专硕"],
        "modes": cat.get("modes") or ["全日制", "非全日制"],
        "codes": codes,
        "exams": exams,
        "schools": schools,
    }
    js = json.dumps(out, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    open(OUTP, "w", encoding="utf-8").write(js)

    tot = sum(len(v) for v in schools.values())
    print("合并完成:")
    print("  学校 %d 所（研招网 %d + 掌上考研新增 %d；按名字归一化合并了 %d 所）"
          % (len(schools), cat_sch_cnt, new_schools, merged_into))
    print("  行(学校×专业) %d 条（新增 %d 条来自掌上考研独有专业）" % (tot, added_rows))
    print("  专业代码 %d 个 | 省份 %d 个" % (len(codes), len(provs)))
    print("  catalog_merged.json: %.2f MB" % (os.path.getsize(OUTP) / 1048576))


if __name__ == "__main__":
    main()
