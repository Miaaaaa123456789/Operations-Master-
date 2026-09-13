#!/usr/bin/env node
/**
 * kdocs-ingest.js — 医院经营协同看板 · 每日 09:00 数据入口
 *
 * 流程（与硬约束 1:1 对应）：
 *   1. 从金山文档抓 5 个部门 sheet 的关键格
 *   2. 算 8 项指纹（admit / outpatient / revenueWan / therapyFeeWan /
 *                  therapyVisits / followup / psychVisits / psychRevenue）
 *   3. 比对 data/ops-dashboard-snapshot.json
 *      - 指纹不变 → 只改 periodLabel（表头年月）；不刷洞察；不推企微
 *      - 指纹变化 → 重写 summary / mainNumbers / periodLabel；写快照；
 *                   （后续）按授权发企业微信
 *
 * 运行：
 *   node scripts/kdocs-ingest.js                 # 标准执行
 *   node scripts/kdocs-ingest.js --discover      # 仅打印 5 个 sheet 的结构，不写快照
 *   node scripts/kdocs-ingest.js --dry-run       # 抓 + 算指纹 + 比对，不写文件
 *
 * 依赖：kdocs-cli v2.6.13+（由 ~/.workbuddy/skills/kdocs 安装）
 *       已通过 `kdocs-cli auth login` 或 `auth set-token` 完成认证
 */

'use strict';

const { execFileSync } = require('child_process');
const fs = require('fs');
const path = require('path');
const os = require('os');

// ─── kdocs-cli 路径解析（绝对路径优先，避免依赖 PATH） ──────────────────

function resolveKdocsCli() {
  const candidates = [
    process.env.KDOCS_CLI,
    path.join(os.homedir(), '.local', 'bin', 'kdocs-cli'),
    '/usr/local/bin/kdocs-cli',
    '/opt/homebrew/bin/kdocs-cli',
  ].filter(Boolean);
  for (const p of candidates) { try { fs.accessSync(p, fs.constants.X_OK); return p; } catch (_) {} }
  return 'kdocs-cli'; // 兜底：靠 PATH 解析（自动化 prompt 中会先 export PATH）
}

// ─── 配置 ─────────────────────────────────────────────────────────────────

const REPO_ROOT = path.resolve(__dirname, '..');
const SNAPSHOT_PATH = path.join(REPO_ROOT, 'data', 'ops-dashboard-snapshot.json');
const RAW_DIR = path.join(REPO_ROOT, 'data', 'raw');
const KDOCS_CLI = resolveKdocsCli();

const KDOCS_URL = 'https://www.kdocs.cn/l/cbwp2cvTiFyK';

// 5 个部门 sheet 的标题（必须与金山表 sheet 名精确匹配）
const SHEET_NAMES = {
  doctor:     '医生组',
  nursing:    '护理组',
  psychology: '心理咨询组',
  service:    '客服服务部',
  marketing:  '营销中心',
};

// 8 项指纹字段 → 在金山表里的精确 (row, col) 位置
// 由 --discover 模式跑出来的真实表头确认（每张表的 r1 是指标表头，r2 是本期数值）
const FINGERPRINT_FIELDS = [
  { key: 'admit',         sheet: 'doctor',     row: 2, col: 1 },  // 医生组 r2 c1  本周入院人数
  { key: 'outpatient',    sheet: 'doctor',     row: 2, col: 3 },  // 医生组 r2 c3  本周门诊人数
  { key: 'revenueWan',    sheet: 'doctor',     row: 2, col: 7 },  // 医生组 r2 c7  总收入(万)
  { key: 'therapyFeeWan', sheet: 'doctor',     row: 2, col: 5 },  // 医生组 r2 c5  物理治疗费用(万)
  { key: 'therapyVisits', sheet: 'nursing',    row: 2, col: 1 },  // 护理组 r2 c1  物理治疗人数
  { key: 'followup',      sheet: 'service',    row: 2, col: 1 },  // 客服服务部 r2 c1  随访人数
  { key: 'psychVisits',   sheet: 'psychology', row: 2, col: 1 },  // 心理咨询组 r2 c1  个体咨询人数
  { key: 'psychRevenue',  sheet: 'psychology', row: 2, col: 7 },  // 心理咨询组 r2 c7  总收入(元)
];

// ─── CLI 封装 ─────────────────────────────────────────────────────────────

function kdocs(...args) {
  // kdocs-cli <service> <action> k=v k=v ...
  const out = execFileSync(KDOCS_CLI, args, { encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] });
  return JSON.parse(out);
}

function call(tool, params = {}) {
  return kdocs('call', tool, JSON.stringify(params));
}

// ─── 步骤 1: 取文件元 + sheet 列表 ─────────────────────────────────────────

