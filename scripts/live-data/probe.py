#!/usr/bin/env python3
"""探测 6 份金山文档：file_id / 类型 / 工作表清单。"""
import json, subprocess, sys

SOURCES = [
    ("action_report", "https://www.kdocs.cn/l/cbwp2cvTiFyK"),
    ("psych_v4", "https://www.kdocs.cn/l/cgd3nVre7qWs"),
    ("psych_visits", "https://www.kdocs.cn/l/coL1GfCvA0an"),
    ("butler_contacts", "https://www.kdocs.cn/l/ctlu8ktnEwi8"),
    ("service_followups", "https://www.kdocs.cn/l/cuOhExpV6n29"),
    ("arrival_register", "https://www.kdocs.cn/l/cp4lRRCVcqVa"),
]


def cli(*args):
    """调用 kdocs-cli，容忍尾部升级提示等非 JSON 尾巴。"""
    p = subprocess.run(["kdocs-cli", *args], capture_output=True, text=True, timeout=180)
    out = (p.stdout or "").strip()
    try:
        obj, _ = json.JSONDecoder().raw_decode(out)
        return obj
    except Exception:
        return {"_raw": out[:500], "_err": (p.stderr or "").strip()[:300]}


def unwrap(obj):
    """kdocs-cli 有时形成 data.data 两层包裹。"""
    d = obj.get("data") if isinstance(obj, dict) else None
    if isinstance(d, dict) and isinstance(d.get("data"), dict):
        return d["data"]
    return d or {}


def main():
    result = {}
    for sid, url in SOURCES:
        info = cli("drive", "get-file-info", json.dumps({"url": url}))
        d = unwrap(info)
        fid = d.get("id")
        rec = {
            "id": sid,
            "url": url,
            "fileId": fid,
            "name": d.get("name"),
            "type": d.get("type"),
            "size": d.get("size"),
            "mtime": d.get("mtime"),
        }
        if fid:
            sh = cli("sheet", "get-sheets-info", json.dumps({"file_id": fid}))
            sd = unwrap(sh)
            sheets = (sd.get("detail") or {}).get("sheetsInfo") or sd.get("sheetsInfo") or []
            rec["sheets"] = [
                {
                    "sheetId": s.get("sheetId"),
                    "name": s.get("sheetName"),
                    "rowTo": s.get("rowTo"),
                    "colTo": s.get("colTo"),
                    "visible": s.get("isVisible"),
                    "idx": s.get("sheetIdx"),
                }
                for s in sheets
            ]
            rec["sheetsCount"] = len(rec["sheets"])
        result[sid] = rec
        print(json.dumps(rec, ensure_ascii=False), flush=True)
    with open("data/raw-kdocs/_probe.json", "w") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
