# -*- coding: utf-8 -*-
"""把 fetch_kaoyan.py 采集的 details.jsonl 聚合成 App 用的 kao.json。

产物（压缩结构，供 build_html.py 注入模板 __KAO__）：
{
  "src": "掌上考研(kaoyan.cn) 公开接口 · 2027届",
  "subs":  [考试科目串, ...],      # 字符串池
  "books": [参考书串, ...],        # 字符串池
  "schools": {
     "校名": [ [code, degI, modeI, college, score, scoreYr, subI, bookI, [[yr,n],...]], ... ]
  }
}
  degI   0=学硕 1=专硕 -1=其他
  modeI  0=全日制 1=非全日制 -1=其他
  score  复试线(min_score)，无则 -1
  scoreYr score_years 中最大年份，无则 -1
  subI   最新年份考试科目在 subs 的下标，无则 -1
  bookI  参考书在 books 的下标，无则 -1
  [[yr,n]] 各年招生人数（n>0），年份降序
"""
import json, os, re, collections

BASE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(BASE, "kaoyan_api", "details.jsonl")
OUT = os.path.join(BASE, "kao.json")

DEG = {"学硕": 0, "学术型硕士": 0, "学术学位": 0,
       "专硕": 1, "专业型硕士": 1, "专业学位": 1}
MODE = {"全日制": 0, "非全日制": 1}


def norm(s):
    s = re.sub(r"\s+", " ", str(s or "")).strip()
    return s


def norm_book(s):
    s = str(s or "")
    s = re.sub(r"<br\s*/?>", "；", s, flags=re.I)
    s = s.replace("\u200c", "").replace("\u200b", "")
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"；\s*；+", "；", s)
    return s.strip(" ；")


def pool_idx(pool, lst, s):
    if not s:
        return -1
    i = pool.get(s)
    if i is None:
        i = len(lst)
        pool[s] = i
        lst.append(s)
    return i


def main():
    if not os.path.exists(SRC):
        print("缺少", SRC, "——先跑 fetch_kaoyan.py")
        return
    subs, books = [], []
    spool, bpool = {}, {}
    codes = {}          # 专业代码 -> 专业名（供并集时补 KAO 独有专业）
    byschool = collections.defaultdict(list)
    n = 0
    with open(SRC, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except Exception:
                continue
            school = d.get("school") or ""
            code = (d.get("code") or "").strip()
            if not school or not code:
                continue
            n += 1
            nm = norm(d.get("name"))
            if nm:
                codes.setdefault(code, nm)
            years = d.get("years") or {}
            # 最新年份（用于取最新考试科目）
            ykeys = sorted([y for y in years if str(y).isdigit()], key=lambda x: -int(x))
            subj = ""
            for y in ykeys:
                v = years[y]
                if isinstance(v, list) and len(v) > 1 and norm(v[1]):
                    subj = norm(v[1])
                    break
            plans = []
            for y in ykeys:
                v = years[y]
                if isinstance(v, list) and v:
                    try:
                        k = int(v[0])
                    except Exception:
                        k = 0
                    if k > 0:
                        plans.append([int(y), k])
            sc = d.get("score")
            try:
                sc = int(sc)
            except Exception:
                sc = -1
            sy = d.get("score_years") or []
            syr = max([int(x) for x in sy if str(x).isdigit()], default=-1)
            rec = [
                code,
                DEG.get(norm(d.get("deg")), -1),
                MODE.get(norm(d.get("mode")), -1),
                norm(d.get("col"))[:40],
                sc, syr,
                pool_idx(spool, subs, subj),
                pool_idx(bpool, books, norm_book(d.get("book"))),
                plans,
            ]
            byschool[school].append(rec)

    # 每校内按 (code, degI, modeI, college) 排序去重
    schools = {}
    for s, arr in byschool.items():
        seen = set()
        uniq = []
        for r in arr:
            k = (r[0], r[1], r[2], r[3])
            if k in seen:
                continue
            seen.add(k)
            uniq.append(r)
        uniq.sort(key=lambda r: (r[0], r[1], r[3]))
        schools[s] = uniq

    # 院校层次（985 / 211 / 双一流）+ 省份，来自掌上考研 schoolList
    lvl = {}
    prov = {}
    sp = os.path.join(BASE, "kaoyan_api", "schools.json")
    if os.path.exists(sp):
        for sc in json.load(open(sp, encoding="utf-8")):
            nm = sc.get("school_name")
            if not nm:
                continue
            if sc.get("province_name"):
                prov[nm] = sc["province_name"]
            if str(sc.get("is_985")) == "1":
                lvl[nm] = "985"
            elif str(sc.get("is_211")) == "1":
                lvl[nm] = "211"
            elif str(sc.get("syl")) == "1":
                lvl[nm] = "双一流"

    out = {
        "src": "掌上考研(kaoyan.cn) 公开接口 · 2027届招生",
        "subs": subs, "books": books, "lvl": lvl, "prov": prov,
        "codes": codes, "schools": schools,
    }
    js = json.dumps(out, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    open(OUT, "w", encoding="utf-8").write(js)
    size = os.path.getsize(OUT)
    total_rows = sum(len(v) for v in schools.values())
    withscore = sum(1 for v in schools.values() for r in v if r[4] > 0)
    withsub = sum(1 for v in schools.values() for r in v if r[6] >= 0)
    withbook = sum(1 for v in schools.values() for r in v if r[7] >= 0)
    withplan = sum(1 for v in schools.values() for r in v if r[8])
    print(f"明细 {n} 条 -> {len(schools)} 校 / {total_rows} 行(校×专业×院系×学习方式)")
    print(f"  有复试线 {withscore} | 有考试科目 {withsub} | 有参考书 {withbook} | 有招生人数 {withplan}")
    print(f"  字符串池：科目 {len(subs)} 条 / 参考书 {len(books)} 条 | 省份 {len(prov)} 校 | 专业名 {len(codes)} 个")
    print(f"kao.json: {size//1024} KB ({size/1024/1024:.2f} MB)")


if __name__ == "__main__":
    main()