function listSheets() {
  const meta = call('sheet.get_sheets_info', { url: KDOCS_URL });
  // 真实结构：{ code:0, data:{ detail:{ sheetsInfo:[{sheetId, sheetName, rowFrom, rowTo, colFrom, colTo}, ...] } } }
  const sheetsInfo = (meta.data && meta.data.detail && meta.data.detail.sheetsInfo) || [];
  return { fileId: meta.file_id || (meta.data && meta.data.file_id), sheets: sheetsInfo };
}

function pickDeptSheet(sheets, sheetName) {
  return sheets.find(s => s.sheetName === sheetName) || sheets.find(s => s.sheetName && s.sheetName.includes(sheetName)) || null;
}

// ─── 步骤 2: 读每个部门 sheet 的内容（足够覆盖指纹 + 核验项）─────────────

function readSheet(url, sheetId, range) {
  const r = call('sheet.get_range_data', { url, worksheet_id: sheetId, range });
  // 真实结构：data.detail.rangeData = [ { originRow, originCol, cellText, originalCellValue, understandableType:{type,value}, colFrom, colTo, ... }, ... ]
  return (r.data && r.data.detail && r.data.detail.rangeData) || (r.detail && r.detail.rangeData) || [];
}

function flattenCells(cells) {
  // 每个 cell 对象 → { r, c, text, value, type }
  return cells.map(x => {
    const text = x.cellText || (x.understandableType && x.understandableType.value) || '';
    const raw  = x.originalCellValue !== undefined ? x.originalCellValue : text;
    const num  = typeof raw === 'number' ? raw : (parseFloat(raw));
    return {
      r: x.originRow,
      c: x.originCol,
      text: String(text),
      raw: String(raw),
      value: isNaN(num) ? null : num,
      type: x.understandableType && x.understandableType.type,
    };
  }).filter(x => x.r !== undefined && x.c !== undefined && (x.text !== '' || x.value !== null));
}

// ─── 步骤 3: 算 8 项指纹 ───────────────────────────────────────────────────

function findRowWith(cells, label) {
  // 在 0..2 列找含 label 的行号；优先精确匹配，其次包含
  for (const cell of cells) {
    if (cell.c > 2) continue;
    if (cell.text === label) return cell.r;
  }
  for (const cell of cells) {
    if (cell.c > 2) continue;
    if (cell.text.includes(label)) return cell.r;
  }
  return -1;
}

function rowNumbers(cells, rowIdx) {
  return cells
    .filter(x => x.r === rowIdx && x.c >= 2)
    .map(x => x.value)
    .filter(v => v !== null && isFinite(v));
}

function computeFingerprint(sheetDataByDept) {
  // sheetDataByDept: { doctor:{cells}, nursing:{cells}, psychology:{cells}, service:{cells}, marketing:{cells} }
  const fp = {};
  for (const f of FINGERPRINT_FIELDS) {
    const deptSheet = sheetDataByDept[f.sheet];
    if (!deptSheet) { fp[f.key] = null; continue; }
    const hit = deptSheet.cells.find(c => c.r === f.row && c.c === f.col);
    fp[f.key] = (hit && hit.value !== null && hit.value !== undefined) ? hit.value : null;
  }
  return fp;
}

// ─── 步骤 4: 比对 + 写快照 ─────────────────────────────────────────────────

function loadSnapshot() {
  try { return JSON.parse(fs.readFileSync(SNAPSHOT_PATH, 'utf8')); }
  catch (e) { return null; }
}

function saveSnapshot(snap) {
  fs.mkdirSync(path.dirname(SNAPSHOT_PATH), { recursive: true });
  fs.writeFileSync(SNAPSHOT_PATH, JSON.stringify(snap, null, 2) + '\n');
}

function fingerprintEqual(a, b) {
  if (!a || !b) return false;
  for (const f of FINGERPRINT_FIELDS) {
    if (Math.abs((a[f.key] || 0) - (b[f.key] || 0)) > 1e-6) return false;
  }
  return true;
}

function periodLabelFromSnapshot(prevSnap) {
  const m = new Date();
  return `数据更新至 ${m.getFullYear()}年${m.getMonth() + 1}月${m.getDate()}日`;
}

function buildSnapshotFromFingerprint(fp, prevSnap) {
  const periodLabel = periodLabelFromSnapshot(prevSnap);
  // 这里写最简化的陈述句；真实场景里"先修复...再..."这种业务判断
  // 必须由人工 / 后续 AI 步骤注入——本脚本只负责"数字+环比"层
  const summary =
    `总收入 ${fp.revenueWan || '—'} 万元，入院 ${fp.admit ?? '—'} 人，` +
    `门诊 ${fp.outpatient ?? '—'} 人，环比见信号详情。`;
  return {
    fingerprint: fp,
    narrativeMain: {
      admit: fp.admit || null,
      outpatient: fp.outpatient || null,
      revenueWan: fp.revenueWan || null,
    },
    periodLabel,
    snapshotAt: new Date().toISOString(),
    source: 'kdocs/cbwp2cvTiFyK',
    auth: prevSnap && prevSnap.auth ? prevSnap.auth : { kdocs: false, wecom: false },
    summary,
    mainNumbers: [
      { label: '总收入（万）', value: String(fp.revenueWan ?? '—'), delta: '—', deltaColor: 'rgba(255,255,255,.85)' },
      { label: '入院（人）',   value: String(fp.admit ?? '—'),         delta: '—', deltaColor: 'rgba(255,255,255,.85)' },
      { label: '门诊（人）',   value: String(fp.outpatient ?? '—'),    delta: '—', deltaColor: 'rgba(255,255,255,.85)' },
    ],
    wecomTemplate: prevSnap && prevSnap.wecomTemplate || '',
  };
}

