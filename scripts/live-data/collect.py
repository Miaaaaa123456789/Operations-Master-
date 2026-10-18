#!/usr/bin/env python3
"""采集 6 份金山文档 → data/raw-kdocs/<source>/<sheet>.json（稠密二维数组，已展开合并单元格）。

约定：
- 只读白名单内的工作表；psych_visits 严格限前三张（新-排班 / 课程排班 / 团体治疗登记）。
- 分块读取（每块 200 行），避免单次响应过大。
- 合并单元格按 rowFrom/rowTo/colFrom/colTo 展开填充，保留"跨行日期"这类语义。
"""
import json, os, re, subprocess, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "data", "raw-kdocs")
CHUNK = 200

# source -> (fileId, colCap, [(sheetId, sheetName), ...])
PLAN = {
    "action_report": ("AQxj9iAVMrMJGYmLrPL5rxQrsDvJiKR17", 24, [
        (3, "医生组"), (4, "护理组"), (5, "心理咨询组"), (6, "客服服务部"), (8, "营销中心"),
    ]),
    "psych_v4": ("fdg34kWW8xM3A1fVCrSP1xhVhBazPDzkt", 60, [
        (4, "日报原始数据"), (5, "团队查房日报"), (7, "周个人统计"),
        (10, "组长日管理"), (11, "咨询师每日简报"), (15, "管床心理师患者对接表"),
    ]),
    "psych_visits": ("z6x6JbCFfxMDK32s7KRyrxLXkT3MBZ1cp", 32, [
        (19, "新-排班"), (3, "课程排班"), (5, "团体治疗登记"),
    ]),
    "butler_contacts": ("zTTYxTcbJxMXBcbnnZ8ZrxTDRareiGEH9", 16, [
        (1, "菲菲"), (2, "国威"), (3, "金林"), (4, "朱婧"), (6, "利娟"),
    ]),
    "service_followups": ("qRzhvsBzrxMY7DuYWNPQrxuTUqMUNHPcJ", 24, [
        (2, "标准化回访台账"), (3, "客户投诉处理登记表"),
        (4, "导诊主动服务记录表"), (7, "日工作量考核表"),
    ]),
    "arrival_register": ("rswrTbnrK1MdNt3KLL5t1xyYVTpbCRGVZ", 14, [
        (3, "工作表1"),
    ]),
}


def cli(*args, retries=3):
    """调用 kdocs-cli，带重试（在线表格偶发超时）。"""
    last = None
    for attempt in range(retries):
        p = subprocess.run(["kdocs-cli", *args], capture_output=True, text=True, timeout=300)
        out = (p.stdout or "").strip()
        try:
            obj, _ = json.JSONDecoder().raw_decode(out)
            return obj
        except Exception:
            last = f"{out[:200]} / {(p.stderr or '')[:160]}"
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"kdocs-cli 多次失败: {last}")


def unwrap(obj):
    d = obj.get("data") if isinstance(obj, dict) else None
    if isinstance(d, dict) and isinstance(d.get("data"), dict):
        return d["data"]
    return d or {}


def cell_text(c):
    t = c.get("cellText")
    if t is None or t == "":
        t = (c.get("understandableType") or {}).get("value")
    return "" if t is None else str(t).strip()


def read_sheet(fid, sid, col_cap, row_end):
    grid = {}
    maxr = maxc = 0
    r = 0
    while r <= row_end:
        r1 = min(r + CHUNK - 1, row_end)
        payload = {
            "file_id": fid, "worksheet_id": sid,
            "range": {"rowFrom": r, "rowTo": r1, "colFrom": 0, "colTo": col_cap - 1},
        }
        data = unwrap(cli("sheet", "get-range-data", json.dumps(payload)))
        cells = (data.get("detail") or {}).get("rangeData") or data.get("rangeData") or []
        for c in cells:
            txt = cell_text(c)
            if not txt:
                continue
            cr0 = c.get("rowFrom", 0); cr1 = c.get("rowTo", cr0)
            cc0 = c.get("colFrom", 0); cc1 = c.get("colTo", cc0)
            for rr in range(cr0, min(cr1, r1) + 1):
                for cc in range(cc0, min(cc1, col_cap - 1) + 1):
                    grid[(rr, cc)] = txt
                    maxr = max(maxr, rr); maxc = max(maxc, cc)
        r = r1 + 1
    rows = [[grid.get((i, j), "") for j in range(maxc + 1)] for i in range(maxr + 1)]
    return rows


def safe(name):
    return re.sub(r"[^\w\u4e00-\u9fa5\-]+", "_", name).strip("_")


def main():
    summary = []
    failed = []
    # ⛔ 2026-10-18 修：原先**每张表**都调一次 get-sheets-info，24 张表＝24 次冗余请求，
    #    既慢又把"最后一站接口 EOF"的概率放大到必现。改为**每个文件只取一次**并缓存。
    #    另外 get-sheets-info 失败**不能中断整轮采集**（真会丢一整批源），
    #    取不到就退化为默认行数上限，把失败记进 manifest。
    meta_cache = {}

    def file_meta(fid):
        if fid in meta_cache:
            return meta_cache[fid]
        try:
            m = unwrap(cli("sheet", "get-sheets-info", json.dumps({"file_id": fid})))
            info = {s["sheetId"]: s for s in ((m.get("detail") or {}).get("sheetsInfo") or [])}
        except Exception as e:
            print(f"  ⚠ 表元信息获取失败，退化默认行数：{str(e)[:110]}", flush=True)
            info = {}
        meta_cache[fid] = info
        return info

    for src, (fid, cap, sheets) in PLAN.items():
        d = os.path.join(OUT, src)
        os.makedirs(d, exist_ok=True)
        info = file_meta(fid)
        for sid, name in sheets:
            row_end = (info.get(sid) or {}).get("rowTo", 200)
            row_end = min(row_end, 1200)
            t0 = time.time()
            try:
                rows = read_sheet(fid, sid, cap, row_end)
            except Exception as e:
                print(f"  ⚠ {src}/{name} 本次抓取失败，沿用上一版：{str(e)[:120]}", flush=True)
                failed.append(f"{src}/{name}")
                continue
            path = os.path.join(d, f"{sid}-{safe(name)}.json")
            with open(path, "w") as f:
                json.dump({"source": src, "fileId": fid, "sheetId": sid, "sheetName": name,
                           "rows": rows, "pulledAt": time.strftime("%Y-%m-%dT%H:%M:%S%z")},
                          f, ensure_ascii=False)
            filled = sum(1 for row in rows for v in row if v)
            rec = f"{src}/{name}: {len(rows)}行x{(len(rows[0]) if rows else 0)}列 非空{filled} ({time.time()-t0:.1f}s)"
            print(rec, flush=True)
            summary.append(rec)
    with open(os.path.join(OUT, "_manifest.json"), "w") as f:
        json.dump({"pulledAt": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                   "sheets": summary, "failed": failed}, f, ensure_ascii=False, indent=2)
    if failed:
        print(f"部分工作表未取到（{len(failed)}）：{'、'.join(failed)}", flush=True)


if __name__ == "__main__":
    main()
