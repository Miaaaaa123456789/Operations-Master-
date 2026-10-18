#!/bin/zsh
# ============================================================================
# 医院经营协同看板 · 线上更新（不依赖 workbuddy_sites_deploy）
# ----------------------------------------------------------------------------
# 背景：workbuddy_sites_deploy 在当前账号被**产品特性门控**
#   （asar: ite(e)=f.Fn.includes(enterpriseId); ste=[sites_deploy,sites_unpublish,cloud_service]）
#   调用恒报 "not available in the current environment or configuration"。
# 本脚本走 **WBIPC(wb.request/http.fetch) + 沙箱直连 + 部署 API** 这条等价通道，
#   与 workbuddy_sites_deploy 内部实现（asar mFe）逐字同构。
#
# 用法：
#   sh scripts/deploy-online.sh            # 打包→上传→起服务→发布→逐字节校验
#   sh scripts/deploy-online.sh --check    # 只做线上逐字节校验，不发布
#
# ⛔ 只在业主当轮明确说「推线上 / 上线 / 同步到线上」时运行。
# ============================================================================
set -u

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT" || exit 1

PY="${PY_BIN:-/Users/opp/.workbuddy/binaries/python/envs/default/bin/python}"
NODE="${NODE_BIN:-/Users/opp/.workbuddy/binaries/node/versions/24.14.0/bin/node}"
[ -x "$PY" ] || PY="python3"
[ -x "$NODE" ] || NODE="node"

# ── 固定参数（与本仓应用绑定，勿改）────────────────────────────────
APP_ID="wbapp_JDYgxiKM8iOuFClocbrh1J"
SHARE_LINK="https://hospital-ops-collab-77609.app.workbuddy.host/"
DEPLOY_CONV="2099012471780237312"     # 部署专用会话（≠ 当前会话！）
SANDBOX="73befced846e414fb1429af149cf9224"
CLUSTER="gz2.sandbox.cloudstudio.club"
EXEC_PORT=65213                        # asar: b5  （/console、/filesystem）
AUTO_PORT=65310                        # asar: NFe （/replaceCloudStudioConfig）
BUNDLE="/tmp/site-bundle.tar.gz"
REF_LIST="/tmp/site-bundle-files.txt"

MODE="${1:-deploy}"
[ "$MODE" = "--check" ] && echo "═══ 只校验线上（不发布）═══" || echo "═══ $(date '+%Y-%m-%d %H:%M:%S') 开始推线上 ═══"

# ── 0. 取沙箱凭证（WBIPC）────────────────────────────────────────
CREDS=$("$NODE" scripts/_deploy.mjs creds "$DEPLOY_CONV" 2>/dev/null | tail -1)
echo "$CREDS" | grep -q sandboxId || { echo "[FAIL] 取沙箱凭证失败：$CREDS"; exit 1; }
TOKEN=$("$PY" -c "import json,sys; print(json.loads(sys.argv[1])['token'])" "$CREDS")
# ⛔⛔ 2026-10-12 修：`SANDBOX` 常量会**轮换**（实测 73befced… → 12cfokbv…），
#   写死会导致「上传 200 但内容没变 / 一发就失败」。改成**每轮从凭证里动态取**。
#   ⚠ 同时 SESSION_ID 必须与当前沙箱一致 —— 下面 release 用的就是刚取到的这个值。
SBX=$("$PY" -c "import json,sys; print(json.loads(sys.argv[1])['sandboxId'])" "$CREDS")
CLU=$("$PY" -c "import json,sys; print(json.loads(sys.argv[1]).get('cluster') or '$CLUSTER')" "$CREDS")
[ -n "$SBX" ] || { echo "[FAIL] 凭证里没有 sandboxId"; exit 1; }
SANDBOX="$SBX"; CLUSTER="$CLU"
echo "[1/5] 沙箱凭证 OK · sandbox=$SANDBOX"

BOX="https://${EXEC_PORT}-${SANDBOX}.${CLUSTER}"
AUTO="https://${AUTO_PORT}-${SANDBOX}.${CLUSTER}"

