#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""医院经营协同看板 · 单端口服务（静态站 + 小 API + SQLite）

为什么要有这个文件
------------------
看板原先只有两种形态：
  ① 纯静态（线上部署）—— 拖图导入只能写浏览器 localStorage，换设备就丢；
  ② 本地 SQLite + 构建脚本 —— 数据是真的，但只有本机命令行能写入。
两者之间缺一个「能被浏览器调用的写入口」。本服务补的就是这一层：
同一个端口既发静态文件，也接受导入写入，并把重算后的快照吐回去。

关键约束（别绕开）
------------------
· 零第三方依赖：只用标准库。sites 沙箱只给一个 HTTP 端口，没有数据库/缓存，
  能带在项目里的持久化只有文件 —— 所以是 SQLite（随项目发布）。
· 口径只有一份：写入后调 scripts/live-data/build_snapshot.py 的同一套公式重算，
  不在服务端再写第二份「本期营收怎么加」。
· 缺项写 NULL 不写 0：导入里没填的字段留空，让快照按契约标 provisional。
· 写入前先删该日旧行：营收日报是「一天一行」的粒度，同日重导必须覆盖，
  否则 SUM 会翻倍（历史上真翻过倍，见 2026-10-18 记录）。

接口
----
GET  /api/health                     健康检查
GET  /api/operations/v1/snapshot     发布快照（data/snapshot.json）
GET  /api/revenue                    逐日营收覆盖层，给导入抽屉回填
POST /api/imports                    写库 + 重算 + 返回新快照摘要
GET  /api/events                     SSE，revision 变化即推送
"""
import json
import mimetypes
import os
import posixpath
import sys
import threading
import time
import traceback
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlparse

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "scripts", "live-data"))

import live_db          # noqa: E402
import build_snapshot   # noqa: E402

CN = timezone(timedelta(hours=8))

# ── 库的分层（别合并成一个路径，理由见下）──────────────────────────
#   deploy-seed.sqlite : 部署用的脱敏种子（pull 原始层已清空，不含患者姓名/电话）
#   live-data.sqlite   : 本机全量库（含 pull 原始层，只在本地用，会上云就换成种子）
#   runtime.sqlite     : 运行时库。**导入写的是它**。
# 为什么要多这一层：沙箱的 /workspace 是持久目录，重新部署只会覆盖包内文件。
# 若直接写种子库，用户手工导入的数据会在下一次发布时被整包覆盖掉。
# 现在 runtime 不在包里 ⇒ 发布不会碰它，数据跨发布保留；沙箱被重建时则从种子重来。
_SEED_CANDIDATES = [os.path.join(ROOT, "db", "deploy-seed.sqlite"),
                    os.path.join(ROOT, "db", "live-data.sqlite")]
SEED_PATH = next((p for p in _SEED_CANDIDATES if os.path.exists(p)), _SEED_CANDIDATES[-1])
DB_PATH = os.environ.get("OPS_DB") or os.path.join(ROOT, "db", "runtime.sqlite")
SNAP_PATH = os.path.join(ROOT, "data", "snapshot.json")
PORT = int(os.environ.get("PORT") or 8787)
HOST = os.environ.get("HOST") or "0.0.0.0"

# 写入口令：设了才校验。公网部署时请务必设置，否则谁都能改数。
WRITE_TOKEN = os.environ.get("OPS_WRITE_TOKEN") or ""

REV_SOURCE = "revenue_daily_report"
REV_SHEET = "MANUAL_IMPORT"

# 前端日数组顺序：0门诊 1在院 2初诊 3复诊 4在院人数 5入院 6出院
FIELDS = [
    ("outpatient", "revenue.outpatient", "元"),
    ("inpatient", "revenue.inpatient", "元"),
    ("visitsNew", "visit.new", "人次"),
    ("visitsReturn", "visit.return", "人次"),
    ("ward", "ward.count", "人"),
    ("admit", "admit", "人"),
    ("discharge", "discharge", "人"),
]

# 静态服务白名单之外的目录/后缀一律不对外。
# 理由不是「好看」：db/ 里是院内逐日经营数据，scripts/ 里有内网地址与采集逻辑，
# 发布到公网后任何人拿到 URL 就能直接下载。宁可 404。
_BLOCK_DIRS = {"db", "scripts", "logs", "output", "tmp", "docs", "node_modules",
               ".git", ".workbuddy", ".trash-20261018"}
_BLOCK_EXT = (".sqlite", ".sqlite-journal", ".db", ".py", ".sh", ".mjs", ".env",
              ".log", ".bak", ".bak-rollup-1012", ".bak-rollup5")

_LOCK = threading.Lock()          # 写串行化：SQLite 单写者 + 重算不能并发
_CACHE = {"snap": None, "mtime": 0.0}
_SSE_TICK = 2.0


def now_iso():
    return datetime.now(CN).isoformat(timespec="seconds")


def ensure_runtime_db():
    """首次启动时把种子库落成运行时库；之后一直用它，发布不再覆盖。"""
    if os.path.exists(DB_PATH):
        return False
    if not os.path.exists(SEED_PATH):
        raise SystemExit("既没有运行时库也没有种子库：%s" % SEED_PATH)
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    # 用读写而非 copy2：沙箱对「复制后改属性」有额外限制，纯字节写入最稳
    with open(SEED_PATH, "rb") as f:
        data = f.read()
    with open(DB_PATH, "wb") as f:
        f.write(data)
    return True


# ----------------------------------------------------------------- 库
def ensure_import_log(c):
    c.execute("""CREATE TABLE IF NOT EXISTS import_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        imported_at TEXT NOT NULL,
        business_dates TEXT NOT NULL,
        rows_json TEXT NOT NULL,
        files_json TEXT,
        client TEXT)""")
    c.commit()


def read_snapshot():
    """读发布快照。按 mtime 缓存，POST 重算后文件变了自动失效。"""
    try:
        m = os.path.getmtime(SNAP_PATH)
    except OSError:
        return None
    if _CACHE["snap"] is not None and m == _CACHE["mtime"]:
        return _CACHE["snap"]
    with open(SNAP_PATH, encoding="utf-8") as f:
        snap = json.load(f)
    _CACHE["snap"], _CACHE["mtime"] = snap, m
    return snap


def read_revenue_days():
    """逐日营收覆盖层 → {date: [7 个值]}，给前端导入抽屉回填。"""
    c = live_db.connect(DB_PATH, schema=False)
    try:
        rows = c.execute(
            "SELECT metric_id, business_date, SUM(value) FROM fact "
            "WHERE source_id=? GROUP BY 1,2", (REV_SOURCE,)).fetchall()
    finally:
        c.close()
    by_metric = {}
    for mid, d, v in rows:
        by_metric.setdefault(d, {})[mid] = None if v is None else round(v, 2)
    out = {}
    for d, m in by_metric.items():
        out[d] = [m.get(mid) for _k, mid, _u in FIELDS]
    return out


def apply_import(rows, files=None, client=""):
    """把导入行写进事实库，然后按同一套口径重算发布快照。

    每行先删该日该源的全部 fact（不管原来来自 SEED 还是上次人工导入），
    再写 7 个 metric —— 营收日报是「一天一行」，同日二次导入必须覆盖而不是叠加。
    """
    if not rows:
        raise ValueError("没有可写入的数据行")
    stamped = now_iso()
    touched = []
    backup = []           # 重算失败时把本日旧行原样放回去
    with _LOCK:
        c = live_db.connect(DB_PATH, schema=False)
        try:
            ensure_import_log(c)
            for r in rows:
                d = str(r.get("date") or "").strip()
                if len(d) != 10 or d[4] != "-" or d[7] != "-":
                    raise ValueError("日期格式不对：%r" % (d,))
                try:
                    datetime.strptime(d, "%Y-%m-%d")
                except ValueError:
                    raise ValueError("日期不存在：%s（例：2026-10-18）" % d)
                old_rows = c.execute(
                    "SELECT metric_id,business_date,dim_key,dim_value,value,unit,source_id,"
                    "sheet_name,row_ref,status,fetched_at FROM fact "
                    "WHERE source_id=? AND business_date=?", (REV_SOURCE, d)).fetchall()
                backup.extend(old_rows)
                old_val = {row[0]: row[4] for row in old_rows}
                c.execute("DELETE FROM fact WHERE source_id=? AND business_date=?",
                          (REV_SOURCE, d))
                for key, mid, unit in FIELDS:
                    v = r.get(key)
                    if v is not None and v != "":
                        try:
                            v = round(float(v), 2)
                        except (TypeError, ValueError):
                            raise ValueError("%s 的 %s 不是数字：%r" % (d, key, v))
                    else:
                        # 只做了部分字段的修订时，未填的沿用该日已有值，
                        # 不能把「没提到」当成「归零/清空」—— 那会把在院人数抹掉。
                        v = old_val.get(mid)
                    c.execute(
                        "INSERT INTO fact(metric_id,business_date,dim_key,dim_value,value,unit,"
                        "source_id,sheet_name,row_ref,status,fetched_at) "
                        "VALUES(?,?,'','',?,?,?,?,?,'ok',?)",
                        (mid, d, v, unit, REV_SOURCE, REV_SHEET, d, stamped))
                touched.append(d)
            c.execute(
                "INSERT INTO import_log(imported_at,business_dates,rows_json,files_json,client) "
                "VALUES(?,?,?,?,?)",
                (stamped, ",".join(touched), json.dumps(rows, ensure_ascii=False),
                 json.dumps(files or [], ensure_ascii=False), client or ""))
            c.commit()
        except Exception:
            c.rollback()
            raise
        finally:
            c.close()

        # 同一套公式重算：口径只有一份，不在这里另写加减法。
        # ⚠ 重算失败必须把刚写的行换回去，否则「库里有、快照没有」，
        #   页面显示的是旧数，而库里已经是新数，排查时极容易看错。
        try:
            snap = build_snapshot.main(db_path=DB_PATH)
        except Exception:
            c2 = live_db.connect(DB_PATH, schema=False)
            try:
                for d in touched:
                    c2.execute("DELETE FROM fact WHERE source_id=? AND business_date=?",
                               (REV_SOURCE, d))
                for b in backup:
                    c2.execute(
                        "INSERT INTO fact(metric_id,business_date,dim_key,dim_value,value,unit,"
                        "source_id,sheet_name,row_ref,status,fetched_at) "
                        "VALUES(?,?,?,?,?,?,?,?,?,?,?)", b)
                c2.commit()
            finally:
                c2.close()
            raise
        _CACHE["snap"] = None
        _CACHE["mtime"] = 0.0
    return snap, touched


# ----------------------------------------------------------------- HTTP
class Handler(BaseHTTPRequestHandler):
    server_version = "OpsBoard/1.0"
    protocol_version = "HTTP/1.1"

    # --- 工具 -----------------------------------------------------
    def log_message(self, fmt, *args):
        sys.stderr.write("%s %s\n" % (self.address_string(), fmt % args))

    def _json(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _err(self, code, msg):
        self._json(code, {"ok": False, "error": msg})

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n <= 0:
            return {}
        raw = self.rfile.read(n)
        return json.loads(raw.decode("utf-8"))

    # --- 路由 -----------------------------------------------------
    def do_GET(self):
        path = urlparse(self.path).path
        try:
            if path == "/api/health":
                return self._json(200, {"ok": True, "db": os.path.basename(DB_PATH),
                                        "snapshot": os.path.exists(SNAP_PATH),
                                        "now": now_iso()})
            if path == "/api/revenue":
                return self._json(200, {"ok": True, "daily": read_revenue_days(),
                                        "updatedAt": now_iso()})
            if path in ("/api/operations/v1/snapshot", "/api/snapshot"):
                snap = read_snapshot()
                if not snap:
                    return self._err(503, "快照尚未生成")
                return self._json(200, snap)
            if path == "/api/events":
                return self._sse()
            return self._static(path)
        except Exception:
            traceback.print_exc()
            return self._err(500, "服务端异常，详见日志")

    def do_POST(self):
        path = urlparse(self.path).path
        if path not in ("/api/imports", "/api/corrections"):
            return self._err(404, "未知接口")
        if WRITE_TOKEN:
            got = self.headers.get("X-Ops-Token") or ""
            if got != WRITE_TOKEN:
                return self._err(401, "写入口令不正确")
        try:
            body = self._body()
        except Exception:
            return self._err(400, "请求体不是合法 JSON")
        rows = body.get("rows") or []
        files = body.get("files") or []
        client = body.get("client") or ""
        try:
            snap, touched = apply_import(rows, files, client)
        except ValueError as e:
            return self._err(400, str(e))
        except Exception:
            traceback.print_exc()
            return self._err(500, "写入失败，详见服务端日志")
        m = snap["metrics"]
        return self._json(200, {
            "ok": True,
            "writtenDays": touched,
            "revision": snap.get("revision"),
            "dataThrough": snap["period"]["dataThrough"],
            "daysRecorded": snap["period"]["daysRecorded"],
            "summary": {
                "weekRevenueWan": m["weekRevenue"]["value"],
                "monthRevenueWan": m["monthRevenue"]["value"],
                "deltaPct": m["weekRevenue"].get("deltaPct"),
            },
        })

    # --- SSE ------------------------------------------------------
    def _sse(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        last = None
        try:
            while True:
                snap = read_snapshot() or {}
                rev = snap.get("revision")
                if rev != last:
                    payload = json.dumps({"type": "snapshot", "revision": rev,
                                          "asOf": snap.get("asOf")}, ensure_ascii=False)
                    self.wfile.write(("event: snapshot\ndata: %s\n\n" % payload).encode("utf-8"))
                    self.wfile.flush()
                    last = rev
                time.sleep(_SSE_TICK)
        except (BrokenPipeError, ConnectionResetError):
            return

    # --- 静态 -----------------------------------------------------
    def _static(self, path):
        if path in ("/", ""):
            path = "/index.html"
        rel = unquote(path).lstrip("/")
        # 防穿越：规范化后必须仍在 ROOT 内
        rel = posixpath.normpath(rel)
        if rel.startswith("..") or rel.startswith("/"):
            return self._err(403, "禁止访问")
        if rel.split("/")[0] in _BLOCK_DIRS or rel.endswith(_BLOCK_EXT):
            return self._err(404, "文件不存在")
        full = os.path.join(ROOT, rel.replace("/", os.sep))
        if not os.path.isfile(full):
            # 单页应用兜底：未知路径回 index.html（不带扩展名才算）
            if "." not in posixpath.basename(rel):
                full = os.path.join(ROOT, "index.html")
            else:
                return self._err(404, "文件不存在：%s" % rel)
        ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/javascript", "application/json"):
            ctype += "; charset=utf-8"
        try:
            with open(full, "rb") as f:
                data = f.read()
        except OSError:
            return self._err(500, "读取文件失败")
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        # 页面与其引用的脚本一律协商缓存：版本号写在 ?v= 里，靠它破缓存
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(data)


def main():
    created = ensure_runtime_db()
    if not os.path.exists(DB_PATH):
        sys.stderr.write("找不到事实库：%s\n" % DB_PATH)
        sys.exit(1)
    srv = ThreadingHTTPServer((HOST, PORT), Handler)
    srv.daemon_threads = True
    sys.stderr.write("看板服务已启动 http://%s:%d/  (db=%s%s)\n"
                     % (HOST, PORT, DB_PATH, "，由种子新建" if created else ""))
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