// ─── Main ─────────────────────────────────────────────────────────────────

function main() {
  const argv = process.argv.slice(2);
  const discover = argv.includes('--discover');
  const dryRun = argv.includes('--dry-run');

  console.log('🔐 检查认证 …');
  const status = JSON.parse(execFileSync(KDOCS_CLI, ['auth', 'status'], { encoding: 'utf8' }));
  if (!status.authenticated) {
    console.error('❌ 未认证。先跑：`kdocs-cli auth login` 或 `kdocs-cli auth set-token <TOKEN>`');
    process.exit(2);
  }

  console.log('📄 读 sheet 列表 …');
  const { sheets } = listSheets();
  console.log(`  → 共 ${sheets.length} 个 sheet：`);
  sheets.forEach(s => console.log(`    - ${s.sheetName} (id=${s.sheetId}, 范围 ${s.rowFrom}-${s.rowTo}行 × ${s.colFrom}-${s.colTo}列)`));

  const sheetDataByDept = {};
  for (const [enKey, sheetName] of Object.entries(SHEET_NAMES)) {
    const s = pickDeptSheet(sheets, sheetName);
    if (!s) {
      console.warn(`  ⚠ 未匹配到「${sheetName}」sheet，跳过`);
      sheetDataByDept[enKey] = { cells: [] };
      continue;
    }
    // 用 get_sheets_info 返回的实际范围 + 2 行 buffer 抓全表
    const rowTo = (s.rowTo || 40) + 2;
    const colTo = (s.colTo || 25) + 2;
    const rows = readSheet(KDOCS_URL, s.sheetId, {
      rowFrom: 0, rowTo, colFrom: 0, colTo,
    });
    const cells = flattenCells(rows);
    sheetDataByDept[enKey] = { sheetId: s.sheetId, sheetName: s.sheetName, cells, rows };
    console.log(`  ✓ ${sheetName}: ${cells.length} 个非空单元格 (${s.rowTo+1}行 × ${s.colTo+1}列)`);
  }

  if (discover) {
    // 落盘原始抓取 + 退出，方便后续人工补 fingerprint_cells
    fs.mkdirSync(RAW_DIR, { recursive: true });
    const stamp = new Date().toISOString().replace(/[:.]/g, '-');
    const dumpPath = path.join(RAW_DIR, `discover-${stamp}.json`);
    fs.writeFileSync(dumpPath, JSON.stringify({
      fetchedAt: new Date().toISOString(),
      url: KDOCS_URL,
      sheets: sheetDataByDept,
    }, null, 2));
    console.log(`\n📦 原始抓取已保存到 ${dumpPath}`);
    console.log('  下一步：打开该文件，根据表头文本确认 8 项指纹字段各在哪个 (row, col)，');
    console.log('         然后用硬编码替换 FINGERPRINT_FIELDS 里的取数策略。');
    process.exit(0);
  }

  console.log('🔢 计算 8 项指纹 …');
  const fp = computeFingerprint(sheetDataByDept);
  for (const [k, v] of Object.entries(fp)) {
    console.log(`  ${k.padEnd(15)} = ${v === null ? '—' : v}`);
  }

  const prev = loadSnapshot();
  const same = prev && fingerprintEqual(prev.fingerprint, fp);

  if (same) {
    console.log('\n✅ 指纹未变 → 只更新表头年月，不改洞察，不推企微。');
    if (!dryRun) {
      const next = {
        ...prev,
        periodLabel: periodLabelFromSnapshot(prev),
        snapshotAt: new Date().toISOString(),
      };
      saveSnapshot(next);
      console.log(`  → periodLabel = ${next.periodLabel}`);
    }
  } else {
    console.log('\n⚠️  指纹变化 → 重写 summary / mainNumbers / periodLabel，更新快照。');
    const next = buildSnapshotFromFingerprint(fp, prev);
    console.log(`  summary: ${next.summary}`);
    if (!dryRun) {
      saveSnapshot(next);
      console.log(`  → 已写 ${SNAPSHOT_PATH}`);
      // 此处后续接入企业微信：if (next.auth.wecom) { /* 推群 */ }
    }
  }
}

try { main(); }
catch (e) {
  console.error('💥 运行失败：', e.message);
  if (process.env.DEBUG) console.error(e.stack);
  process.exit(1);
}