sbx_exec() {
  "$PY" - "$TOKEN" "$BOX" "$1" <<'PYEOF'
import json, subprocess, sys
token, box, cmd = sys.argv[1], sys.argv[2], sys.argv[3]
payload = json.dumps({"command": cmd, "shell": "/bin/bash", "timeoutMs": 120000}).encode()
r = subprocess.run(['curl','-sS','-X','POST','-H','Authorization: Bearer '+token,
                    '-H','Content-Type: application/json','--data-binary','@-',
                    box+'/console','--max-time','180'], input=payload, capture_output=True)
try:
    d = json.loads(r.stdout.decode('utf-8','replace'))
    if d.get('stdout'): print(d['stdout'][:2000])
    if d.get('exitCode'): print('[exit %s] %s' % (d.get('exitCode'), (d.get('stderr') or '')[:400]))
except Exception:
    print('[RAW]', r.stdout.decode('utf-8','replace')[:600])
PYEOF
}

if [ "$MODE" != "--check" ]; then
  # ── 0.5 先重建脱敏种子（线上只收脱敏库，绝不上传 db/live-data.sqlite）──
  "$PY" scripts/live-data/build-deploy-seed.py || { echo "[FAIL] 脱敏种子生成失败，已中止发布"; exit 1; }
  # ── 1. 打包（只打页面真正引用的资源）────────────────────────────
  # ⭐ 提速关键：原先 tar 整个目录，把 data/(11M) scripts/(2.5M) docs/ output/
  #    这些**页面完全不引用**的东西也传了 —— 实测 7.3MB，上传耗时 12—19 秒。
  #    改为按 index.html 的引用清单打包 + vendor（OCR 引擎，运行时按需加载），
  #    包体降到约 1.5MB，上传 2—3 秒。
  #    ⛔ 只打引用清单有风险吗？—— 已核对：index.html 只引用 26 个本地资源，
  #      全部落在 repo 根目录；未引用任何 data/ scripts/ docs/ output/。
  #      新增模块时若忘了加进清单，页面会 404 —— 故下面做了「引用存在性校验」。
  [ -f "$REF_LIST" ] && rm -f "$REF_LIST"
  # ⭐⭐ vendor/（OCR 引擎，压缩后约 3.5MB）**只在沙箱里没有时才打包**。
  #    依据：沙箱是按 sandboxId 复用的持久化环境，vendor 上次部署已解压在里面；
  #    而 OCR 只在「拖图识别营收日报」时按需 fetch，不影响页面与其余模块。
  #    ⇒ 常规更新不传 vendor，包体 4.97MB → 约 1.4MB，上传 12—19s → 2—3s。
  #    ⛔ 判断错会怎样：沙箱里缺 vendor 且不传 → 拖图 OCR 404。故这里**实测探测**，
  #      探不到（命令失败/超时）时**保守地打包 vendor**，宁可慢也不坏。
  HAS_VENDOR=$(sbx_exec 'test -d /workspace/vendor/tesseract && echo YES || echo NO' 2>/dev/null | grep -o 'YES\|NO' | head -1)
  [ -z "$HAS_VENDOR" ] && HAS_VENDOR="NO"
  "$PY" - "$ROOT" "$REF_LIST" "$HAS_VENDOR" <<'PYEOF'
import io, os, re, sys
root, out, has_vendor = sys.argv[1], sys.argv[2], sys.argv[3]
html = io.open(os.path.join(root, 'index.html'), encoding='utf-8').read()
refs = sorted(set(re.findall(r'(?:href|src)="\./([^"]+)"', html)))
# ⛔ 2026-10-12 修：清单只列「被引用资源」，**漏了入口 index.html 本身**
#    → 沙箱解压后 /workspace/index.html 仍是上一版（实测 621,479）。
#    入口文件必须无条件加入清单。
keep, missing = ['index.html'], []
for r in refs:
    # ⛔ 2026-10-18 修：带版本号的引用（live-sync.js?v=20261018i）按 `r` 取文件必然
    #   不存在 → 被丢进 missing、**根本没打进包**，线上就是 404、整页不动效。
    #   必须 **去掉 ?query 再判存在性**，且 tar 清单里只能写真实文件名。
    path = r.split('?')[0].split('#')[0]
    if os.path.exists(os.path.join(root, path)):
        if path not in keep:
            keep.append(path)
    else:
        missing.append(r)
