# -*- coding: utf-8 -*-
"""
掌上考研 (api.kaoyan.cn) 全量采集：所有学校所有专业的
  复试分数线(min_score) + 多年招生人数 + 考试科目 + 参考书 + 院系/学位/学习方式

三层接口（均 POST JSON，无需鉴权）：
  /app/school/schoolList     {page,limit,province_id?,school_name?}  -> 1109 校
  /app/school/planListV2     {page,limit,school_id}                  -> 该校当年专业(含 plan_id)
  /app/school/planDetailV2   {is_apply:2, plan_id}                   -> 详情

产物（目录 kaoyan_api/）：
  schools.json      全部学校
  plans.jsonl       每条: {sid, school, pid, code, name, deg, mode, col}
  details.jsonl     每条: 精简详情（断点续传依据：已完成的 pid 不重抓）
  _progress.txt     进度快照

用法：
  python -u fetch_kaoyan.py            # 全量（自动续传）
  python -u fetch_kaoyan.py --limit 5  # 只抓前 5 所学校（试跑）
"""
import json, os, sys, time, random, threading, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "kaoyan_api")
os.makedirs(OUT, exist_ok=True)

PROXY = os.environ.get("KAOYAN_PROXY") or ""  # 默认直连（api.kaoyan.cn 未被墙），需要时才设 KAOYAN_PROXY
BASE = "https://api.kaoyan.cn/app"
HDR = {
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (Linux; Android 12) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110 Mobile Safari/537.36",
    "Referer": "https://www.kaoyan.cn/",
    "Origin": "https://www.kaoyan.cn",
}
_opener = urllib.request.build_opener(
    urllib.request.ProxyHandler({"http": PROXY, "https": PROXY}) if PROXY else urllib.request.ProxyHandler({})
)

WORKERS_DETAIL = 10
WORKERS_LIST = 8

PRINT_LOCK = threading.Lock()


def log(*a):
    with PRINT_LOCK:
        print(*a, flush=True)


def post(path, payload, timeout=30, retries=5):
    """带重试的 POST。返回 dict 或 None。"""
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(BASE + path, data=body, headers=HDR, method="POST")
            with _opener.open(req, timeout=timeout) as r:
                txt = r.read().decode("utf-8", "replace")
            return json.loads(txt)
        except urllib.error.HTTPError as e:
            last = "HTTP %s" % e.code
            if e.code in (429, 503, 502, 504):
                time.sleep(2.0 * (i + 1) + random.random())
                continue
            time.sleep(1.2 * (i + 1))
        except Exception as e:
            last = repr(e)
            time.sleep(1.5 * (i + 1) + random.random())
    return None


# ---------------- Phase A: 学校 ----------------
def fetch_schools():
    fp = os.path.join(OUT, "schools.json")
    if os.path.exists(fp):
        d = json.load(open(fp, encoding="utf-8"))
        log("[A] 复用 schools.json ->", len(d), "校")
        return d
    out, page = [], 1
    while True:
        r = post("/school/schoolList", {"page": page, "limit": 100})
        if not r or r.get("code") != "0000":
            log("[A] 第", page, "页失败，重试一次")
            r = post("/school/schoolList", {"page": page, "limit": 100})
            if not r or r.get("code") != "0000":
                break
        d = r["data"] or {}
        arr = d.get("data") or []
        tot = d.get("total") or 0
        out += arr
        log("[A] page %d  +=%d  total=%d/%d" % (page, len(arr), len(out), tot))
        if not arr or len(out) >= tot:
            break
        page += 1
    json.dump(out, open(fp, "w", encoding="utf-8"), ensure_ascii=False)
    log("[A] 学校总数 =", len(out))
    return out


