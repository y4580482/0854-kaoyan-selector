# -*- coding: utf-8 -*-
"""通过 GitHub REST API 推送当前已提交的工作树到 master（绕开 github.com git 传输被墙）。"""
import os, sys, json, base64, subprocess, tempfile

TOKEN = os.environ.get("GHTOKEN")
if not TOKEN:
    sys.exit("缺少 GHTOKEN 环境变量")
REPO = "y4580482/0854-kaoyan-selector"
API = "https://api.github.com"
BASE = os.path.dirname(os.path.abspath(__file__))
MSG = "v5.2: 两源并集做到「所有专业都能查」——研招网919校∪掌上考研930校=1047校/1483专业代码/42823条(+5101)，顶部搜索框直接命中全量专业库，兼容全角括号/校区后缀校名差异"


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        sys.exit(f"curl 失败: {cmd[0:4]}\n{r.stderr[-1500:]}")
    return r.stdout


PROXY = os.environ.get("https_proxy") or os.environ.get("HTTPS_PROXY") \
          or os.environ.get("http_proxy") or os.environ.get("HTTP_PROXY")


def api(method, path, body_file=None):
    url = API + path
    cmd = ["curl", "-sS", "--http1.1", "--ssl-no-revoke",
           "--connect-timeout", "20", "--max-time", "900", "-H", "Expect:"]
    if PROXY:
        cmd += ["-x", PROXY]
    cmd += ["-H", f"Authorization: Bearer {TOKEN}",
            "-H", "Accept: application/vnd.github+json",
            "-X", method, url]
    if body_file:
        cmd += ["-H", "Content-Type: application/json", "--data-binary", "@" + body_file]
    out = run(cmd)
    try:
        return json.loads(out)
    except Exception:
        sys.exit(f"非 JSON 响应 {method} {path}:\n{out[:1500]}")


print("使用代理:", PROXY or "(无，直连)")
ref = api("GET", f"/repos/{REPO}/git/ref/heads/master")
parent = ref["object"]["sha"]
print("当前 master:", parent[:10])

ls = subprocess.run(["git", "-c", "core.quotepath=false", "ls-files"],
                    capture_output=True, text=True, encoding="utf-8", cwd=BASE).stdout
paths = [p for p in ls.splitlines() if p.strip()]
print("待推送文件数:", len(paths))

entries = []
big = 0
for p in paths:
    fp = os.path.join(BASE, p)
    if not os.path.isfile(fp):
        continue
    raw = open(fp, "rb").read()
    b64 = base64.b64encode(raw).decode("ascii")
    if len(b64) > 800_000:
        big += 1
    tf = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
    tf.write(json.dumps({"content": b64, "encoding": "base64"}))
    tf.close()
    res = api("POST", f"/repos/{REPO}/git/blobs", tf.name)
    os.unlink(tf.name)
    entries.append({"path": p, "mode": "100644", "type": "blob", "sha": res["sha"]})

print(f"blob 已建 {len(entries)} 个（其中大文件 {big} 个）")

tree_file = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
tree_file.write(json.dumps({"tree": entries}))
tree_file.close()
tree = api("POST", f"/repos/{REPO}/git/trees", tree_file.name)
os.unlink(tree_file.name)
print("tree:", tree["sha"][:10])

cm_file = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
cm_file.write(json.dumps({"message": MSG, "tree": tree["sha"], "parents": [parent]}))
cm_file.close()
commit = api("POST", f"/repos/{REPO}/git/commits", cm_file.name)
os.unlink(cm_file.name)
print("commit:", commit["sha"][:10])

rb_file = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
rb_file.write(json.dumps({"sha": commit["sha"], "force": False}))
rb_file.close()
api("PATCH", f"/repos/{REPO}/git/refs/heads/master", rb_file.name)
os.unlink(rb_file.name)
print("✅ 已更新 master ->", commit["sha"][:10])
print("👉 https://github.com/" + REPO)