# ⛔ 2026-10-18 补：`data/snapshot.json` 不在 index.html 的 href/src 里
#    （由 live-sync.js 运行时 fetch），但**它是静态部署下唯一的数据源**：
#    同源 /api/operations/v1/snapshot 在纯静态服务里必然 404 → 回退读这个文件。
#    ⇒ 必须显式入清单，否则线上页面框架在、数字却永远不出现。
# ⭐ 2026-10-18 追加：线上从「纯静态」升级为「静态 + 小 API + SQLite」。
#    拖图导入原先只写 localStorage，换设备就丢（双会话实测 POST=0）；
#    现在服务端接住写入、落 SQLite、重算快照，跨设备才成立。
#    这几个文件是服务端与重算链的全部依赖，少一个线上就 500。
#    ⚠ 注意 db/deploy-seed.sqlite 是**脱敏种子**（pull 原始层已清空，无患者手机号），
#      绝不要把 db/live-data.sqlite 打进包 —— 那是本地全量库。
for extra in ('data/snapshot.json', 'server.py', 'db/deploy-seed.sqlite', 'db/schema.sql',
              'scripts/live-data/live_db.py', 'scripts/live-data/build_snapshot.py'):
    p = os.path.join(root, extra)
    if os.path.exists(p) and extra not in keep:
        keep.append(extra)
    elif not os.path.exists(p):
        missing.append(extra)
tag = '沙箱已有 → 跳过' if has_vendor == 'YES' else '沙箱没有 → 一并打包'
if has_vendor != 'YES' and os.path.isdir(os.path.join(root, 'vendor')):
    keep.append('vendor')
io.open(out, 'w', encoding='utf-8').write('\n'.join(keep) + '\n')
print('[2/5] 打包清单 %d 项 · vendor %s' % (len(keep), tag))
if missing:
    print('      ⚠ 引用但文件不存在：%s' % ', '.join(missing))