# ---------------- Phase B: 各校专业列表 ----------------
def fetch_plans(schools):
    fp = os.path.join(OUT, "plans.jsonl")
    done_sids = set()
    if os.path.exists(fp):
        for line in open(fp, encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            try:
                done_sids.add(json.loads(line)["sid"])
            except Exception:
                pass
        log("[B] 已有 %d 校的专业列表，续抓其余" % len(done_sids))

    f = open(fp, "a", encoding="utf-8")
    lock = threading.Lock()
    todo = [s for s in schools if s.get("school_id") not in done_sids]
    log("[B] 待抓学校 =", len(todo))

    def one(sc):
        sid = sc.get("school_id")
        sname = sc.get("school_name")
        rows = []
        page = 1
        while True:
            r = post("/school/planListV2", {"page": page, "limit": 100, "school_id": sid})
            if not r or r.get("code") != "0000":
                break
            d = r["data"] or {}
            arr = d.get("data") or []
            tot = d.get("total") or len(arr)
            for p in arr:
                rows.append({
                    "sid": sid, "school": sname, "pid": p.get("plan_id"),
                    "code": p.get("special_code"), "name": p.get("special_name"),
                    "l1": p.get("level1_name"), "l2": p.get("level2_name"),
                    "deg": p.get("degree_type_name"), "mode": p.get("recruit_type_name"),
                    "col": p.get("depart_name"), "yr": p.get("year"),
                    "n": p.get("recruit_number"),
                })
            if not arr or len(rows) >= tot:
                break
            page += 1
        with lock:
            for x in rows:
                f.write(json.dumps(x, ensure_ascii=False) + "\n")
            f.flush()
        return sid, sname, len(rows)

    n = 0
    with ThreadPoolExecutor(max_workers=WORKERS_LIST) as ex:
        futs = [ex.submit(one, sc) for sc in todo]
        for fu in as_completed(futs):
            try:
                sid, sname, c = fu.result()
            except Exception as e:
                log("[B] err", repr(e)); continue
            n += 1
            if n % 25 == 0 or n == len(todo):
                log("[B] %d/%d 校  最近: %s(%d 专业)" % (n, len(todo), sname, c))
    f.close()

    plans = [json.loads(l) for l in open(fp, encoding="utf-8") if l.strip()]
    # 去重（按 pid）
    uniq = {}
    for p in plans:
        if p.get("pid"):
            uniq[p["pid"]] = p
    plans = list(uniq.values())
    log("[B] 专业总数 =", len(plans))
    return plans


# ---------------- Phase C: 专业详情 ----------------
def slim_detail(pid, d):
    """把 planDetailV2 的 data 压成精简结构。"""
    years = {}
    rad = d.get("research_area_data") or {}
    for y, arr in rad.items():
        if not isinstance(arr, list) or not arr:
            continue
        a0 = arr[0] or {}
        subj = (a0.get("exam_subject") or "").strip()
        cnt = a0.get("recruit_number")
        note = (a0.get("note") or "").strip()
        # 合并方向级人数（部分学校按方向给数）
        tot = None
        try:
            vals = [int(x.get("recruit_number")) for x in arr if str(x.get("recruit_number", "")).strip().isdigit()]
            tot = sum(vals) if vals else None
        except Exception:
            tot = None
        years[str(y)] = [cnt if cnt is not None else tot, subj, note]
    book = (d.get("exam_book") or "").strip()
    return {
        "pid": pid,
        "sid": d.get("school_id"),
        "code": d.get("special_code"),
        "name": d.get("special_name"),
        "deg": d.get("degree_type_name"),
        "mode": d.get("recruit_type_name"),
        "col": d.get("depart_name"),
        "score": d.get("min_score"),
        "score_years": d.get("score_years") or [],
        "book": book[:300],
        "book_year": d.get("exam_book_year"),
        "years": years,
    }


def fetch_details(plans):
    fp = os.path.join(OUT, "details.jsonl")
    done = set()
    if os.path.exists(fp):
        for line in open(fp, encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            try:
                done.add(json.loads(line)["pid"])
            except Exception:
                pass
        log("[C] 已完成 %d 条详情，续抓其余" % len(done))

    todo = [p for p in plans if p.get("pid") not in done]
    log("[C] 待抓详情 =", len(todo))
    if not todo:
        return fp

    f = open(fp, "a", encoding="utf-8")
    lock = threading.Lock()
    stat = {"ok": 0, "fail": 0, "n": 0}
    t0 = time.time()

    def one(p):
        r = post("/school/planDetailV2", {"is_apply": 2, "plan_id": p["pid"]})
        if not r or r.get("code") != "0000" or not isinstance(r.get("data"), dict):
            return None
        rec = slim_detail(p["pid"], r["data"])
        rec["school"] = p.get("school")
        return rec

    with ThreadPoolExecutor(max_workers=WORKERS_DETAIL) as ex:
        futs = {ex.submit(one, p): p for p in todo}
        for fu in as_completed(futs):
            p = futs[fu]
            try:
                rec = fu.result()
            except Exception as e:
                rec = None
            with lock:
                stat["n"] += 1
                if rec:
                    stat["ok"] += 1
                    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                else:
                    stat["fail"] += 1
                if stat["n"] % 200 == 0:
                    f.flush()
                    el = time.time() - t0
                    rate = stat["n"] / el if el > 0 else 0
                    remain = (len(todo) - stat["n"]) / rate if rate > 0 else 0
                    log("[C] %d/%d ok=%d fail=%d  %.1f/s  剩余约 %.0f 分"
                        % (stat["n"], len(todo), stat["ok"], stat["fail"], rate, remain / 60))
    f.flush(); f.close()
    log("[C] 完成：ok=%d fail=%d，用时 %.0f 秒" % (stat["ok"], stat["fail"], time.time() - t0))
    return fp


def main():
    limit = 0
    if "--limit" in sys.argv:
        i = sys.argv.index("--limit")
        limit = int(sys.argv[i + 1])
    log("PROXY =", PROXY or "(none)")
    schools = fetch_schools()
    if limit:
        schools = schools[:limit]
    plans = fetch_plans(schools)
    fetch_details(plans)
    log("ALL DONE")


if __name__ == "__main__":
    main()