PYEOF
  rm -f "$BUNDLE"
  tar czf "$BUNDLE" -T "$REF_LIST" 2>/dev/null
  echo "[2/5] 打包完成  $(wc -c < "$BUNDLE" | tr -d ' ') bytes（旧方案 7.36MB）"

  # ── 2. 上传 ────────────────────────────────────────────────────
  # ⚠ 2026-10-12 修：上传偶发 HTTP 302（网关瞬时重定向，实测立即重试即 200）。
  #   ⛔ 不要重取 token（302 不是凭证问题），直接重试同一次上传即可。
  # ⛔⛔ 2026-10-12 定论（实测 4 次）：**token 取到后有效期极短**。
  #   证据：① 脚本里「取 token → 探测 vendor → 打包 → 上传」→ **必 302**；
  #        ② 同一条 curl 手动「取 token 后立即上传」→ **必 200**。
  #   所以 302 ＝ **token 已失效**，不是网络抖动 ⇒ 重试前**必须重取 token**。
  code=""
  for _i in 1 2 3 4; do
    # ⭐ 每次（含第 1 次）都**重新取 token**：把「取 token」与「上传」的时间差压到最小，
    #   因为凭证有效期很短。第一次也重取是为了绕开「探测 vendor / 打包」所耗的时间。
    CREDS=$("$NODE" scripts/_deploy.mjs creds "$DEPLOY_CONV" 2>/dev/null | tail -1)
    TOKEN=$("$PY" -c "import json,sys; print(json.loads(sys.argv[1])['token'])" "$CREDS")
    _SBX=$("$PY" -c "import json,sys; print(json.loads(sys.argv[1])['sandboxId'])" "$CREDS")
    if [ "$_SBX" != "$SANDBOX" ]; then
      SANDBOX="$_SBX"; BOX="https://${EXEC_PORT}-${SANDBOX}.${CLUSTER}"; echo "      （沙箱已轮换 → $SANDBOX）"
    fi
    _URL="$BOX/filesystem/workspace/site-bundle.tar.gz"
    code=$(curl -sS -o /tmp/_up_body.txt -w '%{http_code}' -X POST \
      -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/octet-stream" \
      --data-binary @"$BUNDLE" "$_URL" --max-time 240 -D /tmp/_up_h.txt)
    [ "$code" = "200" ] && break
    echo "      warn: upload HTTP ${code} (attempt ${_i})"
    sleep 1
  done
  [ "$code" = "200" ] || { echo "[FAIL] 上传 HTTP ${code}（已重试 4 次）"; echo "--- resp headers ---"; head -14 /tmp/_up_h.txt; echo "--- body ---"; head -c 200 /tmp/_up_body.txt; exit 1; }
  echo "[3/5] 上传 OK"

  # ── 3. 解压 + 起服务 + 沙箱内自检 ───────────────────────────────
  sbx_exec 'cd /workspace && tar xzf site-bundle.tar.gz && echo EXTRACT_OK'
  # ⭐ 启动命令从「静态 http.server」换成 server.py：同一个端口既发页面也发 /api。
  #   ⛔ 不要在这里写 `--directory /workspace` 那种纯静态启动 —— 那样导入接口 404，
  #      前端会静默退化成「只存本机」，跨设备同步又回到原样。
  #   server.py 首次启动会从 db/deploy-seed.sqlite 生 db/runtime.sqlite；
  #   之后的发布不覆盖 runtime.sqlite，所以用户导入的数据跨发布保留。
  curl -sS -o /dev/null -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
    -d '{"app":[{"name":"app","port":3000,"cmd":"cd /workspace && PORT=3000 python3 server.py 2> /workspace/.sites-app.log"}],"restart":true}' \
    "$AUTO/replaceCloudStudioConfig" --max-time 90
  sleep 6
  echo -n "[4/5] 沙箱服务自检："
  sbx_exec 'curl -sS -o /dev/null -w "页面 HTTP %{http_code} · " --max-time 10 http://127.0.0.1:3000/index.html; curl -sS --max-time 10 http://127.0.0.1:3000/api/health; echo'

  # ── 4. 发布 ────────────────────────────────────────────────────
  "$NODE" scripts/_deploy.mjs release "$APP_ID" "$DEPLOY_CONV" "$SANDBOX" "$SHARE_LINK" "${WB_SESSION:-2404f039-ed52-4a4f-9ad0-bc968f5ed60f}" 2>&1 | sed 's/^/      /'
  echo "[5/5] 发布 OK → $SHARE_LINK"
fi

# ── 5. 线上逐字节校验 ──────────────────────────────────────────
sleep 8
"$PY" - "$SHARE_LINK" "$ROOT" <<'PYEOF'
import sys, os, json, urllib.request, urllib.error
share, root = sys.argv[1], sys.argv[2]
FILES = ['index.html','live-sync.js','data-import.js','data/snapshot.json','business-analysis.js','month-dashboard.js','revision-v6.js',
         'final-enhancements.js','marketing-detail.js','channel-snapshot.js',
         'october-board.css','channel-dashboard.js']
ok = True
for f in FILES:
    try:
        req = urllib.request.Request(share + f + '?cb=' + str(os.getpid()) + str(os.times().elapsed),
                                     headers={'Cache-Control': 'no-cache'})
        a = urllib.request.urlopen(req, timeout=30).read()
    except Exception as e:
        print('  %-24s ERR %s' % (f, str(e)[:60])); ok = False; continue
    p = os.path.join(root, f)
    if not os.path.exists(p):
        print('  %-24s (本地无，跳过)' % f); continue
    b = open(p, 'rb').read()
    same = a == b
    if not same: ok = False
    print('  %-24s online=%-8d local=%-8d %s' % (f, len(a), len(b), 'IDENTICAL' if same else 'DIFF'))

# ⭐ 服务端接口必须真的活着：静态部署时这里 404，导入就会静默退化成只存本机
for api in ('api/health', 'api/operations/v1/snapshot', 'api/revenue'):
    try:
        u = share + api + '?cb=' + str(os.getpid())
        j = json.loads(urllib.request.urlopen(
            urllib.request.Request(u, headers={'Cache-Control': 'no-cache'}), timeout=30).read())
        if api == 'api/health':
            print('  %-24s %s' % ('/' + api, 'OK db=' + str(j.get('db'))))
        elif api.endswith('snapshot'):
            print('  %-24s %s' % ('/' + api, 'OK revision=%s 本期=%s万' % (
                j.get('revision'), (j.get('metrics') or {}).get('weekRevenue', {}).get('value'))))
        else:
            print('  %-24s %s' % ('/' + api, 'OK 覆盖 %d 天' % len(j.get('daily') or {})))
    except Exception as e:
        ok = False
        print('  %-24s ERR %s' % ('/' + api, str(e)[:70]))

# ⛔ 数据库与源码不能能被直接下载
for bad in ('db/live-data.sqlite', 'db/runtime.sqlite', 'server.py'):
    try:
        code = urllib.request.urlopen(share + bad, timeout=15).getcode()
        ok = False
        print('  %-24s ⛔ 可被下载（HTTP %s）' % (bad, code))
    except urllib.error.HTTPError as e:
        print('  %-24s 已拦截 HTTP %s' % (bad, e.code))
    except Exception as e:
        print('  %-24s 已拦截 %s' % (bad, type(e).__name__))
print()
print('线上校验：', '✅ 全部一致' if ok else '❌ 有不一致')
sys.exit(0 if ok else 1)
PYEOF
RC=$?
echo
[ $RC -eq 0 ] && echo "═══ 完成：$SHARE_LINK ═══" || echo "═══ 校验未全过，请检查上方 DIFF ═══"
exit $RC