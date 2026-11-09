/* ============================================================================
   看板数据导入与同步
   ----------------------------------------------------------------------------
   真实链路：解析（CSV / XLSX / 粘贴文本）→ 逐行校验 → 重算 → 全站重绘 + 时间戳同步
   · 图片：显示预览缩略图；浏览器端离线无法可靠 OCR，数值在「识别结果」里确认
   · 数据落在 localStorage（叠加在种子数据之上），刷新后保持；可导出为源码数据块
   · 无冲突时确认按钮立即可用 —— 不再出现「必须先解决冲突」
   ========================================================================== */
(function () {
  'use strict';

  /* ============================ 常量 ============================ */
  var LS_DAILY = 'ops.rev.daily.v1';   // 逐日营收覆盖层
  var LS_META = 'ops.rev.meta.v1';    // 导入元信息
  var LS_SNAP = 'ops.rev.snapshot.v1';// 导入前快照（保留最近一次）
  var LS_PENDING = 'ops.rev.pending.v1'; // 已在本机导入、但还没确认写进服务端的日期
  /* ⭐ 2026-10-18：跨设备同步的落点。
     原先导入只写 localStorage → 换设备/换浏览器/清缓存全丢（双会话实测 POST 数为 0）。
     现在真身在服务端 SQLite，这里只是它在本页的镜像；服务端不在时（纯静态部署）
     整个逻辑自动退化为原来那套本地覆盖层，不会白屏、不会报错。 */
  var REMOTE_DAILY = {};

  var MONTH_TARGET = 260;             // 月度营收目标（万元）—— 2026-10 沿用 9 月目标（业主 2026-10-06 确认）
  /* ⭐⭐ 本期（观察期）＝**两周窗口**（业主 2026-10-06 定）。
     单周口径下「本期」＝10.5—10.11、实际只 1 天数据；业主指定所有「本期」时间戳与洞察
     一律按 **9.28—10.11** 算。改这里即改全站的本期区间（与 september-revenue-data.js
     的 PERIOD_WEEKS 必须一致，两处一起改）。 */
  var PERIOD_WEEKS = 1;   // 2026-10-18：本期改为自然周 10.12—10.18
  /* ⚠ MONTH_DAYS 已改为按结算月推导（见下方 SETTLED_MONTH 处）：
     原写死 30，10 月切过来后时间进度会算成 5/30=16.7%（正确应为 5/31=16.1%）、
     「剩余 25 天」也会错成 26 天。 */

  /* ⭐ 写入数据后重算「数据窗口」。
     为什么必须有这一步：上面那批常量是**求值一次就固定**的。用户在页面打开期间拖入
     新一天的数据时，若不自增窗口，新数据会落在 [WEEK_START, WEEK_END] 之外，
     面板仍然显示旧数字 → 用户再次误判为「没留存」。
     这里把「本周 / 上周 / 当月 / 截止日」整体重新对齐到「包含最新数据的那一周」，
     并向后延长区间以覆盖到最新数据日。窗口只会前进、不会回退。 */
  function refreshWindow() {
    /* ⚠ 与初始化一致：有 PERIOD_ANCHOR 时窗口锁死在锚点周，
       否则营收日报推到 10.20 会把本期撑成 10.12—10.20（9 天），
       医生卡的出院数会被算成 22（含 10.19/10.20 各 2 人）。 */
    var last = PERIOD_ANCHOR || _probeLastDay(TODAY);
    var a = new Date(+last.slice(0, 4), +last.slice(5, 7) - 1, +last.slice(8));
    var mon = _monOf(a), sun = new Date(mon.getFullYear(), mon.getMonth(), mon.getDate() + 6);
    /* ⭐ 本期＝两周窗口：起点＝数据末日所在周的周一往前推 (PERIOD_WEEKS-1) 周；
       上一期＝紧邻其前的等长完整期。10.5（周一）→ 本期 9.28—10.11、上一期 9.14—9.27。 */
    var pStart = new Date(mon.getFullYear(), mon.getMonth(), mon.getDate() - 7 * (PERIOD_WEEKS - 1));
    var lwm = new Date(mon.getFullYear(), mon.getMonth(), mon.getDate() - 7 * PERIOD_WEEKS - 7);
    var lws = new Date(mon.getFullYear(), mon.getMonth(), mon.getDate() - 8);
    var ws = _d2s(pStart), we = _d2s(sun);
    if (ws > WEEK_START) {              // 只在数据推进到更晚的期时前移
      WEEK_START = ws; WEEK_END = we;
      LW_START = _d2s(lwm); LW_END = _d2s(lws);
    }
    if (!PERIOD_ANCHOR && last > WEEK_END) WEEK_END = last;   // 本期内的新数据：把区间向右延到最新数据日
    /* ⚠ 月窗口仍**不随数据前移** —— 但原因已变：
       2026-10-06 起结算月显式设为 2026-10（业主决定主面板切 10 月），
       窗口由 SETTLED_MONTH 推导，**按定义**就不该跟着数据漂。
       若改成跟着 last 走，月末跨月时会瞬间把新月份的天数算进来。
       ⚠ 切下个月时，改 SETTLED_MONTH 一处即可（下面 MONTH_FROM/TO/DAYS 全会跟着变）。 */
    if (last > SOURCE_CUTOFF) SOURCE_CUTOFF = last;
    return last;
  }
  var DOW = ['周日', '周一', '周二', '周三', '周四', '周五', '周六'];

  /* ============================ 种子数据 ============================
     逐日营业日报，单位：元 / 人
     数组含义：[门诊收入, 在院收入, 初诊, 复诊, 在院, 入院, 出院]
     · 收入：9.1—9.14 取自 data/daily-sales/2026-09.csv；9.15 由 9.16 环比反推；
             9.16—9.30 取自业主营收日报截图（含当月累计收入交叉校验）
     · 人数：9.1—9.14 取自同一 CSV；9.18—9.24 取自营收日报截图逐列识别；
             9.15—9.17 截图无此行，人数记 null（不参与人数环比）
     · 校验：9.1—9.30 累计 = 2,271,746.38 元（227.17 万），与源表「当月累计收入」一致
     ================================================================ */
  var SEED = {
    '2026-09-01': [8329.46, 13695.01, 4, 13, 28, 2, 0],
    '2026-09-02': [16747.27, 62605.0, 3, 15, 27, 1, 2],
    '2026-09-03': [4710.35, 35411.99, 0, 14, 25, 0, 2],
    '2026-09-04': [31464.5, 40703.93, 8, 24, 29, 6, 2],
    '2026-09-05': [15041.96, 39769.7, 4, 30, 31, 2, 0],
    '2026-09-06': [140116.7, 43682.69, 9, 92, 30, 3, 4],
    '2026-09-07': [20267.31, 39148.42, 3, 16, 30, 4, 4],
    '2026-09-08': [21632.61, 36448.39, 3, 20, 30, 1, 1],
    '2026-09-09': [17044.52, 41666.05, 3, 12, 29, 1, 2],
    '2026-09-10': [10042.88, 36522.53, 1, 12, 28, 0, 1],
    '2026-09-11': [9814.03, 38027.06, 3, 17, 30, 2, 0],
    '2026-09-12': [18029.88, 33831.37, 4, 17, 30, 0, 0],
    '2026-09-13': [133002.16, 31013.81, 11, 108, 27, 4, 7],
    '2026-09-14': [20100.68, 15521.66, 3, 14, 24, 1, 4],
    '2026-09-15': [34846.27, 43388.86, 8, 10, 25, 1, 0],
    '2026-09-16': [13958.85, 28288.75, 2, 13, 25, 0, 1],
    '2026-09-17': [34398.72, 28935.61, 7, 13, 26, 1, 0],
    '2026-09-18': [40570.2, 32821.31, 3, 26, 25, 2, 3],
    '2026-09-19': [99908.85, 37754.86, 7, 79, 28, 5, 2],
    '2026-09-20': [27228.16, 33779.66, 6, 17, 27, 2, 3],
    '2026-09-21': [22568.92, 30721.41, 3, 17, 26, 1, 2],
    '2026-09-22': [25087.04, 30216.77, 6, 13, 26, 2, 2],
    '2026-09-23': [25904.97, 36553.99, 2, 7, 28, 3, 1],
    '2026-09-24': [38082.09, 39383.78, 6, 33, 30, 4, 2],
    '2026-09-25': [69642.38, 31545.11, 3, 51, 31, 3, 2],
    '2026-09-26': [111055.54, 45821.53, 5, 63, 34, 4, 1],
    '2026-09-27': [65135.53, 24151.31, 5, 51, 33, 3, 4],
    '2026-09-28': [34390.08, 67632.02, 5, 17, 32, 2, 3],
    '2026-09-29': [30504.20, 36850.80, 3, 12, 31, 1, 2],
    '2026-09-30': [27460.37, 48766.52, 5, 24, 34, 4, 1],
    /* ⭐ 10 月营收日报（业主 2026-10-05 提供 10.1—10.4，取数含心理科）。
       ⚠⚠ 2026-10-05 更正 10.1：此前存 [77820.76, 8152.62]（＝8.60 万）**是误读**。
       那两个数实为源表「门诊环比」「在院环比」两列的**差额**，被当成了当日归属额：
         门诊 105281.13 − 27460.37(9.30 门诊) = 77820.76
         在院  56919.14 − 48766.52(9.30 在院) =  8152.62
       二者之和 85,973.38 恰好＝毛额 162,200.27 − 9.30 合计 76,226.89，
       看起来像「跨期分摊」，实为巧合误读。
       ⇒ 铁证：源表 10.2 的「门诊环比 -58841.32」＝ 46439.81 − **105281.13**（10.1 全额），
         若 10.1 当日真是 77820.76，该环比应等于 −31380.95。故源表一直是**全额**口径。
       ⇒ **源表 10.1 当日收入合计就是 162,200.27**，且源表自身「门诊＋在院＝当日合计」成立，
         **无需任何跨期分摊**。现按源表原值存储。
       [门诊, 在院, 初诊, 复诊, 在院, 入院, 出院] ← 出院＝出院初次 ＋ 出院多次 */
    '2026-10-01': [105281.13, 56919.14, 7, 50, 40, 7, 1],
    '2026-10-02': [46439.81, 58004.60, 1, 45, 42, 3, 1],
    '2026-10-03': [9030.53, 52909.64, 1, 10, 42, 1, 1],
    '2026-10-04': [16872.55, 30229.12, 0, 16, 39, 0, 3],
    '2026-10-05': [8510.61, 62256.06, 1, 14, 37, 0, 2],
    /* ⭐ 2026-10-06（业主 2026-10-07 提供，取数含心理科）。
       ✅ 三项勾稽全通过：门诊 82,599.70 ＋ 在院 42,475.88 ＝ 当日合计 125,075.58；
         当月累计 446,453.19 ＋ 125,075.58 ＝ 571,528.77；
         在院递推 37 ＋ 入院 1 − 出院 5 ＝ 33。
       ⚠ 出院列存**初次＋多次**合计（源表分两列，本仓 SEED 只有一列）：2 ＋ 3 ＝ 5。 */
    '2026-10-06': [82599.70, 42475.88, 5, 65, 33, 1, 5],
    /* ⭐ 2026-10-07（业主 2026-10-08 提供，取数含心理科）。
       ✅ 四项勾稽全通过：门诊 111,519.00 ＋ 在院 46,419.12 ＝ 当日合计 157,938.12；
         当月累计 571,528.77 ＋ 157,938.12 ＝ 729,466.89；
         在院递推 33 ＋ 入院 4 − 出院 6 ＝ 31；
         环比列互证：门诊 111,519.00 − 82,599.70(10.6) = 28,919.30 ✓
                     在院  46,419.12 − 42,475.88(10.6) =  3,943.24 ✓
       ⚠ 出院列存**初次＋多次**合计（源表分两列，本仓 SEED 只有一列）：4 ＋ 2 ＝ 6。
       ⚠ 源表「门诊收入」该格写的是 `111519`（无小数），按 111519.00 存储。 */
    '2026-10-07': [111519.00, 46419.12, 7, 57, 31, 4, 6],
    /* ⭐ 2026-10-08 / 2026-10-09（业主 2026-10-10 提供实拍图，取数含心理科）。
       ✅ 两日**五项勾稽全部通过**（门诊＋在院＝当日合计／上月累计＋当日＝本月累计／
          在院递推／门诊环比／在院环比，逐项与源表列一致）：
          · 10.8：2,380.13＋29,596.95＝31,977.08；累计 729,466.89＋31,977.08＝761,443.97；
                  在院 31＋0−2＝29；门诊环比 −109,138.87；在院环比 −16,822.17
          · 10.9：8,186.33＋37,342.64＝45,528.97；累计 761,443.97＋45,528.97＝806,972.94；
                  在院 29＋0−0＝29；门诊环比 ＋5,806.20；在院环比 ＋7,745.69
       ⚠ 出院列＝源表「出院初次 ＋ 出院多次」之和：10.8 = 2＋0 = 2；10.9 = 0＋0 = **0**
         （10.9 当日无人出院，是**真实 0**，不是缺值/未读）。
       ⚠ 10.8 当日合计仅 3.20 万（门诊 2,380.13 极低），是真实低点，非缺数。 */
    '2026-10-08': [2380.13, 29596.95, 4, 19, 29, 0, 2],
    '2026-10-09': [8186.33, 37342.64, 4, 10, 29, 0, 0],
    /* ⭐ 2026-10-10（业主 2026-10-11 提供实拍图，取数含心理科）。
       ✅ 五项勾稽全部通过，逐项与源表列一致：
          ① 门诊 19,504.73＋在院 37,290.07＝当日合计 56,794.80
          ② 上月累计 806,972.94＋56,794.80＝本月累计 863,767.74
          ③ 在院递推：10.9 在院 29＋入院 1−出院 0＝30
          ④ 门诊环比 ＋11,318.40（8,186.33 → 19,504.73）
          ⑤ 在院环比 −52.57（37,342.64 → 37,290.07）
       ⚠ 出院列＝「出院初次 0＋出院多次 0」＝**真实 0**（当日无人出院），不是缺值。
       ⚠ 10.10 当日合计 5.68 万，门诊回到 1.95 万（10.8/10.9 连续两日偏低后回升）。 */
    '2026-10-10': [19504.73, 37290.07, 5, 25, 30, 1, 0],
    /* ⭐ 2026-10-11（业主 2026-10-13 提供实拍图，取数含心理科）。
       ✅ 五项勾稽全部通过，逐项与源表列一致：
          ① 门诊 126,900.10＋在院 34,451.41＝当日合计 161,351.51
          ② 上月累计 863,767.74＋161,351.51＝本月累计 1,025,119.25
          ③ 在院递推：10.10 在院 30＋入院 5−出院 4＝31
          ④ 门诊环比 ＋107,395.37（19,504.73 → 126,900.10）
          ⑤ 在院环比 −2,838.66（37,290.07 → 34,451.41）
       ⚠ 出院列＝「出院初次 3＋出院多次 1」＝4。
       ⚠ 源表「门诊收入」格写的是 `126900.1`（小数位被列宽截断），
         按 126,900.10 存储 —— 由 10.12 门诊环比 −110,910.32 反推确证。
       ⚠ 10.11 当日合计 16.14 万，为 10 月单日最高（门诊 12.69 万放量）。 */
    '2026-10-11': [126900.10, 34451.41, 11, 81, 31, 5, 4],
    /* ⭐ 2026-10-12（同上）。
       ✅ 五项勾稽全部通过：
          ① 门诊 15,989.78＋在院 34,554.98＝当日合计 50,544.76
          ② 上月累计 1,025,119.25＋50,544.76＝本月累计 1,075,664.01
          ③ 在院递推：10.11 在院 31＋入院 3−出院 2＝32
          ④ 门诊环比 −110,910.32（126,900.10 → 15,989.78）
          ⑤ 在院环比 ＋103.57（34,451.41 → 34,554.98）
       ⚠ 出院列＝「出院初次 0＋出院多次 2」＝2。
       ⚠ 源表「星期」格为「—」（未填），按日期推算为周一（不影响统计）。 */
    '2026-10-12': [15989.78, 34554.98, 1, 19, 32, 3, 2],
    /* ⭐ 2026-10-13（业主 2026-10-15 提供实拍图，取数含心理科）。
       ✅ 五项勾稽全部通过，逐项与源表列一致：
          ① 门诊 25,292.71＋在院 37,283.02＝当日合计 62,575.73
          ② 上月累计 1,075,664.01＋62,575.73＝本月累计 1,138,239.74
          ③ 在院递推：10.12 在院 32＋入院 1−出院 1＝32
          ④ 门诊环比 ＋9,302.93（15,989.78 → 25,292.71）
          ⑤ 在院环比 ＋2,728.04（34,554.98 → 37,283.02）
       ⚠ 出院列＝「出院初次 1＋出院多次 0」＝1。
       ⚠ 源表「星期」格为「二」（周二）。 */
    '2026-10-13': [25292.71, 37283.02, 6, 12, 32, 1, 1],
    /* ⭐ 2026-10-14（同上）。
       ✅ 五项勾稽全部通过：
          ① 门诊 55,741.34＋在院 41,495.24＝当日合计 97,236.58
          ② 上月累计 1,138,239.74＋97,236.58＝本月累计 1,235,476.32
          ③ 在院递推：10.13 在院 32＋入院 3−出院 3＝32
          ④ 门诊环比 ＋30,448.63（25,292.71 → 55,741.34）
          ⑤ 在院环比 ＋4,212.22（37,283.02 → 41,495.24）
       ⚠ 出院列＝「出院初次 3＋出院多次 0」＝3。
       ⚠ 10.14 当日合计 9.72 万、门诊 5.57 万，均创 10 月次高（仅次于 10.1 的 16.22 万）。 */
    '2026-10-14': [55741.34, 41495.24, 12, 18, 32, 3, 3],
    /* ⭐ 2026-10-15 — 10-17（业主 2026-10-18 提供营收日报截图，取数含心理科）。
       ✅ 逐日「门诊＋在院＝当日合计」与「当月累计」勾稽通过。
       ⚠ 源表 10.17「当月累计」1,397,789.29 与逐日「当日合计」加总 1,397,778.29
         相差 11.00 元；按契约以逐日事实为准，累计列登记待核，不静默抹平。
       ⚠ 出院列＝出院初次＋出院多次。 */
    '2026-10-15': [15606.47, 34949.26, 3, 13, 31, 3, 4],
    '2026-10-16': [16889.99, 40612.27, 5, 12, 34, 3, 0],
    '2026-10-17': [15455.42, 38788.56, 4, 18, 32, 0, 2],
    /* ⭐ 2026-10-18 — 10-20（业主 2026-10-22 提供营收日报截图）。
       ⚠ 这三条的缺失，正是「财务经营分析 / 十月经营板还停在 10.17」的唯一原因：
         本文件是 OPS_REVENUE 的**种子层**，SEED 到哪天、SEED_REVENUE_DATA.updatedThrough
         就到哪天，与 data/snapshot.json 里已补的三天无关。
       ✅ 与 db/live-data.sqlite 的 fact（source_id=revenue_daily_report）逐项一致。
       ⚠ 10.18 单日 15.21 万（门诊 13.02 万）是本月次高，仅低于 10.1 的 16.22 万；
         10.18 门诊 87 人次（初 7 / 复 80）为 10 月单日最高。 */
    /* ⚠ 2026-10-26 修：本行「出院」原记 4，只见「出院初次 4」、漏了「出院多次 1」。
       按源表出院＝初次＋多次应为 5，在院递推 32＋5−5＝32 才闭合（记 4 时会推出 33，与源表 32 矛盾）。 */
    '2026-10-18': [130216.02, 21929.66, 7, 80, 32, 5, 5],
    /* ⚠ 2026-10-26 修：同上，出院初次 2＋多次 2＝4（原记 2）。 */
    '2026-10-19': [23093.65, 54220.66, 5, 17, 30, 2, 4],
    /* ⚠ 2026-10-26 修：同上，出院初次 1＋多次 1＝2（原记 1）。 */
    '2026-10-20': [38068.91, 29528.77, 8, 19, 29, 1, 2],
    /* ⭐ 2026-10-21 — 10-23（业主 2026-10-25 提供营收日报截图，取数含心理科）。
       ✅ 逐日「门诊＋在院＝当日合计」与「当月累计」勾稽通过：
          10.21 74,144.84；10.22 71,787.59；10.23 98,966.52；
          10.23 当月累计 1,939,734.90（逐日加总 1,939,734.91，差 0.01 系四舍五入）。
       ⚠ 出院列＝出院初次＋出院多次（10.22 = 1＋1、10.23 = 1＋0）。
       ⚠ 10.23 门诊 5 人＋复诊 40 人却创周内单日最高 9.90 万，属结算集中，
         不代表日均节奏，排目标时不要按这天外推。 */
    '2026-10-21': [38835.29, 35309.55, 10, 17, 32, 3, 0],
    '2026-10-22': [25082.19, 46705.40, 5, 54, 32, 2, 2],
    '2026-10-23': [55094.50, 43872.02, 5, 40, 35, 4, 1],
    /* ⭐ 2026-10-24 — 10-25（业主 2026-10-26 提供营收日报截图，取数含心理科）。
       ✅ 五项勾稽全部通过：
          10.24 门诊 6,612.16＋在院 38,925.01＝当日合计 45,537.17；
                累計 1,939,734.90＋45,537.17＝1,985,272.07
          10.25 门诊 106,560.16＋在院 41,626.26＝当日合计 148,186.42；
                累计 1,985,272.07＋148,186.42＝2,133,458.49（源表末行）
          在院递推 10.24：35＋1−1＝35；10.25：35＋3−5＝33
       ⚠ 10.25 单日 14.82 万（门诊 10.66 万、复诊 75 人）为 10 月次高，
         仅低于 10.1 的 16.22 万；门诊环比 ＋99,948.00 是本轮最大单日回升。
       ⚠ 10.24（周六）门诊仅 6,612.16、当日 4.55 万，是月内第二低点
         （最低 10.8 的 3.20 万）—— 周末前后落差极大，别按单日外推。 */
    '2026-10-24': [6612.16, 38925.01, 3, 24, 35, 1, 1],
    '2026-10-25': [106560.16, 41626.26, 4, 75, 33, 3, 5],
    /* ⭐ 2026-10-26 — 10-28（业主 2026-10-29 提供营收日报截图，取数含心理科）。
       ✅ 五项勾稽全部通过：
          10.26 门诊 29,800.61＋在院 39,252.58＝当日 69,053.19；累计 2,133,458.49＋69,053.19＝2,202,511.68
          10.27 门诊 20,668.46＋在院 37,745.98＝当日 58,414.44；累计 2,202,511.68＋58,414.44＝2,260,926.12
          10.28 门诊 24,871.41＋在院 42,491.41＝当日 67,362.82；累计 2,260,926.12＋67,362.82＝2,328,288.94（源表末行）
          在院递推 10.26：33＋1−2＝32；10.27：32＋0−0＝32；10.28：32＋2−1＝33
          （出院列仍为「初次＋多次」合计：10.26＝2＋0、10.27＝0＋0、10.28＝1＋0）
       ⚠ 三日都落在**新的自然周 10.26—11.01**，不属于本期 10.19—10.25；
         该注释写于 10.29；2026-11-02 换期后 PERIOD_ANCHOR 已推进到 10.26，这三日（及 10.29—10.31）
         均属本期 10.26—11.01，进本周口径。
       ⚠ 10.27 门诊仅 20,668.46、14 人次（初 7／复 7），是 10 月单日次低；10.26 复诊 23 人、
         门诊 34 人次——节后回落明显，别按 10.25 的 14.82 万外推。 */
    '2026-10-26': [29800.61, 39252.58, 11, 23, 32, 1, 2],
    '2026-10-27': [20668.46, 37745.98, 7, 7, 32, 0, 0],
    '2026-10-28': [24871.41, 42491.41, 5, 16, 33, 2, 1],
    /* ⭐ 2026-10-29 — 10-31（业主 2026-11-01 提供营收日报截图，取数含心理科）：
       10 月**全月收官**的最后三天，补上后月累计 232.83 万 → **262.18 万**。
       ✅ 勾稽：
          10.29 门诊 15,142.80＋在院 43,292.71＝当日 58,435.51；累计 2,328,288.94＋58,435.51＝2,386,724.45
          10.30 门诊 17,829.45＋在院 50,272.46＝当日 68,101.91；累计 2,386,724.45＋68,101.91＝2,454,826.36
          10.31 门诊 132,458.80＋在院 34,464.84＝当日 166,923.64；累计 2,454,826.36＋166,923.64＝**2,621,750.00**
       ✅ 在院递推三日全部闭合（源表「出院」列＝出院初次＋出院多次）：
          10.29：33＋入 3−出(0＋1)=1 → **35**；10.30：35＋入 0−出(3＋0)=3 → **32**；
          10.31：32＋入 2−出(1＋0)=1 → **33**。
       ⛔ 2026-11-01 修：10.29 出院原误录为 3（实为初次 0＋多次 1＝1），
          导致在院递推差 2 人并被误记为「源表待核」。按业主截图逐格复读后改正，
          源表本身自洽，**无待核项**。
       ⚠ 10.31 单日 16.69 万（门诊 13.25 万、复诊 90 人）为 10 月**单日最高**，
          超过 10.1 的 16.22 万；月末冲量与 10.29—10.30 的低位（5.8／6.8 万）反差极大。 */
    '2026-10-29': [15142.80, 43292.71, 4, 13, 35, 3, 1],
    '2026-10-30': [17829.45, 50272.46, 4, 14, 32, 0, 3],
    '2026-10-31': [132458.80, 34464.84, 11, 90, 33, 2, 1],
    /* ⭐ 2026-11-01（业主 2026-11-02 提供营收日报截图，取数含心理科）。
       本期 10.26—11.01 由此满 7 天，营收 48.83 万 → **62.51 万**。
       ✅ 勾稽：
          11.01 门诊 84,840.41＋在院 52,010.73＝当日 136,851.14（＝11 月累计首日）
          在院递推 10.31：33＋入 5−出(1＋1)＝36 → 与源表「在院 36」一致
          门诊 4 初诊＋58 复诊＝62 人次；出院列＝初次 1＋多次 1＝2
       ⚠ 该日属 11 月，**不进 10 月累计**（10 月仍 262.18 万、31/31 天收官）；
         10.26—11.01 跨月 7 天合计 625,142.65 元，环比 10.19—10.25 同 7 天 58.35 万 +7.1%。 */
    '2026-11-01': [84840.41, 52010.73, 4, 58, 36, 5, 2],
    /* ⭐ 2026-11-02（业主 2026-11-04 提供营收日报截图，取数含心理科）。
       ⚠ 该日是**周一**，属新一周 11.02—11.08 的第 1 天，**不进上一期 10.26—11.01**；
         页面「本期」仍是已收官的 10.26—11.01（62.51 万），11.02 以「新一周进行中」并列。
       ✅ 勾稽：
          11.02 门诊 34,033.18＋在院 48,863.51＝当日 82,896.69
          在院递推 11.01：36＋入 3−出(0＋0)＝39 → 与源表「在院 39」一致
          门诊 9 初诊＋14 复诊＝23 人次；出院初次 0＋多次 0＝0，当日零出院
          11 月累计 136,851.14＋82,896.69＝**219,747.83**（21.97 万，2/30 天）
       ⚠ 源表「门诊环比 −50,807.23」「在院环比 −3,147.22」均为**对前一日**的差，
         不是同比/周比，页面不引用这两个数。 */
    '2026-11-02': [34033.18, 48863.51, 9, 14, 39, 3, 0],
    /* ⭐ 2026-11-03 / 11-04（业主 2026-11-05 提供营收日报截图，取数含心理科）。
       仍属新一周 11.02—11.08，累计 3 天；**不进已收官的 10.26—11.01**。
       ✅ 勾稽：
          11.03 门诊 30,145.10＋在院 47,345.08＝77,490.18；在院 39＋入 0−出(4＋0)＝35
          11.04 门诊 35,533.78＋在院 49,275.74＝84,809.52；在院 35＋入 3−出(0＋0)＝38
          人次 11.03：5＋15＝20；11.04：7＋13＝20
          11 月累计 219,747.83＋77,490.18＝297,238.01；＋84,809.52＝**382,047.53**（38.20 万，4/30 天）
       ⚠ 11.03 出院初次 4、多次 0 —— 该日入 0 出 4，是本期唯一净减日；
         11.04 入 3 出 0，回流一半。源表「环比」仍为对前一日差，页面不引用。 */
    '2026-11-03': [30145.10, 47345.08, 5, 15, 35, 0, 4],
    '2026-11-04': [35533.78, 49275.74, 7, 13, 38, 3, 0],
    /* ⭐ 2026-11-05 / 11-06（业主 2026-11-08 提供营收日报截图，取数含心理科）。
       本期周窗已滚到 11.02—11.08，这两日使本周已录 5 天（11.02—11.06）。
       ✅ 勾稽（源表「出院」= 出院初次＋出院多次，本数组记合计）：
          11.05 门诊 22,232.33＋在院 47,794.95＝70,007.28；在院 38＋入 0−出(1＋0)=37
          11.06 门诊 38,848.11＋在院 49,756.39＝88,604.50；在院 37＋入 2−出(7＋1)=31
          人次 11.05：5＋23＝28；11.06：2＋21＝23
          11 月累计 382,047.53＋70,007.28＝452,054.81；＋88,604.50＝**540,659.31**（54.07 万，6/30 天）
       ⚠ 11.06 出院 8 人（初次 7＋多次 1）为 11 月单日最高，在院由 37 降到 31（净 −6）。 */
    '2026-11-05': [22232.33, 47774.95, 5, 23, 37, 0, 1],
    '2026-11-06': [38848.11, 49756.39, 2, 21, 31, 2, 8]
  };


  /* ⚠ 周区间不再写死，改为**初始化时按真实日期推导**。
     起因：原先 WEEK_START/WEEK_END/TODAY 都是固定字符串（9.21—9.27 / TODAY=9.26）。
     过了这个区间之后，用户拖入 9.28、9.29 的日报时，数据其实**已经写进 localStorage**，
     但落在 [WEEK_START, WEEK_END] 之外 → 小结与 Hero 的「本周」不含它 →
     用户看到「图拖了、数字没变」= 误判为「数据没留存」。

     ⚠ 关键设计选择：**「本周」以「已有数据的最后一天」所在周为准，而不是以当天为准。**
     理由：营收日报/护理日报都是隔天甚至隔几天才补的，数据日很少正好等于当天。
     若按当天算，今天（9.28，周一）的「本周」会变成 9.28—10.04，
     反而让刚补进来的 9.27 落在区间外、又看不到 → 同一个错觉换个方向再犯一次。
     所以：取 SEED 与覆盖层里最晚的那一天所在周；没有任何数据时才退回「当天所在周」。

     字符串比较（YYYY-MM-DD）天然有序，既有逻辑不变；
     MONTH_FROM/MONTH_TO 也按真实当月推导，避免跨月时把新月份数据当脏数据清掉。 */
  function _d2s(d) { return d.getFullYear() + '-' + ('0' + (d.getMonth() + 1)).slice(-2) + '-' + ('0' + d.getDate()).slice(-2); }
  function _monOf(d) { var w = d.getDay(); return new Date(d.getFullYear(), d.getMonth(), d.getDate() - ((w + 6) % 7)); }  // 所在周的周一
  /* 探测数据最后一天：优先覆盖层，其次种子。读 localStorage 失败时安全退回当天。 */
  function _probeLastDay(fallback) {
    var best = null;
    var probe = function (obj) {
      if (!obj || typeof obj !== 'object') return;
      for (var k in obj) {
        if (!Object.prototype.hasOwnProperty.call(obj, k)) continue;
        if (!/^\d{4}-\d{2}-\d{2}$/.test(k)) continue;
        if (best === null || k > best) best = k;
      }
    };
    try { probe(JSON.parse(localStorage.getItem(LS_DAILY) || 'null')); } catch (e) { }
    try { probe(SEED); } catch (e) { }
    return best || fallback;
  }
  var _now = new Date();
  var _todayS = _d2s(_now);
  /* ⭐⭐ 2026-10-22：本期窗口锚点改为**显式常量**，不再取「数据最后一天」。
     起因：营收日报补到 10.20 后，_probeLastDay 返回 10.20（周二），
     本周被推导成 10.19—10.25 → Hero / 医生卡 / 本周小结全部空窗，
     而看板的「本期」按业主口径仍是 10.12—10.18。
     与 scripts/live-data/build_snapshot.py 的 settings.period_anchor 同一取值；
     换期时两处一起改。 */
  /* ⭐⭐ 2026-11-08：本期滚到自然周 11.02—11.08（业主确认：周一—周日 7 天）。
     与 scripts/live-data/build_snapshot.py 的 settings.period_anchor='2026-11-02'
     同一取值；换期时两处一起改（september-revenue-data.js 的 PERIOD_ANCHOR 同）。
     ⚠ 锚点必须是**周一**：_monOf() 会归一到本周周一，写周日会整体退回上一周。 */
  var PERIOD_ANCHOR = '2026-11-02';   // 本期 11.02—11.08；上期 10.26—11.01
  var _anchorS = PERIOD_ANCHOR || _probeLastDay(_todayS);   // 数据锚点日（本周归属以它为准）
  var _anchor = new Date(+_anchorS.slice(0, 4), +_anchorS.slice(5, 7) - 1, +_anchorS.slice(8));
  var _mon = _monOf(_anchor);                     // 锚点所在周的周一
  var _sun = new Date(_mon.getFullYear(), _mon.getMonth(), _mon.getDate() + 6);
  var _lwm = new Date(_mon.getFullYear(), _mon.getMonth(), _mon.getDate() - 7 * PERIOD_WEEKS - 7);
  var _lws = new Date(_mon.getFullYear(), _mon.getMonth(), _mon.getDate() - 8);
  var _pStart = new Date(_mon.getFullYear(), _mon.getMonth(), _mon.getDate() - 7 * (PERIOD_WEEKS - 1));   // 本期起点（两周窗口）
  /* ⚠ 「当月」以**数据锚点月**为准，不以系统当天为准。
     跨月时（如 10.1 打开 9 月看板）若按系统当月取窗口，9 月数据会整段落在
     窗口之外 → Hero 与「9月经营总览」一起归零（本轮实测命中）。
     与「本周以数据最后一天所在周为准」同一原则。 */
  /* ⭐⭐ 结算月（业主 2026-10-06 决定：主面板切到 10 月）。
     9 月内容不再靠「锁死月口径」保留，而是整份折进 #sepReport 抽屉
     （抽屉走 SEPTEMBER_REVENUE_DATA.derive('2026-09') 取 9 月口径）。
     ⚠ 月窗口仍按**结算月**取、不跟数据锚点月走 —— 与「本周按数据锚点周」各自独立；
       否则月内某天数据缺失时窗口会漂移。 */
  var SETTLED_MONTH = '2026-11';
  var MONTH_FROM = SETTLED_MONTH + '-01';
  var MONTH_TO = _d2s(new Date(+SETTLED_MONTH.slice(0, 4), +SETTLED_MONTH.slice(5, 7), 0));
  /* ⭐ 结算月的天数 / 月份标签（全站时间进度、收官文案共用，别再写死 30 或 '9 月'） */
  var MONTH_DAYS = new Date(+SETTLED_MONTH.slice(0, 4), +SETTLED_MONTH.slice(5, 7), 0).getDate();
  var MONTH_NUM = +SETTLED_MONTH.slice(5, 7);        // 10
  var MONTH_LABEL = MONTH_NUM + ' 月';               // '10 月'
  var MONTH_LABEL_TIGHT = MONTH_NUM + '月';          // '10月'
  var WEEK_START = _d2s(_pStart), WEEK_END = _d2s(_sun);   // 本期（两周窗口）＝数据锚点所在周 及其前一周
  var LW_START = _d2s(_lwm), LW_END = _d2s(_lws);          // 上一期（紧邻的完整两周期）
  var TODAY = _todayS;                                     // 今日（真实当天）
  var SOURCE_CUTOFF = TODAY;   // 其他数据源（客服/心理/管家/团体）的共同截止日
  /* 字段下标（供渲染与校验共用） */
  var F_OUT = 0, F_INP = 1, F_FIRST = 2, F_AGAIN = 3, F_INHOS = 4, F_ADMIT = 5, F_DISCH = 6;

  /* ============================ 工具 ============================ */
  function p2(n) { return (n < 10 ? '0' : '') + n; }
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]; }); }
  function num(v, d) { d = d == null ? 2 : d; return (Math.round(v * Math.pow(10, d)) / Math.pow(10, d)).toFixed(d); }
  function wan(yuan, d) { return num(yuan / 10000, d == null ? 2 : d); }
  function sign(v, d) { d = d == null ? 1 : d; return (v >= 0 ? '+' : '−') + Math.abs(v).toFixed(d); }
  function dateObj(s) { var p = String(s).split('-'); return new Date(+p[0], +p[1] - 1, +p[2]); }
  function shiftDay(s, n) { var d = dateObj(s); d.setDate(d.getDate() + n); return d.getFullYear() + '-' + p2(d.getMonth() + 1) + '-' + p2(d.getDate()); }
  function enumerate(a, b) { var out = [], c = a, guard = 0; while (c <= b && guard++ < 400) { out.push(c); c = shiftDay(c, 1); } return out; }
  /* 取某月相对偏移后的「YYYY-MM」前缀（-1 = 上月，+1 = 下月），用于数据保留窗口 */
  function shiftMonth(s, n) { var p = String(s).split('-'); var d = new Date(+p[0], (+p[1] - 1) + n, 1); return d.getFullYear() + '-' + p2(d.getMonth() + 1); }
  function dowOf(s) { return DOW[dateObj(s).getDay()]; }
  /* 编辑表里显示短日期（9.23），内部仍按标准日期处理；用户也可直接输入 9.23 */
  function shortDate(v) { var n = normDate(v); return n ? ((+n.slice(5, 7)) + '.' + (+n.slice(8))) : (v || ''); }
  function isWeekend(s) { var w = dateObj(s).getDay(); return w === 0 || w === 6; }
  function fmtCN(s) { var p = s.split('-'); return (+p[1]) + '月' + (+p[2]) + '日'; }
  function fmtDot(s) { var p = s.split('-'); return p[0] + '.' + p[1] + '.' + p[2]; }
  function rangeLabel(days) {
    if (!days || !days.length) return '';
    var a = days[0], b = days[days.length - 1], ma = a.slice(5, 7), da = a.slice(8), mb = b.slice(5, 7), db = b.slice(8);
    if (a === b) return fmtCN(a);
    if (ma === mb) return (+ma) + '月' + (+da) + '—' + (+db) + '日';
    return fmtCN(a) + '—' + fmtCN(b);
  }
  /* ⚠ 区间简写：月份必须从日期里取，**不可硬编码 '9.'**
     （原文写死 '9.' + (+d.slice(8))，跨到 10 月后 2026-10-04 被显示成「9.4」） */
  function shortRange(days) {
    if (!days || !days.length) return '';
    var a = days[0], b = days[days.length - 1];
    var sa = (+a.slice(5, 7)) + '.' + (+a.slice(8));
    var sb = (+b.slice(5, 7)) + '.' + (+b.slice(8));
    return a === b ? sa : sa + '—' + sb;
  }

  /* 日期归一化：支持 9.23 / 9月23日 / 2026-09-23 / 0923 / 20260923 */
  function normDate(raw, year) {
    year = year || 2026;
    if (raw == null) return null;
    var s = String(raw).trim();
    if (!s) return null;
    s = s.replace(/[年月]/g, '-').replace(/日/g, '').replace(/[./]/g, '-').replace(/\s+/g, '');
    var m;
    if ((m = s.match(/^(\d{4})-(\d{1,2})-(\d{1,2})$/))) return m[1] + '-' + p2(+m[2]) + '-' + p2(+m[3]);
    if ((m = s.match(/^(\d{1,2})-(\d{1,2})$/))) return year + '-' + p2(+m[1]) + '-' + p2(+m[2]);
    if (/^\d{8}$/.test(s)) return s.slice(0, 4) + '-' + s.slice(4, 6) + '-' + s.slice(6, 8);
    if (/^\d{4}$/.test(s)) return year + '-' + s.slice(0, 2) + '-' + s.slice(2, 4);
    return null;
  }

  /* 金额归一化：25,087.04 / 25087.04元 / 2.5万 → 元 */
  function toNum(raw) {
    if (raw == null) return null;
    var s = String(raw).trim();
    if (!s || /^[-—–]+$/.test(s)) return null;
    var isWan = /万/.test(s);
    s = s.replace(/万/g, '').replace(/[¥￥元,\s]/g, '').replace(/[（(][^）)]*[）)]/g, '');
    var v = parseFloat(s);
    if (!isFinite(v)) return null;
    return isWan ? v * 10000 : v;
  }

  /* ============================ 数据层 ============================ */
  function readJSON(key) { try { var r = localStorage.getItem(key); return r ? JSON.parse(r) : null; } catch (e) { return null; } }
  function writeJSON(key, v) { try { localStorage.setItem(key, JSON.stringify(v)); return true; } catch (e) { return false; } }

  function loadDaily() {
    var base = {}, k;
    for (k in SEED) if (Object.prototype.hasOwnProperty.call(SEED, k)) base[k] = SEED[k].slice();
    var ov = readJSON(LS_DAILY);
    if (ov && typeof ov === 'object') for (k in ov) if (Object.prototype.hasOwnProperty.call(ov, k)) base[k] = ov[k].slice();
    /* 服务端是权威层：它有的日期一律以它为准（否则两台设备各看各的）。
       唯一例外是「本机刚导入、但提交还没成功」的日期 —— 那些留着本地值，
       等下次提交成功再让服务端的值接管，避免当场把用户刚填的数抹掉。 */
    var pend = pendingSet();
    for (k in REMOTE_DAILY) {
      if (!Object.prototype.hasOwnProperty.call(REMOTE_DAILY, k)) continue;
      if (pend.indexOf(k) >= 0) continue;
      base[k] = REMOTE_DAILY[k].slice();
    }
    return base;
  }

  function pendingSet() {
    var a = readJSON(LS_PENDING);
    return Array.isArray(a) ? a : [];
  }
  function markPending(dates) {
    var p = pendingSet();
    (dates || []).forEach(function (d) { if (p.indexOf(d) < 0) p.push(d); });
    writeJSON(LS_PENDING, p);
  }
  function clearPending(dates) {
    var p = pendingSet().filter(function (d) { return (dates || []).indexOf(d) < 0; });
    writeJSON(LS_PENDING, p);
  }

  /* 从服务端拉覆盖层。纯静态部署时这里 404/失败 → 静默保持原状。 */
  function syncFromServer() {
    if (!window.fetch) return Promise.resolve(false);
    return fetch('/api/revenue', { cache: 'no-store' })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (j) {
        if (!j || !j.daily) return false;
        REMOTE_DAILY = j.daily;
        try { renderRevenue(); refreshMeta(); } catch (e) { }
        try { window.dispatchEvent(new CustomEvent('ops:revenue-updated', { detail: summary(loadDaily()) })); } catch (e) { }
        return true;
      })
      .catch(function () { return false; });
  }

  /* 把导入写进服务端。成功才算「已同步」，失败必须让用户看见，不能静默降级。 */
  var LS_TOKEN = 'ops.write.token';   // 写入口令：只在首次输入，之后记在本机
  function writeToken() { try { return localStorage.getItem(LS_TOKEN) || ''; } catch (e) { return ''; } }

  function sendImport(rows, names, token) {
    var headers = { 'Content-Type': 'application/json' };
    if (token) headers['X-Ops-Token'] = token;
    return fetch('/api/imports', {
      method: 'POST',
      headers: headers,
      body: JSON.stringify({ rows: rows, files: names || [], client: 'web' })
    });
  }

  function pushToServer(rows, names) {
    if (!window.fetch) return Promise.resolve({ ok: false, reason: '当前浏览器不支持网络提交' });
    var attempt = function (token) {
      return sendImport(rows, names, token).then(function (r) {
        // 401＝服务端设了口令而本机没有/不对，交给下面弹一次输入
        if (r.status === 401) return { ok: false, needToken: true, reason: '需要写入口令' };
        return r.json().catch(function () { return {}; }).then(function (j) {
          if (r.ok && j && j.ok) return { ok: true, summary: j };
          return { ok: false, reason: (j && j.error) || ('HTTP ' + r.status) };
        });
      }).catch(function (e) {
        return { ok: false, reason: '网络不通（' + ((e && e.message) || e) + '）' };
      });
    };
    return attempt(writeToken()).then(function (res) {
      if (!res.needToken) return res;
      var t = window.prompt('请输入看板写入口令（只需输一次，之后本机记住）');
      if (!t) return { ok: false, reason: '已取消：未输入写入口令' };
      return attempt(t.trim()).then(function (r2) {
        if (r2.ok) { try { localStorage.setItem(LS_TOKEN, t.trim()); } catch (e) { } }
        else if (r2.needToken) return { ok: false, reason: '写入口令不正确' };
        return r2;
      });
    });
  }
  /* ⭐⭐⭐ 2026-10-09：落盘**必须回读自检**，否则「存不住」会被当成「已保存」。
     ─────────────────────────────────────────────────────────────────
     原先末尾只有一句 `writeJSON(LS_DAILY, ov);`：
       · writeJSON 用 try/catch 把 setItem 的异常**静默吞掉**，只返回 false，而**没人看**；
       · 也没有回读 → 写入失败时内存里数据是对的，界面全对，**只有刷新会露馅**。
     触发场景（都不是罕见操作）：无痕/隐私模式、微信内置浏览器限制站点数据、
     浏览器「关闭后清除站点数据」、配额已满、看板被嵌在无 allow-same-origin 的 iframe。
     现在返回 {ok, reason, bytes}，**调用方必须据此决定要不要报成功**。 */
  function saveDaily(daily) {
    var ov = {}, k;
    for (k in daily) {
      if (!Object.prototype.hasOwnProperty.call(daily, k)) continue;
      var s = SEED[k], v = daily[k];
      var same = s && s.length === v.length && s.every(function (x, i) { return x === v[i]; });
      if (!same) ov[k] = v;
    }
    var txt = JSON.stringify(ov);
    if (!writeJSON(LS_DAILY, ov)) return { ok: false, reason: '本机存储写入被拒绝', bytes: 0 };
    var back = null;
    try { back = localStorage.getItem(LS_DAILY); } catch (e) { back = null; }
    if (back == null) return { ok: false, reason: '写入后读不到刚存的数据', bytes: 0 };
    if (back !== txt) return { ok: false, reason: '写入后被其它程序改写（回读不一致）', bytes: back.length };
    return { ok: true, reason: '', bytes: txt.length };
  }
  /* 本机存储可用性自检：失败时把**原因**讲清楚，别让用户自己猜。 */
  function storageCheck() {
    var probe = '__ops_store_probe__';
    try {
      localStorage.setItem(probe, '1');
      if (localStorage.getItem(probe) !== '1') return { ok: false, reason: '写入后回读不一致' };
      localStorage.removeItem(probe);
      return { ok: true, reason: '' };
    } catch (e) {
      var n = (e && e.name) || 'Error';
      var why = n === 'QuotaExceededError' ? '本机站点存储已满'
        : n === 'SecurityError' ? '浏览器或内嵌环境禁止本站点使用存储'
        : ((e && e.message) || '未知错误');
      return { ok: false, reason: why + '（' + n + '）' };
    }
  }
  function storageHint() {
    var c = storageCheck();
    if (c.ok) return '';
    return '<b>⚠ 检测到本机无法保存数据</b><span>' + esc(c.reason)
      + '。本次更新<b>只对当前页面有效，刷新后会回到上一版</b>。'
      + '请用普通浏览器（非无痕模式）直接打开本链接，并在浏览器设置里允许本站点保存站点数据后再试。</span>';
  }
  function resetDaily() { try { localStorage.removeItem(LS_DAILY); localStorage.removeItem(LS_META); } catch (e) { } }
  function importedMeta() { return readJSON(LS_META) || { imported: [], updatedAt: null }; }
  function snapshotBefore(daily, files) {
    writeJSON(LS_SNAP, { at: new Date().toISOString(), files: files, daily: daily });
  }

  /* ============================ 汇总 ============================ */
  function keysIn(daily, a, b) {
    return Object.keys(daily).filter(function (d) { return d >= a && d <= b; }).sort();
  }
  function agg(daily, days) {
    var o = 0, i = 0, hit = 0;
    var p = { first: 0, again: 0, admit: 0, disch: 0, inhos: null, inhosAt: null };
    var cover = { first: 0, again: 0, admit: 0, disch: 0 };
    days.forEach(function (d) {
      var v = daily[d]; if (!v) return;
      if (v[F_OUT] != null) o += v[F_OUT];
      if (v[F_INP] != null) i += v[F_INP];
      if (v[F_FIRST] != null) { p.first += v[F_FIRST]; cover.first++; }
      if (v[F_AGAIN] != null) { p.again += v[F_AGAIN]; cover.again++; }
      if (v[F_ADMIT] != null) { p.admit += v[F_ADMIT]; cover.admit++; }
      if (v[F_DISCH] != null) { p.disch += v[F_DISCH]; cover.disch++; }
      if (v[F_INHOS] != null) { p.inhos = v[F_INHOS]; p.inhosAt = d; }
      hit++;
    });
    p.cover = cover;
    p.days = hit;
    return { o: o, i: i, t: o + i, n: hit, days: days.slice(), p: p };
  }
  /* 人数是否覆盖了窗口内全部有收入的日子（用于决定要不要展示环比） */
  function peopleComplete(a) {
    return a.n > 0 && a.p.cover.first === a.n && a.p.cover.admit === a.n && a.p.cover.disch === a.n;
  }
  function summary(daily) {
    var twDays = keysIn(daily, WEEK_START, WEEK_END);
    var tw = agg(daily, twDays);
    var lwDays = keysIn(daily, LW_START, LW_END);
    var lw = agg(daily, lwDays);
    // 上一期同期 = 本期已有日期各前移 7×PERIOD_WEEKS 天（本期是两周窗口，故前移 14 天）
    var sameDays = twDays.map(function (d) { return shiftDay(d, -7 * PERIOD_WEEKS); }).filter(function (d) { return daily[d]; });
    var same = agg(daily, sameDays);
    // 月度（截至最新数据日）
    var mDays = keysIn(daily, MONTH_FROM, MONTH_TO);
    var cut = mDays.length ? mDays[mDays.length - 1] : null;
    var mtd = agg(daily, mDays);
    var cutD = cut ? +cut.slice(8) : 0;
    var done = mtd.t / 10000;
    var pct = MONTH_TARGET ? done / MONTH_TARGET * 100 : 0;
    var timePct = cutD / MONTH_DAYS * 100;
    var leftDays = Math.max(0, MONTH_DAYS - cutD);
    var monthClosed = cutD >= MONTH_DAYS;   // 月末收官：整月已走完
    var leftAmt = Math.max(0, MONTH_TARGET - done);
    var need = leftDays ? leftAmt / leftDays : 0;
    var twAvg = tw.n ? tw.t / 10000 / tw.n : 0;
    var sameAvg = same.n ? same.t / 10000 / same.n : 0;
    var gap = need - twAvg;
    var delta = same.t ? (tw.t / same.t - 1) * 100 : null;
    // 本周内应报未报（只到其他源截止日）
    var dueEnd = SOURCE_CUTOFF < WEEK_END ? SOURCE_CUTOFF : WEEK_END;
    var due = enumerate(WEEK_START, dueEnd);
    var missing = due.filter(function (d) { return !daily[d]; });
    // 上周完整周派生
    var lwAvg = lw.n ? lw.t / lw.n : 0;
    var weAmt = 0;
    lwDays.forEach(function (d) { if (isWeekend(d)) weAmt += (daily[d][0] || 0) + (daily[d][1] || 0); });
    var weShare = lw.t ? weAmt / lw.t * 100 : 0;
    var revCut = cut;
    var globalCut = revCut && revCut > SOURCE_CUTOFF ? revCut : SOURCE_CUTOFF;
    // 最近 7 个有收入数据的日期（用于逐日明细）
    var recent = mDays.slice().filter(function (d) { return daily[d] && ((daily[d][F_OUT] || 0) + (daily[d][F_INP] || 0)) > 0; });
    var rec7 = recent.slice(-7);
    var rec7Agg = agg(daily, rec7);
    var recWeekend = 0;
    rec7.forEach(function (d) { if (isWeekend(d)) recWeekend += (daily[d][F_OUT] || 0) + (daily[d][F_INP] || 0); });
    rec7Agg.weShare = rec7Agg.t ? recWeekend / rec7Agg.t * 100 : 0;
    return {
      tw: tw, lw: lw, same: same, sameDays: sameDays, mtd: mtd, mDays: mDays,
      rec7: rec7, rec7Agg: rec7Agg,
      twPeopleOk: peopleComplete(tw), samePeopleOk: peopleComplete(same),
      cut: cut, cutD: cutD, done: done, pct: pct, timePct: timePct,
      leftDays: leftDays, leftAmt: leftAmt, need: need, twAvg: twAvg, sameAvg: sameAvg,
      monthClosed: monthClosed,
      gap: gap, delta: delta, missing: missing, lwDays: lwDays, lwAvg: lwAvg,
      weShare: weShare, revCut: revCut, globalCut: globalCut, twDays: twDays
    };
  }

  /* ============================ 解析：CSV ============================ */
  function splitCSV(text) {
    var lines = text.replace(/\r\n?/g, '\n').replace(/^\uFEFF/, '').split('\n')
      .filter(function (l) { return l.trim() !== ''; });
    if (!lines.length) return [];
    var head = lines[0], cand = [',', '\t', ';', '|'], delim = ',', best = 0;
    cand.forEach(function (c) { var n = head.split(c).length; if (n > best) { best = n; delim = c; } });
    return lines.map(function (line) {
      var out = [], cur = '', q = false, i;
      for (i = 0; i < line.length; i++) {
        var ch = line.charAt(i);
        if (q) {
          if (ch === '"') { if (line.charAt(i + 1) === '"') { cur += '"'; i++; } else q = false; }
          else cur += ch;
        } else {
          if (ch === '"') q = true;
          else if (ch === delim) { out.push(cur); cur = ''; }
          else cur += ch;
        }
      }
      out.push(cur);
      return out;
    });
  }

  /* 从二维表提取行：定位表头列；无表头时退化为 日期/门诊/在院 顺序 */
  function rowsFromTable(table) {
    if (!table || table.length < 2) return [];
    var hi = -1, i;
    /* ⚠ 表头行判定要防「说明句误判」：
       业务表首行常有一段说明（如「环比：正数=收入增加…」），它含「收入」二字，
       用 /日期/ + /收入/ 的宽松判定会把它当成表头 → 后续列映射全错。
       判据收紧为：
         ① 必须含日期关键词；
         ② 必须含收入关键词；
         ③ 该行**不含中文冒号/分号**（说明句特征：「环比：」「说明；」）；
         ④ 表头行的「短单元格」占比要高（列名都是短词，说明句是长文本）。
       先按收紧条件扫前 8 行；找不到再放宽（兼容极简两列表）。 */
    var looksLikeNote = function (s) { return /[：；]/.test(s) || s.length > 120; };
    var hasDate = function (s) { return /日期|时间|date/i.test(s); };
    var hasMoney = function (s) { return /门诊|在院|住院|合计|收入/.test(s); };
    for (i = 0; i < Math.min(table.length, 12); i++) {
      var cells = table[i].map(function (c) { return String(c == null ? '' : c).trim(); });
      var nonEmpty = cells.filter(function (c) { return c !== ''; });
      if (!nonEmpty.length) continue;
      var j = nonEmpty.join('|');
      if (!hasDate(j) || !hasMoney(j)) continue;
      if (looksLikeNote(j)) continue;                       // 说明句 → 不是表头
      var shortRatio = nonEmpty.filter(function (c) { return c.length <= 8; }).length / nonEmpty.length;
      if (shortRatio < 0.6 && nonEmpty.length > 3) continue; // 长文本为主 → 不是表头
      hi = i; break;
    }
    if (hi < 0) {                                            // 放宽：只要求日期 + 收入
      for (i = 0; i < Math.min(table.length, 8); i++) {
        var j2 = table[i].join('|');
        if (hasDate(j2) && hasMoney(j2) && !looksLikeNote(j2)) { hi = i; break; }
      }
    }
    var col = { date: -1, out: -1, inp: -1, total: -1 };
    /* ⚠ 列名匹配要比「先到先得」更聪明：
       业务表里常见「门诊收入 / 门诊环比」「在院收入 / 在院环比」并列，
       而「环比」列在「收入」列**之前**，用 /门诊/ 会先把环比列抢走。
       故分两轮：第一轮只认「收入」类精确列名，第二轮才放宽。
       同时显式排除「环比 / 占比 / 同比 / 差额 / 累计」等派生列。 */
    if (hi >= 0) {
      var BAD = /环比|占比|同比|差额|校验|累计|增减|增幅|比率|百分比|人数|人次/;
      var pick = function (re, key) {
        if (col[key] >= 0) return;
        table[hi].forEach(function (c, idx) {
          if (col[key] >= 0) return;
          var t = String(c).replace(/\s/g, '');
          if (!t || BAD.test(t)) return;
          if (re.test(t)) col[key] = idx;
        });
      };
      /* 第一轮：精确列名 */
      pick(/(门诊|门|outpatient).{0,4}收入|^门诊$/, 'out');
      pick(/(在院|住院|病房).{0,4}收入|^在院$/, 'inp');
      pick(/(当日|今日).{0,4}(收入)?合计|^合计$|^总计$|营业(收入)?合计/, 'total');
      pick(/^(日期|时间|date|统计日期)$/i, 'date');
      /* 第二轮：放宽，但仍排除派生列 */
      pick(/门诊/, 'out');
      pick(/(在院|住院)/, 'inp');
      pick(/(合计|总计|当日收入|营收合计)/, 'total');
      pick(/日期|时间|date/i, 'date');
    }
    if (col.date < 0) col.date = 0;
    /* ⚠ 兜底列映射会「猜列」：表头认不出营收关键词时，把第 2 列当门诊收入、第 3 列当在院收入。
       这会让「日期 + 应做/实做」「日期 + 各项考核分」这类**非营收表**（如护理日表、质控表）
       被静默写成营收覆盖层，污染 Hero 与财务模块，而且界面还报「成功」。
       故加一道「表头不像营收日报就不猜列」的闸：认不出营收表头时，
       只有该行看不出是别的业务表才允许兜底。
       ⚠ 注意这份黑名单只能放**明确与营收无关**的词；不要放「治疗 / 入院 / 出院 / 检查」这类
       营收表本身也会出现的字段（否则会把正常营收表一起拦掉）。 */
    var headTxt = hi >= 0 ? table[hi].join('|') : table.slice(0, 8).map(function (r) { return r.join('|'); }).join('|');
    var NOT_REVENUE = /护理|质控|考核|应做|实做|完成率|排名|绩效|心理咨询|回访台账|管家对接|转住院|工娱|约束执行|在岗|分管患者|护士姓名/;
    if (NOT_REVENUE.test(headTxt)) return [];          // 表头自证是非营收表 → 不解析
    if (col.out < 0 && col.inp < 0 && col.total < 0) { /* 表头完全没有收入列 → 不猜列，交由上层提示 */ return []; }

    var rows = [];
    table.forEach(function (row, ri) {
      if (ri === hi) return;
      var joined = row.join(' ').trim();
      if (!joined) return;
      var d = normDate(col.date < row.length ? row[col.date] : row[0]);
      if (!d) return;
      var o = col.out >= 0 ? toNum(row[col.out]) : null;
      var p = col.inp >= 0 ? toNum(row[col.inp]) : null;
      var t = col.total >= 0 ? toNum(row[col.total]) : null;

      if (o == null && p == null && t == null) return;
      /* ⚠ 必须标注 verified：上层 handleFiles() 只把 r.verified === true 的行填进编辑区，
         否则表格/CSV 通道解析出的行会因为缺这个字段而**只带出日期、丢掉全部金额**
         （现象：拖入 xlsx 后识别到 26 行，但金额列全是空的）。
         表格数据的自洽判据与图片一致：门诊 + 在院 = 当日合计（两者都有值时）。 */
      var verified = false;
      if (o != null && p != null && t != null) verified = Math.abs((o + p) - t) < 0.02;
      else if (o != null || p != null) verified = true;   // 只有一列金额也算可用（上层可核对）
      rows.push({ date: d, out: o, inp: p, total: t, raw: joined.slice(0, 70), verified: verified });
    });
    return rows;
  }

  /* ============================ 解析：XLSX ============================ */
  function zipIndex(buf) {
    var dv = new DataView(buf), u8 = new Uint8Array(buf), eocd = -1, i;
    for (i = buf.byteLength - 22; i >= Math.max(0, buf.byteLength - 66000); i--) {
      if (dv.getUint32(i, true) === 0x06054b50) { eocd = i; break; }
    }
    if (eocd < 0) throw new Error('不是有效的 xlsx（未找到 ZIP 结构）');
    var n = dv.getUint16(eocd + 10, true), p = dv.getUint32(eocd + 16, true), entries = {};
    for (i = 0; i < n; i++) {
      if (p + 46 > buf.byteLength || dv.getUint32(p, true) !== 0x02014b50) break;
      var method = dv.getUint16(p + 10, true);
      var csize = dv.getUint32(p + 20, true);
      var usize = dv.getUint32(p + 24, true);
      var nlen = dv.getUint16(p + 28, true);
      var elen = dv.getUint16(p + 30, true);
      var clen = dv.getUint16(p + 32, true);
      var lho = dv.getUint32(p + 42, true);
      var name = new TextDecoder('utf-8').decode(u8.subarray(p + 46, p + 46 + nlen));
      entries[name] = { method: method, csize: csize, usize: usize, lho: lho };
      p += 46 + nlen + elen + clen;
    }
    return { u8: u8, dv: dv, entries: entries };
  }
  function inflateRaw(u8) {
    if (typeof DecompressionStream === 'undefined') throw new Error('当前浏览器不支持解压 xlsx，请另存为 CSV 后导入');
    var ds = new DecompressionStream('deflate-raw');
    return new Response(new Blob([u8]).stream().pipeThrough(ds)).text();
  }
  function zipRead(zip, name) {
    var e = zip.entries[name];
    if (!e) return Promise.resolve(null);
    var p = e.lho, dv = zip.dv, u8 = zip.u8;
    if (dv.getUint32(p, true) !== 0x04034b50) return Promise.resolve(null);
    var nlen = dv.getUint16(p + 26, true), elen = dv.getUint16(p + 28, true);
    var start = p + 30 + nlen + elen;
    var raw = u8.subarray(start, start + (e.csize || e.usize));
    if (e.method === 0) return Promise.resolve(new TextDecoder('utf-8').decode(raw));
    return inflateRaw(raw);
  }
  function colIdx(ref) {
    var n = 0, s = String(ref).replace(/[^A-Za-z]/g, '').toUpperCase(), i;
    for (i = 0; i < s.length; i++) n = n * 26 + (s.charCodeAt(i) - 64);
    return n - 1;
  }
  function decodeXML(s) {
    return String(s).replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"')
      .replace(/&apos;/g, "'").replace(/&#(\d+);/g, function (_, d) { return String.fromCharCode(+d); })
      .replace(/&amp;/g, '&');
  }
  /* ⚠ xlsx 的 XML 有两种写法：Excel 通常是**无前缀**的 <row>/<c>/<v>，
     而 WPS / 金山导出的是**带命名空间前缀**的 <x:row>/<x:c>/<x:v>。
     原先的正则只认无前缀版 → 拖入 WPS 导出的 xlsx 时**一个单元格都匹配不到**，
     静默返回 0 行（用户看到「未识别到数据行」）。
     这里统一加可选前缀 (?:[A-Za-z_][\w.-]*:)? 两种都能解析。 */
  var NS = '(?:[A-Za-z_][\\w.-]*:)?';
  function parseShared(xml) {
    if (!xml) return [];
    var out = [], re = new RegExp('<' + NS + 'si\\b[^>]*>([\\s\\S]*?)</' + NS + 'si>', 'g'), m;
    while ((m = re.exec(xml))) {
      var txt = '', tr = new RegExp('<' + NS + 't\\b[^>]*>([\\s\\S]*?)</' + NS + 't>', 'g'), t;
      while ((t = tr.exec(m[1]))) txt += decodeXML(t[1]);
      out.push(txt);
    }
    return out;
  }
  function parseSheetXML(xml, shared) {
    var table = [], re = new RegExp('<' + NS + 'row\\b([^>]*)>([\\s\\S]*?)</' + NS + 'row>', 'g'), m;
    var crefTpl = '<' + NS + 'c\\b([^>]*?)(?:\\/>|>([\\s\\S]*?)</' + NS + 'c>)';
    while ((m = re.exec(xml))) {
      var rAttr = m[1], row = [];
      var ri = rAttr.match(/\br="(\d+)"/);
      var cref = new RegExp(crefTpl, 'g'), c;
      while ((c = cref.exec(m[2]))) {
        var attr = c[1] || '', inner = c[2] || '';
        var refM = attr.match(/\br="([A-Za-z]+\d+)"/);
        var ci = refM ? colIdx(refM[1]) : row.length;
        var tm = attr.match(/\bt="([^"]+)"/);
        var type = tm ? tm[1] : 'n';
        var val = '';
        if (type === 'inlineStr') {
          var ir = new RegExp('<' + NS + 't\\b[^>]*>([\\s\\S]*?)</' + NS + 't>', 'g'), it, acc = '';
          while ((it = ir.exec(inner))) acc += decodeXML(it[1]);
          val = acc;
        } else {
          var vr = inner.match(new RegExp('<' + NS + 'v>([\\s\\S]*?)</' + NS + 'v>'));
          var raw = vr ? decodeXML(vr[1]) : '';
          if (type === 's') { var idx = parseInt(raw, 10); val = shared[idx] != null ? shared[idx] : ''; }
          else val = raw;
        }
        row[ci] = val;
      }
      for (var k = 0; k < row.length; k++) if (row[k] === undefined) row[k] = '';
      table.push({ r: ri ? +ri[1] : table.length + 1, cells: row });
    }
    table.sort(function (a, b) { return a.r - b.r; });
    return table.map(function (x) { return x.cells; });
  }
  /* ⚠ 要点：不能只看第一个 sheet。业务方给的汇总文件常把「月度汇总」放在 sheet1，
     而真正的逐日数据在 O:P:R 列或干脆在别的 sheet 里。
     策略：按 sheet1..sheetN **逐个尝试**，返回第一个能解析出数据行的结果；
     全都解析不出时才回退第一个 sheet（让上层给出「未识别到数据行」的提示）。 */
  function parseXLSX(buf) {
    var zip = zipIndex(buf);
    return zipRead(zip, 'xl/sharedStrings.xml').then(function (shared) {
      var sh = parseShared(shared);
      var names = Object.keys(zip.entries).filter(function (n) {
        return /^xl\/worksheets\/sheet\d+\.xml$/i.test(n);
      }).sort(function (a, b) {
        var na = +a.replace(/\D/g, ''), nb = +b.replace(/\D/g, '');
        return na - nb;
      });
      if (!names.length) throw new Error('xlsx 内未找到工作表数据');
      var i = 0, firstResult = null;
      function tryNext() {
        if (i >= names.length) return firstResult || [];
        var nm = names[i++];
        return zipRead(zip, nm).then(function (sx) {
          if (!sx) return tryNext();
          var rows = rowsFromTable(parseSheetXML(sx, sh));
          if (rows.length) return rows;            // 找到有数据的 sheet，直接用
          if (firstResult == null) firstResult = rows;
          return tryNext();
        });
      }
      return tryNext();
    });
  }

  /* ============================ 解析：粘贴文本 ============================ */
  function parsePasted(text) {
    var t = String(text || '').trim();
    if (!t) return [];
    if (t.indexOf(',') >= 0 || t.indexOf('\t') >= 0) return rowsFromTable(splitCSV(t));
    // 逐行宽松匹配：日期 + 若干金额
    var rows = [];
    t.split(/\n+/).forEach(function (line) {
      line = line.trim(); if (!line) return;
      var md = line.match(/(\d{4}[-./年]\d{1,2}[-./月]\d{1,2}|\d{1,2}[-./月]\d{1,2})/);
      if (!md) return;
      var d = normDate(md[1]); if (!d) return;
      var rest = line.slice(line.indexOf(md[1]) + md[1].length);
      var nums = [], rn = /(\d[\d,]*\.?\d*)\s*(万)?/g, mm;
      while ((mm = rn.exec(rest))) {
        if (!mm[1].replace(/[^\d]/g, '')) continue;
        var v = parseFloat(mm[1].replace(/,/g, ''));
        if (!isFinite(v)) continue;
        nums.push(mm[2] ? v * 10000 : v);
      }
      if (!nums.length) return;
      var o = nums[0] != null ? nums[0] : null;
      var p = nums.length > 1 ? nums[1] : null;
      var tot = nums.length > 2 ? nums[2] : null;
      rows.push({ date: d, out: o, inp: p, total: tot, raw: line.slice(0, 70) });
    });
    return rows;
  }

  /* 列级单位推断：整列都 < 1000 视为「万元」记法 */
  function inferUnit(rows) {
    var vals = [];
    rows.forEach(function (r) { [r.out, r.inp].forEach(function (v) { if (v != null && v > 0) vals.push(v); }); });
    if (!vals.length) return 1;
    var mx = Math.max.apply(null, vals);
    return mx < 1000 ? 10000 : 1;
  }

  /* ============================ 校验 ============================ */
  function verifyRows(rows, daily) {
    var unit = inferUnit(rows), seen = {}, out = [];
    rows.forEach(function (r) {
      var o = r.out != null ? r.out * unit : null;
      var p = r.inp != null ? r.inp * unit : null;
      var rec = { date: r.date, out: o, inp: p, raw: r.raw, notes: [] };
      /* ⚠ 原先这里只带 date/out/inp/raw，把人数全部丢掉，导致 applyImport() 里
         `if (r.first != null) arr[F_FIRST] = r.first` 恒不成立 —— 识别结果表里
         填的初诊/复诊/在院/入院/出院**一个都写不进去**。此处按原样透传。 */
      ['first', 'again', 'inhos', 'admit', 'disch'].forEach(function (k) {
        if (r[k] != null) rec[k] = r[k];
      });
      /* ⭐⭐⭐ 2026-10-09：提示必须**可操作** —— 说清缺什么、在哪补、补完能不能提交。
         旧文案两个坑：
           · 日期为空时 `'' < '2026-10-01'` 为 true，于是走「不在当月区间」，
             用户完全不知道**日期根本没识别出来**（提示与事实不符）；
           · 只写「缺少门诊/在院金额」，没说去哪个输入框补。
         现在把「无日期」「无金额」「日期超区间（回显实际值）」分成三种情况。 */
      if (!rec.date) {
        rec.status = 'invalid';
        rec.notes.push('未识别到日期 —— 请在左侧「日期」列填上（如 10.8），填好即可提交');
      } else if (o == null && p == null) {
        rec.status = 'invalid';
        rec.notes.push('未识别到金额 —— 请在「门诊收入 / 在院收入」两列补齐，填好即可提交');
      } else if (rec.date < MONTH_FROM || rec.date > MONTH_TO) {
        rec.status = 'invalid';
        rec.notes.push('识别到的日期是「' + rec.date.slice(5) + '」，不在当前月区间（'
          + MONTH_FROM.slice(5) + '—' + MONTH_TO.slice(5) + '）—— 请核对填对');
      }
      else {
        var cur = daily[rec.date];
        if (!cur) { rec.status = 'new'; }
        else {
          /* ⚠⚠ 判定必须把**人数列也带上**（2026-10-07 修）：
             原先只比 cur[0]/cur[1]（门诊、在院两个金额列），
             用户把「在院 33 → 36」「出院补 5」改对后，界面仍显示「一致 / 0 天」，
             看起来像「改了没反应」，实际数据是会写进去的 —— 用户因此误判功能坏了。
             现在：金额与人数字段任一有变化都算 update，并在备注里说明是哪一类。 */
          var moneySame = (cur[0] === o && cur[1] === p);
          var PPL = [['first', F_FIRST], ['again', F_AGAIN], ['inhos', F_INHOS], ['admit', F_ADMIT], ['disch', F_DISCH]];
          var peopleDiff = false;
          PPL.forEach(function (kv) {
            var nv = rec[kv[0]];
            if (nv == null || nv === '') return;            // 没识别到 → 不作为差异
            var cv = cur[kv[1]];
            if (cv == null || Number(cv) !== Number(nv)) peopleDiff = true;
          });
          if (moneySame && !peopleDiff) { rec.status = 'same'; rec.notes.push('与现值一致'); }
          else {
            rec.status = 'update'; rec.old = cur.slice();
            if (moneySame) rec.notes.push('金额未变，仅人数/床位等字段有更新');
          }
        }
        var key = rec.date;
        if (seen[key]) {
          var prev = seen[key];
          if (prev.out !== o || prev.inp !== p) {
            rec.status = 'conflict'; prev.status = 'conflict';
            rec.notes.push('批次内同日期数值不一致');
            prev.notes.push('批次内同日期数值不一致');
          }
        }
        seen[key] = rec;
        if (rec.status === 'update' && rec.old) {
          var base = (rec.old[0] || 0) + (rec.old[1] || 0);
          var next = (o || 0) + (p || 0);
          if (base > 0 && next && Math.abs(next / base - 1) > 0.5) rec.notes.push('与现值差异超 50%，请核对');
        }
      }
      if (!rec.status) rec.status = 'invalid';
      out.push(rec);
    });
    return { unit: unit, rows: out };
  }

  /* ============================ 渲染：全站同步 ============================ */
  function $(s, r) { return (r || document).querySelector(s); }
  function $$(s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); }
  function setText(sel, txt) { $$(sel).forEach(function (e) { e.textContent = txt; }); }

  function renderRevenue() {
    var daily = loadDaily(), s = summary(daily), shell = $('.mkt-v2');

    /* ---- 时间戳 / 口径行 ---- */
    var revTxt = s.revCut ? fmtCN(s.revCut) : '—';
    var cutTxt = fmtCN(s.globalCut);
    var _p = window.__OPS_PERIOD;
    /* 2026-11-09：水位以《特别行动小组汇报表》为准（至 11.08 / 7 天），
       营收日报台账只到 11.06（5 天）。此前取 dataThrough 会把顶部写成 11.06。 */
    var stamp = (_p && (_p.reportDataThrough || _p.dataThrough)) ? (_p.reportDataThrough || _p.dataThrough)
      : ((s.revCut && s.revCut > TODAY) ? s.revCut : TODAY);
    setText('#periodBtn', '数据更新至 ' + stamp.split('-')[0] + '年' + (+stamp.slice(5, 7)) + '月' + (+stamp.slice(8)) + '日');
    $$('.ov-live').forEach(function (e) {
      var _q = window.__OPS_PERIOD;
      if (_q && _q.reportDataThrough) {
        var _rv = _q.revenueDataThrough || _q.dataThrough || _q.reportDataThrough;
        var _rd = (_q.daysRecorded != null) ? _q.daysRecorded : '—';
        e.innerHTML = '<i></i>每日 09:00 抓取 · 汇报表至 ' + (+_q.reportDataThrough.slice(5, 7)) + '.' + ('0' + (+_q.reportDataThrough.slice(8))).slice(-2)
          + '（' + _rd + ' 天）· 营收台账至 ' + (+_rv.slice(5, 7)) + '.' + ('0' + (+_rv.slice(8))).slice(-2);
      } else {
        e.innerHTML = '<i></i>每日 09:00 抓取 · 数据更新至 ' + (+s.globalCut.slice(5, 7)) + '.' + ('0' + (+s.globalCut.slice(8))).slice(-2);
      }
    });
    setText('.mkt-filter small', ''); // 由下方重建（含 ● 图标）
    $$('.mkt-filter small').forEach(function (e) {
      e.innerHTML = '<b>●</b> 数据更新至 ' + fmtDot(TODAY) + '　·　本期 ' + fmtCN(WEEK_START) + '—' + fmtCN(WEEK_END) + '（进行中，各源数据至 ' + cutTxt + '，营收至 ' + revTxt + '）';
    });
    setText('.dc-scope', '本期 ' + shortRange(enumerate(WEEK_START, WEEK_END)) + ' · 数据截至 ' + (s.globalCut ? (+s.globalCut.slice(5, 7)) + '.' + (+s.globalCut.slice(8)) : '—') + '（营收 ' + (s.revCut ? (+s.revCut.slice(5, 7)) + '.' + (+s.revCut.slice(8)) : '—') + '）');
    setText('#sheetSub', '数据更新至 ' + TODAY.split('-')[0] + '年' + (+TODAY.slice(5, 7)) + '月' + (+TODAY.slice(8)) + '日 · 独立部门经营模块');

    /* ---- Hero ---- */
    if (s.tw.n) {
      var sub = shortRange(s.twDays) + ' · 日均 ¥' + num(s.twAvg, 2) + '万';
      if (s.delta != null) sub += ' · 较上一期同期 ' + sign(s.delta, 1) + '%';
      if (s.missing.length) sub += '（' + shortRange(s.missing) + ' 日报待补）';
      $$('.mkt-amount').forEach(function (e) { e.innerHTML = '¥' + wan(s.tw.t, 2) + '<i>万</i>'; });
      setText('.mkt-sub', sub);
      setText('.mkt-hero-kicker', '本期营业额');
    } else {
      $$('.mkt-amount').forEach(function (e) { e.innerHTML = '—'; });
      setText('.mkt-sub', '本期暂无营收数据');
    }

    /* ---- 目标进度卡 ---- */
    var diff = s.timePct - s.pct;
    setText('.mkt-progress-big > b', wan(s.mtd.t, 2) + '万 / ' + MONTH_TARGET + '万');
    var meta = $$('.mkt-progress-meta span');
    if (meta[0]) meta[0].innerHTML = '金额完成 <strong>' + s.pct.toFixed(1) + '%</strong>';
    if (meta[1]) meta[1].textContent = '时间进度 ' + s.timePct.toFixed(1) + '%';
    $$('.mkt-progress-line').forEach(function (line) {
      var i = line.querySelector('i'), b = line.querySelector('b');
      if (i) i.style.width = Math.max(0, Math.min(100, s.pct)).toFixed(1) + '%';
      if (b) { b.style.left = Math.max(0, Math.min(100, s.timePct)).toFixed(1) + '%'; b.title = '时间进度 ' + s.timePct.toFixed(1) + '%'; }
    });
    // 目标进度卡的 badge
    var progCard = $$('.mkt-card').filter(function (c) { return /营收目标进度/.test(c.textContent); })[0];
    if (progCard) {
      var bd = progCard.querySelector('.mkt-badge');
      if (bd) bd.textContent = (diff >= 0 ? '落后 ' : '领先 ') + Math.abs(diff).toFixed(1) + 'pt';
    }
    var gapBoxes = $$('.mkt-gap > div');
    var gapVals = [num(s.leftAmt, 2) + '万', s.leftDays + '天', num(s.need, 2) + '万', num(s.twAvg, 2) + '万'];
    gapBoxes.forEach(function (box, i) {
      if (i > 3) return;
      var b = box.querySelector('b');
      if (b) b.textContent = gapVals[i];
    });

    /* ---- 经营问题总览 #decisionCore ----
       该区块由 business-analysis.js 负责渲染（它是 owner）。这里**不直接改它的 DOM**
       （逐条正则改写既脆弱又容易漏），而是派发一个专用事件让 owner 自己重绘 ——
       这样结构与文案都不受外部影响，只有数字跟着数据走。 */
    try { window.dispatchEvent(new CustomEvent('ops:core-refresh', { detail: s })); } catch (e) { }

    /* ---- 营收速度缺口柱 ---- */
    var bars = $$('.gap-bars .gap-bar');
    if (bars.length >= 3) {
      var base = s.need || 1;
      var seq = [
        [num(s.twAvg, 2) + '万', s.twAvg / base * 100, '本期实际日均'],
        [num(s.sameAvg, 2) + '万', s.sameAvg / base * 100, '上一期同期日均'],
        [num(s.need, 2) + '万', 100, '达标所需日均']
      ];
      bars.forEach(function (bar, i) {
        if (!seq[i]) return;
        var em = bar.querySelector('em'), i2 = bar.querySelector('i'), sp = bar.querySelector('span');
        if (em) em.textContent = seq[i][0];
        if (i2) i2.style.setProperty('--h', Math.max(3, Math.min(100, seq[i][1])).toFixed(0) + '%');
        if (sp) sp.textContent = seq[i][2];
      });
    }
    // 卡片标题里的缺口 badge
    var barCard = $$('.mkt-card').filter(function (c) { return /营收速度缺口/.test(c.textContent); })[0];
    if (barCard && barCard.querySelector('.mkt-badge')) barCard.querySelector('.mkt-badge').textContent = '缺口 ' + num(Math.max(0, s.gap), 2) + '万/日';

    /* ---- 收入结构（本期） ---- */
    if (s.tw.t) {
      var oPct = s.tw.o / s.tw.t * 100, iPct = s.tw.i / s.tw.t * 100;
      $$('.mkt-ring div').forEach(function (e) {
        e.innerHTML = '<b>' + wan(s.tw.t, 2) + '万</b>本期 ' + shortRange(s.twDays);
      });
      var lg = $$('.mkt-legend span');
      if (lg[0]) lg[0].innerHTML = '<b style="color:#26ae81">' + oPct.toFixed(1) + '%</b>门诊 ' + wan(s.tw.o, 2) + '万';
      if (lg[1]) lg[1].innerHTML = '<b style="color:#2e8ee9">' + iPct.toFixed(1) + '%</b>住院 ' + wan(s.tw.i, 2) + '万';
      var ringCard = $$('.mkt-card').filter(function (c) { return /收入结构/.test(c.textContent); })[0];
      if (ringCard && ringCard.querySelector('.mkt-card-head p')) {
        ringCard.querySelector('.mkt-card-head p').textContent = '本期 ' + shortRange(s.twDays) + ' · ' + (oPct >= iPct ? '门诊' : '住院') + '为主要收入来源';
      }
    }

    /* ---- 逐日明细表（最近 7 天，含最新数据） ---- */
    var tbl = $('.mkt-day-table');
    if (tbl && s.rec7.length) {
      var tb = tbl.querySelector('tbody'), tf = tbl.querySelector('tfoot');
      var mx = Math.max.apply(null, s.rec7.map(function (d) { return (daily[d][F_OUT] || 0) + (daily[d][F_INP] || 0); }));
      var mn = Math.min.apply(null, s.rec7.map(function (d) { return (daily[d][F_OUT] || 0) + (daily[d][F_INP] || 0); }));
      var rowsHtml = '', prev = null;
      s.rec7.forEach(function (d) {
        var amt = (daily[d][F_OUT] || 0) + (daily[d][F_INP] || 0);
        var diffTxt = '—', diffCls = '';
        if (prev) { var r = (amt - prev) / prev * 100; diffTxt = sign(r, 1) + '%'; diffCls = r >= 0 ? 'up' : 'down'; }
        var judge = '常态', jcls = '';
        if (amt === mx) { judge = '峰值'; jcls = 'up'; }
        else if (amt === mn) { judge = '低谷'; jcls = 'down'; }
        else if (prev != null && amt > prev) { judge = '回升'; jcls = 'up'; }
        else if (prev != null && amt < prev) { judge = '回落'; jcls = 'down'; }
        var we = isWeekend(d) ? ' class="weekend"' : '';
        rowsHtml += '<tr' + we + '><td>' + (+d.slice(5, 7)) + '.' + (+d.slice(8)) + ' ' + dowOf(d) + '</td><td><strong>' + wan(amt, 2) + '万</strong></td><td class="' + diffCls + '">' + diffTxt + '</td><td>' + (amt / s.rec7Agg.t * 100).toFixed(1) + '%</td><td class="' + jcls + '">' + judge + '</td></tr>';
        prev = amt;
      });
      if (tb) tb.innerHTML = rowsHtml;
      if (tf) tf.innerHTML = '<tr><td>合计</td><td>' + wan(s.rec7Agg.t, 2) + '万</td><td>日均' + wan(s.rec7Agg.n ? s.rec7Agg.t / s.rec7Agg.n : 0, 2) + '万</td><td>100%</td><td>关键日集中</td></tr>';
      var head = tbl.closest('.mkt-card');
      if (head) {
        var hp = head.querySelector('.mkt-card-head p');
        if (hp) hp.textContent = '最近 7 天 ' + shortRange(s.rec7) + ' · 营收日报口径';
        var hb = head.querySelector('.mkt-badge');
        if (hb) hb.textContent = '周末贡献 ' + s.rec7Agg.weShare.toFixed(1) + '%';
      }
    }

    /* ---- 环比矩阵：营业额行 ---- */
    var mx2 = $('.priority-matrix');
    if (mx2) {
      var cells = $$('.priority-matrix > b, .priority-matrix > span');
      // 结构：b(指标) span(上周) span(本周) span(变化) 循环；找营业额那一组
      var kids = Array.prototype.slice.call(mx2.children);
      for (var i3 = 0; i3 < kids.length; i3++) {
        if (kids[i3].tagName === 'B' && /营业额/.test(kids[i3].textContent)) {
          kids[i3].innerHTML = '营业额（' + s.tw.n + ' 天）';
          if (kids[i3 + 1]) kids[i3 + 1].innerHTML = wan(s.same.t, 2) + '万';
          if (kids[i3 + 2]) kids[i3 + 2].innerHTML = wan(s.tw.t, 2) + '万';
          if (kids[i3 + 3]) {
            kids[i3 + 3].className = (s.delta == null ? '' : (s.delta >= 0 ? 'good' : 'bad'));
            kids[i3 + 3].innerHTML = s.delta == null ? '—' : sign(s.delta, 1) + '%';
          }
          break;
        }
      }
      var sumP = $('.priority-summary');
      if (sumP && s.delta != null) {
        sumP.textContent = sumP.textContent.replace(/营业额[^；。]*[；。]/, '');
      }
      var pmBadge = $('.priority-compare .mkt-badge');
      if (pmBadge && s.delta != null) pmBadge.textContent = '营业额 ' + sign(s.delta, 1) + '%';
      var pmP = $('.priority-compare .mkt-card-head p');
      if (pmP) pmP.textContent = shortRange(s.twDays) + ' 与上一期同期 ' + shortRange(s.sameDays) + ' 同口径（各 ' + s.tw.n + ' 天）';
      /* ⚠ 只更新「营业额」这一行（营收日报是其唯一来源，原有代码已处理）。
         「营销入院 / 营销对接」是管家台账口径、不由营收日报驱动，不要在这里改，
         否则会把 4→8 的管家口径偷偷换成全院入院口径。 */
    }

    /* ---- 分析横幅 ---- */
    var ban = $('.mkt-analysis-banner');
    if (ban) {
      ban.innerHTML = '<i>!</i><div><b>月度营收' + (s.monthClosed ? '已收官 · 未达目标' : (diff > 5 ? '已进入高风险区' : '进度跟踪')) + '</b><span>累计' + wan(s.mtd.t, 2) + '万，完成' + s.pct.toFixed(1) + '%；'
        + (s.monthClosed
          ? (MONTH_LABEL + '已收官，缺口' + num(s.leftAmt, 2) + '万。本期日均' + num(s.twAvg, 2) + '万。')
          : ('剩余' + s.leftDays + '天需' + num(s.leftAmt, 2) + '万。当前日均' + num(s.twAvg, 2) + '万，'
             + (s.gap > 0 ? '距离达标所需日均' + num(s.need, 2) + '万仍差' + num(s.gap, 2) + '万。' : '已高于达标所需日均' + num(s.need, 2) + '万。')))
        + '</span></div>';
    }

    /* ---- 经营问题总览：风险卡 / 诊断 / 链路 ---- */
    var risks = $$('.dc-risk');
    if (risks[0]) {
      var lab = risks[0].querySelector('label'), st = risks[0].querySelector('strong'), p = risks[0].querySelector('p');
      if (lab) lab.textContent = '月目标风险';
      if (st) st.textContent = (diff >= 0 ? '落后' : '领先') + Math.abs(diff).toFixed(1) + 'pt';
      if (p) p.textContent = '累计' + wan(s.mtd.t, 2) + '万（' + (s.cut ? (+s.cut.slice(5, 7)) + '.' + (+s.cut.slice(8)) : '—') + '），剩余' + s.leftDays + '天还需' + num(s.leftAmt, 2) + '万，日均缺口' + num(Math.max(0, s.gap), 2) + '万。';
    }
    var detail = $$('.dc-item');
    if (detail[0]) {
      var dp = detail[0].querySelector('p');
      if (dp) dp.innerHTML = '完成率<b>' + s.pct.toFixed(1) + '%</b>' + (diff >= 0 ? '低于' : '高于') + '时间进度' + s.timePct.toFixed(1) + '%。本期日均' + num(s.twAvg, 2) + '万（' + shortRange(s.twDays) + (s.missing.length ? '，' + shortRange(s.missing) + ' 待补' : '') + '），'
        + (s.delta == null ? '暂无同期对照' : '较上一期同期' + wan(s.same.t, 2) + '万' + (s.delta >= 0 ? '增长' : '下降') + Math.abs(s.delta).toFixed(1) + '%') + '；即使恢复到上周水平，也难以自然完成目标，必须明确新增收入来源。';
    }
    var chain = $$('.dc-node');
    if (chain.length) {
      var last = chain[chain.length - 1].querySelector('span');
      if (last) last.textContent = '营收日报日均' + num(s.twAvg, 2) + '万（' + (s.revCut ? (+s.revCut.slice(5, 7)) + '.' + (+s.revCut.slice(8)) : '—') + ' 止），达标需' + num(s.need, 2) + '万';
    }

    /* ---- 逐日经营判断 ---- */
    var insights = $$('.mkt-day-insight');
    if (insights.length >= 4 && s.rec7.length) {
      var minD = s.rec7[0], maxD = s.rec7[0];
      s.rec7.forEach(function (d) {
        var a = (daily[d][F_OUT] || 0) + (daily[d][F_INP] || 0);
        if (a < (daily[minD][F_OUT] || 0) + (daily[minD][F_INP] || 0)) minD = d;
        if (a > (daily[maxD][F_OUT] || 0) + (daily[maxD][F_INP] || 0)) maxD = d;
      });
      var minA = (daily[minD][F_OUT] || 0) + (daily[minD][F_INP] || 0);
      var maxA = (daily[maxD][F_OUT] || 0) + (daily[maxD][F_INP] || 0);
      insights[0].querySelector('b').textContent = (+minD.slice(5, 7)) + '.' + (+minD.slice(8)) + ' ' + dowOf(minD) + '仅' + wan(minA, 2) + '万';
      insights[1].querySelector('b').textContent = (+maxD.slice(5, 7)) + '.' + (+maxD.slice(8)) + ' ' + dowOf(maxD) + '贡献' + (maxA / s.rec7Agg.t * 100).toFixed(1) + '%';
      var g4 = insights[3];
      if (g4) {
        g4.querySelector('b').textContent = '本期营收已有及时口径';
        g4.querySelector('span').textContent = shortRange(s.twDays) + '合计' + wan(s.tw.t, 2) + '万、日均' + num(s.twAvg, 2) + '万'
          + (s.delta == null ? '' : '，比上一期同期' + (s.delta >= 0 ? '增长' : '下降') + Math.abs(s.delta).toFixed(1) + '%')
          + (s.missing.length ? '（' + shortRange(s.missing) + ' 日报待补）' : '') + '。';
      }
    }

    /* ---- 营销 6 项 KPI：本期（营收日报口径，含入出院与门诊） ---- */
    /* ⚠ 标签也必须一起写：本组 6 格原先由「经营问题总览」模块写成
       客服随访 / 标记到院 / 营销接触 / 营销入院 / 营销转化 / 在院参考，
       而这里只写值（门诊收入 / 住院收入 / 初诊 …）→ 出现「客服随访 ¥11.16万」这类
       标签与数值错位。营收日报只能提供收入与就诊人次，故标签一并改为其口径。 */
    var kpis = $$('.mkt-kpis .mkt-kpi');
    if (kpis.length >= 6 && s.tw.t) {
      var t1 = s.tw, P1 = t1.p;
      var conv = P1.cover.first === t1.n && P1.first > 0 ? P1.admit / P1.first * 100 : null;
      var dspan = shortRange(s.twDays) + '（' + t1.n + ' 天）';
      var outN = (P1.cover.first === t1.n && P1.cover.again === t1.n) ? (P1.first + P1.again) : null;
      var kvals = [
        ['门诊收入', '¥' + wan(t1.o, 2) + '万', '占本期收入 ' + (t1.o / t1.t * 100).toFixed(1) + '%'],
        ['住院收入', '¥' + wan(t1.i, 2) + '万', '占本期收入 ' + (t1.i / t1.t * 100).toFixed(1) + '%'],
        ['门诊人次', outN == null ? '待补' : outN + '人',
         outN == null ? '初诊/复诊待补' : ('初诊 ' + P1.first + ' ＋ 复诊 ' + P1.again)],
        ['本期入院', P1.admit + '人',
         conv == null ? dspan : (dspan + ' · 初诊转入院 ' + conv.toFixed(1) + '%')],
        ['本期出院', P1.disch + '人', dspan],
        ['在院', P1.inhos == null ? '待补' : P1.inhos + '人',
         P1.inhosAt ? ((+P1.inhosAt.slice(5, 7)) + '.' + (+P1.inhosAt.slice(8))) + ' 最新时点' : '待补']
      ];
      kpis.slice(0, 6).forEach(function (k, i) {
        var hd1 = k.querySelector('.mkt-kpi-head');
        var st1 = k.querySelector('strong'), sp1 = k.querySelector('span');
        if (hd1 && hd1.lastChild && hd1.lastChild.nodeType === 3) hd1.lastChild.nodeValue = kvals[i][0];
        else if (hd1) hd1.insertAdjacentText('beforeend', kvals[i][0]);
        if (st1) st1.textContent = kvals[i][1];
        if (sp1) sp1.textContent = kvals[i][2];
      });
    }

    /* ---- 转化漏斗：本期 ---- */
    if (s.tw.t) {
      var P2 = s.tw.p;
      var fbox = $$('.mkt-flow-box');
      if (fbox.length >= 2) {
        var fb1 = fbox[0].querySelector('b'), fb2 = fbox[1].querySelector('b');
        if (fb1) fb1.textContent = P2.first;
        if (fb2) fb2.textContent = P2.admit;
      }
      var outs = $$('.mkt-outflow');
      if (outs.length >= 2) {
        var s1 = outs[0].querySelector('span'), v1 = outs[0].querySelector('b');
        var s2 = outs[1].querySelector('span'), v2 = outs[1].querySelector('b');
        if (s1) s1.textContent = '初诊转入院';
        if (v1) v1.textContent = P2.first > 0 ? (P2.admit / P2.first * 100).toFixed(1) + '%' : '—';
        if (s2) s2.textContent = '本期出院';
        if (v2) v2.textContent = P2.disch + '人';
      }
      var flowCard = $$('.mkt-card').filter(function (c) { return c.querySelector('.mkt-flow'); })[0];
      if (flowCard && flowCard.querySelector('.mkt-card-head p')) {
        flowCard.querySelector('.mkt-card-head p').textContent = '本期 ' + shortRange(s.twDays) + ' · 出院独立作为患者池流出';
      }
    }

    /* ---- 口径说明 ---- */
    var src = $('.mkt-source');
    if (src) {
      var P3 = s.tw.p;
      src.textContent = '口径：本期 ' + shortRange(s.twDays) + '（各源数据截至 ' + cutTxt + '，营收日报至 ' + revTxt + '）＝营业额 ' + wan(s.tw.t, 2) + ' 万（门诊 ' + wan(s.tw.o, 2) + ' ＋ 住院 ' + wan(s.tw.i, 2) + '）、初诊 ' + P3.first + ' 人、入院 ' + P3.admit + ' 人、出院 ' + P3.disch + ' 人'
        + (P3.inhosAt ? '，' + ((+P3.inhosAt.slice(5, 7)) + '.' + (+P3.inhosAt.slice(8))) + ' 在院 ' + P3.inhos + ' 人' : '')
        + '；对照上一期同期 ' + shortRange(s.sameDays) + '（' + wan(s.same.t, 2) + ' 万）。上一期完整 ' + shortRange(s.lwDays) + ' 营收 ' + wan(s.lw.t, 2) + ' 万。月度目标 ' + MONTH_TARGET + ' 万，累计 ' + wan(s.mtd.t, 2) + ' 万（' + (s.cut ? (+s.cut.slice(5, 7)) + '月' + (+s.cut.slice(8)) + '日' : '—') + '）。导入新数据后先校验冲突，再更新看板。';
    }

    /* ---- 数据口径风险卡里的营收部分 ---- */
    $$('.mkt-data-warning p').forEach(function (e) {
      e.innerHTML = e.innerHTML.replace(/营收日报[^；。]*[；。]/, '营收日报已更新至 ' + revTxt + '；');
    });

    /* ---- 主面板（概览 Hero + 营收目标卡）----
       ⛔ 2026-10-19 业主指令：医生组首页严格按《特别行动小组汇报表》填报条目。
         原先这里用营收日报覆盖 Hero 的入院 / 出院 / 门诊三格（会盖成 13 / 12 / 123 与「6 天」，
         与主表 19 / 17 / 210 直接打架），也把目标卡改成营收日报累计。
         现改为**不覆盖**：Hero 与目标卡统一由 live-sync.js 按主表快照渲染，
         静态兜底也已是主表值。此函数保留但不再调用，营收日报只用于逐日图与勾稽。
    renderMainPanel(daily, s); */
    void renderMainPanel;
    try { window.dispatchEvent(new CustomEvent('ops:revenue-updated', { detail: s })); } catch (e) { }
  }

  /* 主面板同步：营收日报 → Hero 五指标 + 9 月营收目标进度卡。
     为什么要有这个函数：这些节点原先在 index.html 里是写死的字面量，
     导入营收图片后不会变（业主 2026-09-26 反馈「拖进来了但数据没更新」）。 */
  function renderMainPanel(daily, s) {
    var tw = s.tw, P = tw.p, cut = s.cut;
    var cn = function (d) { return d ? ((+d.slice(5, 7)) + '月' + (+d.slice(8)) + '日') : '—'; };

    /* ---- ① Hero 五指标：在院 / 入院 / 出院 / 门诊 / 物理治疗 ---- */
    var kpis = $$('#heroKpis .ov-kpi');
    if (kpis.length >= 5) {
      var days = s.twDays || [];
      var span = days.length ? (shortRange(days) + '（' + days.length + ' 天）') : '—';
      // 门诊人次 = 初诊 ＋ 复诊（营收日报「门诊」下的两列）
      var outPat = (P.cover.first === tw.n && P.cover.again === tw.n) ? (P.first + P.again) : null;
      var vals = [
        ['在院人数', P.inhos == null ? '—' : String(P.inhos), '人',
         P.inhosAt ? ('最新时点 ' + ((+P.inhosAt.slice(5, 7)) + '.' + (+P.inhosAt.slice(8)))) : '待补'],
        ['本期入院', String(P.admit), '人', span],
        ['本期出院', String(P.disch), '人', span],
        ['门诊', outPat == null ? '—' : String(outPat), '人',
         outPat == null ? '本期初诊/复诊待补' : (span + ' 营收日报')],
        ['物理治疗', null, null, null]      // 资产表口径，营收日报不含 → 不动
      ];
      kpis.slice(0, 5).forEach(function (k, i) {
        var v = vals[i];
        if (v[1] === null) return;          // 物理治疗保持原值
        var lab = k.querySelector('label'), st = k.querySelector('strong'), sp = k.querySelector('.ov-chip');
        if (lab) lab.textContent = v[0];
        if (st) st.innerHTML = v[1] + '<em>' + v[2] + '</em>';
        if (sp) sp.textContent = v[3];
      });
    }

    /* ---- ② 月度营收目标进度卡（结算月）---- */
    var tp = s.timePct, pc = s.pct, diff = tp - pc;
    var chip = $('.ov-t-head .ov-chip');
    if (chip) chip.innerHTML = MONTH_LABEL_TIGHT + '1日—' + cn(cut) + ' <i>⌄</i>';
    var amt = $('.ov-amount');
    if (amt) amt.innerHTML = '<strong>' + wan(s.mtd.t, 2) + '</strong><em>／' + MONTH_TARGET + '万</em>';
    var bar = $('.ov-bar');
    if (bar) {
      bar.setAttribute('aria-label', '营收完成率 ' + pc.toFixed(1) + '%，时间进度 ' + tp.toFixed(1) + '%');
      var i1 = bar.querySelector('i'), u1 = bar.querySelector('u');
      if (i1) i1.style.width = Math.max(0, Math.min(100, pc)).toFixed(1) + '%';
      if (u1) u1.style.left = Math.max(0, Math.min(100, tp)).toFixed(1) + '%';
    }
    var two = $$('.ov-two > div > b');
    if (two.length >= 3) {
      two[0].textContent = pc.toFixed(1) + '%';
      two[1].textContent = tp.toFixed(1) + '%';
      two[2].textContent = (diff >= 0 ? '落后 ' : '领先 ') + Math.abs(diff).toFixed(1) + 'pt';
      two[2].className = diff >= 0 ? 'neg' : 'pos';
    }
    var gap = $('.ov-gap');
    if (gap) {
      if (s.monthClosed) {
        /* 月末收官：`剩余 0 天 / 日均需 0.00 万` 会误导，改为缺口口径 */
        gap.innerHTML = '<b>' + MONTH_LABEL + '已收官</b>（' + s.cutD + '/' + MONTH_DAYS + ' 天）：累计 <b>' + num(s.mtd.t / 10000, 2) + ' 万</b>，'
          + '完成目标 <b>' + s.pct.toFixed(1) + '%</b>，缺口 <b>' + num(s.leftAmt, 2) + ' 万</b>；'
          + '上一期日均 <b>' + num(s.lwAvg / 10000, 2) + ' 万</b>、'
          + '本期（' + shortRange(s.twDays) + '）日均 <b>' + num(s.twAvg, 2) + ' 万</b>。';
      } else {
        gap.innerHTML = '剩余 <b>' + s.leftDays + '</b> 天需 <b>' + num(s.leftAmt, 2) + ' 万</b>，'
          + '日均需 <b>' + num(s.need, 2) + ' 万</b>；上一期日均 <b>' + num(s.lwAvg / 10000, 2) + ' 万</b>、'
          + '本期（' + shortRange(s.twDays) + '）日均 <b>' + num(s.twAvg, 2) + ' 万</b>，'
          + (s.gap > 0 ? ('缺口 <b>' + num(s.gap, 2) + ' 万</b>。') : ('已高于达标日均 <b>' + num(-s.gap, 2) + ' 万</b>。'));
      }
    }
    var live = $$('.ov-live');
    live.forEach(function (e) {
      e.textContent = '每日 09:00 抓取 · 数据更新至 ' + (+s.globalCut.slice(5, 7)) + '.' + (+s.globalCut.slice(8));
    });
  }

// ============================================================================
//  图片识别（OCR）：营收日报截图 → 逐行营收与人数
//  策略：整图粗识别定位「列」→ 按列间隙分块 → 分块放大 14 倍精识别 → 合并重建
//  为什么这样做：本项目实测，同一张 848×244 的截图
//    · 整图 2.5~6 倍识别 → 数字大面积误识（"25904.97" → "s9008es"）
//    · 分块放大 14 倍识别 → "2026.9.23 25904.97 817.93 2 7" 基本全对
//  依赖：Tesseract.js（懒加载，fast 模型约 1.9MB，浏览器缓存后可复用）
// ============================================================================
  /* ⭐⭐⭐ 2026-10-09：改为**随看板本地发货**，不再依赖境外 CDN。
     ─────────────────────────────────────────────────────────────
     原先四个地址全在 cdn.jsdelivr.net / tessdata.projectnaptha.com。
     实测（最顺畅情况下）语言模型 1.98MB 就要 6.32s（314 KB/s），
     全链 6—7MB、冷态 20s+；国内网络访问 jsdelivr 常被限速甚至超时
     → 用户看到的就是「拖进去半天识别不出来」。
     现在同域加载（本次页面所在的域名），与看板一个包，跨境耗时归零。
     ⚠ core 用**目录**：浏览器会按 SIMD 支持自己选
       `tesseract-core-simd-lstm.wasm.js` 或 `tesseract-core-lstm.wasm.js`，两个都放了。 */
  var OCR_SRC = {
    js: './vendor/tesseract/tesseract.min.js',
    worker: './vendor/tesseract/worker.min.js',
    core: './vendor/tesseract',
    lang: './vendor/tesseract'
  };
  /* ⭐ 兜底：本地资源缺失（误删 / 未随包上传）时退回境外 CDN，
     宁可慢也不要整个功能不可用。 */
  var OCR_ALT = {
    js: 'https://cdn.jsdelivr.net/npm/tesseract.js@5.1.1/dist/tesseract.min.js',
    worker: 'https://cdn.jsdelivr.net/npm/tesseract.js@5.1.1/dist/worker.min.js',
    core: 'https://cdn.jsdelivr.net/npm/tesseract.js-core@5.1.1',
    lang: 'https://tessdata.projectnaptha.com/4.0.0_fast'
  };
  /* 语言模型不设 `.gz` 后缀——Tesseract 会按用途自行拼接（它自己带 gz）。 */
  var OCR_USING_ALT = false;
  var ocrWorker = null;              // 已就绪的 worker
  var ocrWorkerPromise = null;       // ⭐ 在途的「建 worker」promise（预热与拖图可能重叠，必须复用）
  var ocrQueue = Promise.resolve();  // ⭐ 串行队列：同一 worker 上禁止并发 recognize / setParameters
  var ocrGen = 0;                    // ⭐ 世代号：取消后自增，作废所有在途任务
  var ocrJob = null;                 // ⭐ 当前进度：{base, cur, total, shown, label}
  /* 引擎就绪总超时。本地化后同域加载应 <2s；留 60s 是为「走了境外兜底 + 网速差」的情况，
     比原先 90s 更快暴露问题，配合「取消识别」按钮可立刻重试。 */
  var OCR_ENGINE_TIMEOUT = 60000;

  /* ⭐ 统一的超时包装：Tesseract 的加载链路（脚本 → worker → wasm 核心 → 语言模型）
     任何一环卡住，原先都**没有任何报错**，页面就永久停在「加载识别引擎…」。 */
  function withTimeout(p, ms, msg) {
    var t;
    return Promise.race([
      p,
      new Promise(function (_, rej) { t = setTimeout(function () { rej(new Error(msg)); }, ms); })
    ]).then(function (v) { clearTimeout(t); return v; }, function (e) { clearTimeout(t); throw e; });
  }
  /* 插一个 <script> 并等它 onload。timeout 到期或 onerror 都算失败。 */
  function injectScript(src, timeoutMs) {
    return new Promise(function (res, rej) {
      var el = document.createElement('script');
      el.src = src; el.async = true;
      var done = false;
      var to = setTimeout(function () {
        if (done) return; done = true;
        rej(new Error('加载超时'));
      }, timeoutMs);
      el.onload = function () { if (done) return; done = true; clearTimeout(to); res(); };
      el.onerror = function () { if (done) return; done = true; clearTimeout(to); rej(new Error('加载失败')); };
      document.head.appendChild(el);
    });
  }
  /* ⭐ 两级加载：先本地（同域，应 <1s），失败再退回境外 CDN。
     本地超时给 12s（同域还取不到基本就是文件缺失）；境外给 25s。 */
  function loadScript(src) {
    if (typeof Tesseract !== 'undefined') return Promise.resolve();
    var local = (src === OCR_SRC.js);
    if (!local) return injectScript(src, 25000);
    return injectScript(OCR_SRC.js, 12000).catch(function () {
      OCR_USING_ALT = true;
      return injectScript(OCR_ALT.js, 25000).catch(function () {
        throw new Error('识别引擎加载失败（本地与备用源均不可用），请确认 vendor/tesseract 已随看板部署');
      });
    });
  }
  /* ⭐ 真百分比：块宽加权（宽块识别更久），块内再用 worker 自报 progress 插值。 */
  function ocrJobText(p) {
    if (!ocrJob) return '识别中…';
    var pct = ((ocrJob.base + ocrJob.cur * (p || 0)) / (ocrJob.total || 1)) * 100;
    return ocrJob.label + ' ' + Math.round(Math.max(0, Math.min(100, pct))) + '%';
  }
  /* ⭐ 取消入口：网络卡住时用户必须有路可退（原先只能刷新页面）。
     做法＝终止 worker + 世代号自增（在途任务全部作废）+ 清空在途 promise 以便重试。 */
  function ocrCancelBtn(on) {
    var el = document.getElementById('ocrStatus');
    if (!el) return;
    var b = document.getElementById('ocrCancel');
    if (!b) {
      b = document.createElement('button');
      b.id = 'ocrCancel'; b.type = 'button'; b.textContent = '取消识别';
      b.style.cssText = 'margin-left:10px;font-size:12px;padding:2px 10px;border:1px solid #C9D6E8;'
        + 'border-radius:999px;background:#fff;color:#0A54C4;cursor:pointer';
      b.onclick = function () { cancelOcr('已取消识别，可重新拖入'); };
      el.parentNode.insertBefore(b, el.nextSibling);
    }
    b.style.display = on ? '' : 'none';
  }
  function cancelOcr(msg) {
    ocrGen++;
    ocrQueue = Promise.resolve();
    try { if (ocrWorker) ocrWorker.terminate(); } catch (e) { }
    ocrWorker = null; ocrWorkerPromise = null; ocrJob = null;
    ocrCancelBtn(false);
    ocrProgress(msg || '已取消');
  }
  function ocrProgress(txt) {
    var el = document.getElementById('ocrStatus');
    if (el) { el.textContent = txt; el.style.display = txt ? '' : 'none'; }
  }
  function getWorker(silent) {
    if (ocrWorker) return Promise.resolve(ocrWorker);
    /* ⭐ 复用在途 promise：预热与用户拖图可能同时触发，不复用会建出两个 worker（内存翻倍、互相打架） */
    if (ocrWorkerPromise) return ocrWorkerPromise;
    if (!silent) ocrProgress('正在准备识别引擎（首次需初始化，约十几秒；之后约 1 秒）…');
    ocrWorkerPromise = loadScript(OCR_SRC.js).then(function () {
      if (typeof Tesseract === 'undefined') throw new Error('识别引擎未就绪');
      /* ⭐ 若上一步走的是境外兜底，worker/core/模型也要跟着用境外的，
         否则会「JS 从境外来、资源找本地」→ 本地缺失时二次失败。 */
      var S = OCR_USING_ALT ? OCR_ALT : OCR_SRC;
      return Tesseract.createWorker('eng', 1, {
        workerPath: S.worker, corePath: S.core, langPath: S.lang,
        logger: function (m) {
          if (silent) return;
          if (m.status === 'loading tesseract core') ocrProgress('初始化识别核心…');
          else if (m.status === 'loading language traineddata') ocrProgress('加载数字识别模型…');
          else if (m.status === 'initializing api') ocrProgress('初始化…');
          else if (m.status === 'recognizing text') ocrProgress(ocrJobText(m.progress || 0));
        }
      });
    }).then(function (w) {
      /* 这组参数是实测调出来的：
         · user_defined_dpi 不设时 Tesseract 会按 70dpi 处理小图，字符被过度降采样
         · psm 11 = 稀疏文本。⭐ 实测关键：营收日报每个数字都被表格横线隔开，
           用 psm 6（单一均匀文本块）会把它们当噪声整块丢弃（门诊收入列 0/7），
           切 psm 11 后六列金额全部 7/7。窄列在 psm 11 下不足时由块内回退 psm 6。
         · preserve_interword_spaces 让邻列数字不会被粘成一个 token */
      return w.setParameters({
        user_defined_dpi: '300',
        tessedit_pageseg_mode: '11'
      }).then(function () { ocrWorker = w; return w; });
    });
    /* ⭐ 整链路超时：脚本/worker/wasm/模型 任一环挂住都要给出明确错误，而不是无限等待。
       失败时清空在途 promise → 用户重拖即重新尝试。 */
    ocrWorkerPromise = withTimeout(ocrWorkerPromise, OCR_ENGINE_TIMEOUT,
      '加载识别引擎超时（60 秒）。请点「取消识别」后重试；若反复失败，请检查本机网络。')
      .catch(function (e) {
        ocrWorkerPromise = null; ocrJob = null; ocrCancelBtn(false); ocrProgress('');
        throw e;
      });
    return ocrWorkerPromise;
  }
  /* ⭐ 串行排队：同一 worker 上并发 recognize / setParameters 会互相污染
     （psm 从 11 被切成 6 又不切回来），连拖多张时会又慢又错。 */
  function queueOcr(fn) {
    var run = ocrQueue.then(fn, fn);
    ocrQueue = run.catch(function () { });   // 单张失败不阻塞后续
    return run;
  }

  /* ---- 图像处理 ---- */
  function imgToCanvas(img, scale) {
    var c = document.createElement('canvas');
    c.width = Math.max(1, Math.round(img.width * scale));
    c.height = Math.max(1, Math.round(img.height * scale));
    var g = c.getContext('2d');
    g.imageSmoothingEnabled = true; g.imageSmoothingQuality = 'high';
    g.fillStyle = '#fff'; g.fillRect(0, 0, c.width, c.height);
    g.drawImage(img, 0, 0, c.width, c.height);
    return c;
  }
  /* 直接从原图裁剪并缩放：避免先放大整图（848×244 放大 16 倍 = 13568×3904，
     接近浏览器 canvas 上限，会导致 drawImage 静默失败、块全黑 → 识别不到任何内容） */
  function cropScale(img, x0, x1, scale, binarize, y0, y1) {
    /* y0/y1 可选：只裁剪竖直方向的一段（用于跳过顶部标题与表头） */
    var Y0 = (y0 == null ? 0 : Math.max(0, Math.round(y0)));
    var Y1 = (y1 == null ? img.height : Math.min(img.height, Math.round(y1)));
    if (Y1 - Y0 < 4) { Y0 = 0; Y1 = img.height; }
    var c = document.createElement('canvas');
    c.width = Math.max(1, Math.round((x1 - x0) * scale));
    c.height = Math.max(1, Math.round((Y1 - Y0) * scale));
    var g = c.getContext('2d');
    g.imageSmoothingEnabled = true; g.imageSmoothingQuality = 'high';
    g.fillStyle = '#fff'; g.fillRect(0, 0, c.width, c.height);
    g.drawImage(img, x0, Y0, Math.max(1, x1 - x0), Math.max(1, Y1 - Y0), 0, 0, c.width, c.height);
    if (binarize) {
      /* Otsu 自适应阈值：微信压缩过的截图中数字边缘有灰阶噪点，二值化后 Tesseract 更稳 */
      try {
        var d = g.getImageData(0, 0, c.width, c.height), p = d.data;
        var hist = new Array(256).fill(0), n = c.width * c.height;
        var gray = new Uint8Array(n);
        for (var i = 0, j = 0; i < p.length; i += 4, j++) {
          var v = (p[i] * 0.299 + p[i + 1] * 0.587 + p[i + 2] * 0.114) | 0;
          gray[j] = v; hist[v]++;
        }
        var sum = 0; for (var t = 0; t < 256; t++) sum += t * hist[t];
        var sumB = 0, wB = 0, best = 0, thr = 128;
        for (var t2 = 0; t2 < 256; t2++) {
          wB += hist[t2]; if (!wB) continue;
          var wF = n - wB; if (!wF) break;
          sumB += t2 * hist[t2];
          var mB = sumB / wB, mF = (sum - sumB) / wF;
          var bt = wB * wF * (mB - mF) * (mB - mF);
          if (bt > best) { best = bt; thr = t2; }
        }
        for (var k = 0, j2 = 0; k < p.length; k += 4, j2++) {
          var b = gray[j2] > thr ? 255 : 0;
          p[k] = p[k + 1] = p[k + 2] = b; p[k + 3] = 255;
        }
        g.putImageData(d, 0, 0);
      } catch (e) { /* 二值化失败就用原图 */ }
    }
    return c;
  }
  function cropCanvas(canvas, x0, x1) {
    var c = document.createElement('canvas');
    c.width = Math.max(1, x1 - x0); c.height = canvas.height;
    var g = c.getContext('2d');
    g.fillStyle = '#fff'; g.fillRect(0, 0, c.width, c.height);
    g.drawImage(canvas, -x0, 0);
    return c;
  }
  function loadImg(src) {
    return new Promise(function (res, rej) {
      var i = new Image();
      i.onload = function () { res(i); };
      i.onerror = function () { rej(new Error('图片无法读取')); };
      i.src = src;
    });
  }

  /* ---- 表格结构分析：用「表格竖线」定列边界 ----
     为什么不用「列墨量低 → 判为间隙」：本类营收日报数字之间的空隙与列间空隙宽度相当，
     会把数字切两半（实测同一张 854×248 的图切出 43 列，切点落在数字中间）。
     而表格竖线是可靠的结构特征：
       ① 水平宽度极窄（1—3px）
       ② 在表格全高范围内几乎每一行都有墨
     实测：13 条竖线全部命中（另含左右边缘与初诊/复诊分隔线），与表头 14 列逐一对齐。
     返回 { cols:[列边界x…], charH:字符高, rows:数据行数, hlines:横线数 } */
  function analyzeTable(img) {
    var res = { cols: [], charH: 0, rows: 0, hlines: 0, dataTop: 0, dataBot: 0 };
    var c = document.createElement('canvas');
    c.width = img.width; c.height = img.height;
    var g = c.getContext('2d');
    g.fillStyle = '#fff'; g.fillRect(0, 0, c.width, c.height);
    g.drawImage(img, 0, 0);
    var d, p;
    try { d = g.getImageData(0, 0, c.width, c.height); p = d.data; } catch (e) { return res; }
    var W = c.width, H = c.height, x, y;
    /* 行墨量 → 横向表格线（>50% 图宽） */
    var rowInk = new Uint32Array(H);
    for (y = 0; y < H; y++) {
      var n = 0, base = y * W * 4;
      for (x = 0; x < W; x++) {
        var i2 = base + x * 4;
        if (p[i2] < 170 && p[i2 + 1] < 170 && p[i2 + 2] < 170) n++;
      }
      rowInk[y] = n;
    }
    var isLine = new Uint8Array(H), hlines = [];
    for (y = 0; y < H; y++) if (rowInk[y] > W * 0.5) { isLine[y] = 1; hlines.push(y); }
    res.hlines = hlines.length;
    if (hlines.length < 3) return res;                 // 没有表格结构 → 交给旧算法
    var top = hlines[0], bot = hlines[hlines.length - 1];
    var tableH = bot - top + 1;
    /* 数据行带：由横线分隔的连续墨行 */
    var bands = [], st = -1;
    for (y = top; y <= bot; y++) {
      var v = isLine[y] ? 0 : rowInk[y];
      if (v > 2) { if (st < 0) st = y; }
      else if (st >= 0) { if (y - st >= 6) bands.push([st, y - 1]); st = -1; }
    }
    if (st >= 0 && bot - st >= 6) bands.push([st, bot]);
    if (bands.length < 2) return res;
    res.rows = bands.length;
    /* 数据区：bands[0] 是表头带（可能含两行表头，如「出院 初次／多次」），
       数据从 bands[1] 开始。只识别这一段——否则每个块都会混进顶部标题与表头文字，
       噪声会把数据行的数字挤掉（实测：不裁剪时 parsed 仅 1 行、verified 0）。 */
    res.dataTop = Math.max(0, bands[1][0] - 3);
    res.dataBot = bot;
    /* 字符高：数据行带高度的中位数（块放大倍数按它算） */
    var hs = bands.map(function (b) { return b[1] - b[0] + 1; })
                  .sort(function (a, b) { return a - b; });
    res.charH = hs[Math.floor(hs.length / 2)] || 0;
    /* 每个 x 的「全高墨量」与「覆盖行带数」 */
    var full = new Uint32Array(W), cover = new Uint32Array(W);
    for (y = top; y <= bot; y++) {
      var b2 = y * W * 4;
      for (x = 0; x < W; x++) {
        var i3 = b2 + x * 4;
        if (p[i3] < 170 && p[i3 + 1] < 170 && p[i3 + 2] < 170) full[x]++;
      }
    }
    var nb = bands.length;
    for (var bi = 0; bi < nb; bi++) {
      var y0 = bands[bi][0], y1 = bands[bi][1];
      for (x = 0; x < W; x++) {
        for (y = y0; y <= y1; y++) {
          var i4 = (y * W + x) * 4;
          if (p[i4] < 170 && p[i4 + 1] < 170 && p[i4 + 2] < 170) { cover[x]++; break; }
        }
      }
    }
    /* 竖线候选：覆盖行带数 ≥ nb-1，按相邻 ≤2px 聚类 */
    var groups = [], cur = null;
    for (x = 0; x < W; x++) {
      if (cover[x] >= nb - 1) {
        if (cur && x - cur[cur.length - 1] <= 2) cur.push(x);
        else { cur = [x]; groups.push(cur); }
      }
    }
    var cols = [];
    groups.forEach(function (gr) {
      if (gr.length > 3) return;                       // 太宽 → 是数字内容，不是线
      var mx = 0;
      gr.forEach(function (xx) { if (full[xx] > mx) mx = full[xx]; });
      if (mx < tableH * 0.85) return;                  // 墨量不足 → 不是贯穿线
      cols.push(Math.round((gr[0] + gr[gr.length - 1]) / 2));
    });
    res.cols = cols;
    return res;
  }

  /* ---- 按「图像白列」找列切点（不依赖 OCR） ----
     思路同读带网格线的表格截图：逐列统计「有墨像素」占比，
     连续的低墨列就是列与列的间隙；在每段间隙的中间取切点。
     优点：与识别质量完全解耦；且能在数字之间切，不会切断数字。 */
  function inkCuts(img) {
    var c = document.createElement('canvas');
    c.width = img.width; c.height = img.height;
    var g = c.getContext('2d');
    g.fillStyle = '#fff'; g.fillRect(0, 0, c.width, c.height);
    g.drawImage(img, 0, 0);
    var d, p;
    try { d = g.getImageData(0, 0, c.width, c.height); p = d.data; } catch (e) { return []; }
    var W2 = c.width, H2 = c.height;
    var rowInk = new Uint32Array(H2);
    for (var y = 0; y < H2; y++) {
      var base = y * W2 * 4, n = 0;
      for (var x = 0; x < W2; x++) {
        var i2 = base + x * 4;
        /* 阈值 170：表格线与文字比纸底暗得多，取偏保守的门限，
           避免截图压缩的灰噪点把「空白列」填满 */
        if (p[i2] < 170 && p[i2 + 1] < 170 && p[i2 + 2] < 170) n++;
      }
      rowInk[y] = n;
    }
    /* ⭐ 关键一步：先找出「表格横线行」并排除。
       营收日报是带横线的表格，横线贯穿每一列 —— 不排除的话每一列都算「有墨」，
       一个列间隙都找不到。实测 854×248 的营收日报有 12 条横线，
       不排除时只剩 4 个空白列（于是切块错位，6 行日报只重建出 1 行）；
       排除后空白列结构立刻清晰，可切出 11 块。 */
    var lineThr = W2 * 0.5, isLine = new Uint8Array(H2), dataRows = 0;
    for (var y1 = 0; y1 < H2; y1++) {
      if (rowInk[y1] > lineThr) isLine[y1] = 1; else dataRows++;
    }
    if (dataRows < H2 * 0.3) {          // 极端情况（整幅都是线）：放弃这一步，按全图统计
      dataRows = H2;
      isLine = new Uint8Array(H2);
    }
    var colInk = new Uint32Array(W2);
    for (var y2 = 0; y2 < H2; y2++) {
      if (isLine[y2]) continue;
      var b2 = y2 * W2 * 4;
      for (var x2 = 0; x2 < W2; x2++) {
        var k2 = b2 + x2 * 4;
        if (p[k2] < 170 && p[k2 + 1] < 170 && p[k2 + 2] < 170) colInk[x2]++;
      }
    }
    var thr = Math.max(1, Math.round(dataRows * 0.02));   // 有墨行数 < 2% 视为空列
    var runs = [], st = -1;
    for (var x3 = 0; x3 < W2; x3++) {
      if (colInk[x3] <= thr) { if (st < 0) st = x3; }
      else { if (st >= 0) { runs.push([st, x3 - 1]); st = -1; } }
    }
    if (st >= 0) runs.push([st, W2 - 1]);
    /* 段宽阈值 0.8% 是实测出来的：0.6% 会把字符间的小间隙也当列间隙（切出 12 块、含伪列），
       1.0% 又会漏掉窄列（只剩 10 块）。0.8% 对本项目截图恰好切出 11 列且与表头对齐。 */
    var minGap = Math.max(3, Math.round(W2 * 0.005));
    var mids = [];
    runs.forEach(function (r) {
      if (r[1] - r[0] + 1 < minGap) return;
      var mid = Math.round((r[0] + r[1]) / 2);
      if (mid < W2 * 0.02 || W2 - mid < W2 * 0.02) return;   // 丢掉贴边留白
      mids.push(mid);
    });
    /* 合并过近的切点，保证每块有足够宽度供放大识别 */
    var minW2 = Math.max(24, Math.round(W2 * 0.035));
    var out = [];
    mids.forEach(function (m) {
      if (!out.length || m - out[out.length - 1] >= minW2) out.push(m);
    });
    return out;
  }

  /* ---- 把一块的识别结果转成带坐标的 token ---- */
  function wordsOf(data) {
    var o = [];
    var push = function (w) { if (w && w.text && w.bbox) o.push(w); };
    if (Array.isArray(data.words) && data.words.length) { data.words.forEach(push); return o; }
    (data.blocks || []).forEach(function (b) {
      (b.paragraphs || []).forEach(function (p) {
        (p.lines || []).forEach(function (l) { (l.words || []).forEach(push); });
      });
    });
    return o;
  }
  var MONEY_RE = /^-?\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{1,2})?$/;
  function numToken(t) {
    if (t == null) return null;
    var s = String(t).trim();
    if (!/\d/.test(s)) return null;
    var neg = /^[-−–—]/.test(s);
    s = s.replace(/^[-−–—]/, '').replace(/[^\d.,]/g, '');
    if (!s) return null;
    var v;
    if (/^\d{1,3}([.,]\d{3})+$/.test(s)) v = parseFloat(s.replace(/[.,]/g, ''));
    else if (/^\d+\.\d+$/.test(s)) v = parseFloat(s);
    else if (/^\d+$/.test(s)) v = parseFloat(s);
    else v = parseFloat(s.replace(/,/g, ''));
    if (!isFinite(v)) return null;
    return neg ? -v : v;
  }
  var DATE_RE = /(\d{4})\s*[.\-/年]\s*(\d{1,2})\s*[.\-/月]\s*(\d{1,2})/;
  function mkDate(y, mo, d) {
    y = +y; mo = +mo; d = +d;
    if (y < 2000 || y > 2100 || mo < 1 || mo > 12 || d < 1 || d > 31) return null;
    return y + '-' + p2(mo) + '-' + p2(d);
  }
  /* 鲁棒取日期：OCR 对 "2026.9.23" 的识别结果可能是
     "2026.9.23" / "2026 9 23" / "2026923"（丢点）/ "20260923"（补零） */
  function findDate(txt) {
    var t = String(txt || '');
    var m = t.match(/(20\d{2})\s*[.\-/年]\s*(\d{1,2})\s*[.\-/月]\s*(\d{1,2})/);
    if (m) { var r1 = mkDate(m[1], m[2], m[3]); if (r1) return r1; }
    // 年 + 无分隔的 3~4 位（月日）
    m = t.match(/(20\d{2})(\d{3,4})(?!\d)/);
    if (m) {
      var tail = m[2], cands = [];
      if (tail.length === 3) cands.push([+tail.charAt(0), +tail.slice(1)]);
      else cands.push([+tail.slice(0, 2), +tail.slice(2)], [+tail.charAt(0), +tail.slice(1, 3)]);
      for (var i = 0; i < cands.length; i++) {
        var r2 = mkDate(m[1], cands[i][0], cands[i][1]);
        if (r2) return r2;
      }
    }
    // 仅 "9.23"（表头区可能没有年份）
    m = t.match(/(?:^|\s)(\d{1,2})\s*[.\-/月]\s*(\d{1,2})(?!\d)/);
    if (m) { var r3 = mkDate(YEAR, m[1], m[2]); if (r3) return r3; }
    return null;
  }
  var YEAR = 2026;

  /* 三数关系判定：门诊 + 在院 = 当日合计。
     OCR 常整列丢失小数点（27228.16 → 2722816），因此对每个数再试 ×1 / ×0.01 / ×100，
     取「需要缩放次数最少」且能配平的组合 —— 这既救回丢点，又不会把无关数字硬凑。 */
  var SCALES = [1, 0.01, 100];
  function tryTriple(a, b, c) {
    var best = null;
    for (var i = 0; i < 3; i++) for (var j = 0; j < 3; j++) for (var k = 0; k < 3; k++) {
      var A = a * SCALES[i], B = b * SCALES[j], C = c * SCALES[k];
      if (A < 500 || B < 500 || C < 500) continue;
      if (A > 600000 || B > 600000 || C > 800000) continue;   // 单日营收量级上限
      var tol = Math.max(0.06, C * 0.0008);
      if (Math.abs(A + B - C) > tol) continue;
      var fixes = (i ? 1 : 0) + (j ? 1 : 0) + (k ? 1 : 0);
      if (!best || fixes < best.fixes) best = { A: A, B: B, C: C, fixes: fixes };
    }
    return best;
  }

  /* 金额归一：单日/累计都不超过 500 万，超过则视为整列丢了小数点 */
  function normMoney(v) { return Math.abs(v) > 5000000 ? v / 100 : v; }

  /* 已定合计时反求两加数（门诊/在院），同样允许小数点丢失的缩放恢复 */
  function pairSum(a, b, target) {
    var best = null;
    for (var i = 0; i < 3; i++) for (var j = 0; j < 3; j++) {
      var A = a * SCALES[i], B = b * SCALES[j];
      if (A < 500 || B < 500 || A > 600000 || B > 600000) continue;
      var tol = Math.max(0.06, target * 0.0008);
      if (Math.abs(A + B - target) > tol) continue;
      var fixes = (i ? 1 : 0) + (j ? 1 : 0);
      if (!best || fixes < best.fixes) best = { A: A, B: B, fixes: fixes };
    }
    return best;
  }

  /* ---- 按 y 聚行 ---- */
  function groupRows(tokens) {
    if (!tokens.length) return [];
    var a = tokens.slice().sort(function (x, y) { return (x.y - y.y) || (x.x - y.x); });
    var hs = a.map(function (t) { return t.h; }).sort(function (x, y) { return x - y; });
    var h = hs[Math.floor(hs.length / 2)] || 10;
    var tol = Math.max(6, h * 0.7);
    var rows = [];
    a.forEach(function (t) {
      var r = null;
      for (var i = 0; i < rows.length; i++) if (Math.abs(rows[i].cy - t.y) <= tol) { r = rows[i]; break; }
      if (!r) { r = { cy: t.y, ts: [] }; rows.push(r); }
      r.ts.push(t);
      r.cy = r.ts.reduce(function (s2, x) { return s2 + x.y; }, 0) / r.ts.length;
    });
    rows.sort(function (x, y) { return x.cy - y.cy; });
    rows.forEach(function (r) { r.ts.sort(function (x, y) { return x.x - y.x; }); });
    return rows;
  }
  /* ---- 按 x 聚类成列 ---- */
  function clusterCols(tokens, tol) {
    var xs = tokens.map(function (t) { return t.xc; }).sort(function (a, b) { return a - b; });
    if (!xs.length) return [];
    var cols = [], cur = [xs[0]];
    for (var i = 1; i < xs.length; i++) {
      if (xs[i] - cur[cur.length - 1] <= tol) cur.push(xs[i]);
      else { cols.push(cur); cur = [xs[i]]; }
    }
    cols.push(cur);
    return cols.map(function (g) { return g.reduce(function (a, b) { return a + b; }, 0) / g.length; });
  }

  /* ---- 主流程 ---- */
  function ocrRevenueImage(src, onNote) {
    var imgW = 0, note = onNote || function () { };
    return loadImg(src).then(function (img) {
      imgW = img.width;
      return getWorker().then(function (w) { return { w: w, img: img }; });
    }).then(function (ctx) {
      var w = ctx.w, img = ctx.img;
      /* ① 粗识别：只为定位「列」，不取数值 */
      ocrJob = { base: 0, cur: 1, total: 1, shown: 0, label: '定位表格结构' };
      ocrProgress(ocrJobText(0));
      var scaleCoarsePre = Math.min(3, Math.max(1.5, 2200 / img.width));
      return w.recognize(imgToCanvas(img, scaleCoarsePre), {}, { blocks: true, text: true })
        .then(function (r) {
          var raw = wordsOf(r.data).map(function (x) {
            return { x: x.bbox.x0, xc: (x.bbox.x0 + x.bbox.x1) / 2, y: (x.bbox.y0 + x.bbox.y1) / 2,
                     w: x.bbox.x1 - x.bbox.x0, h: x.bbox.y1 - x.bbox.y0, text: x.text };
          });
          var scaleCoarse = scaleCoarsePre;
          // 还原到原图坐标
          raw.forEach(function (t) { t.x /= scaleCoarse; t.xc /= scaleCoarse; t.y /= scaleCoarse; t.h /= scaleCoarse; t.w /= scaleCoarse; });
          return { w: w, img: img, coarse: raw };
        });
    }).then(function (ctx) {
      var w = ctx.w, img = ctx.img, coarse = ctx.coarse;
      /* ② 由粗识别结果推出列位置，进而在「列间隙」处切块（不会切断数字） */
      var W = imgW;
      /* 关键：用 token 的左右边界求「真实空隙」，切点只落在空隙里，绝不切断数字。
         早期版本用「列中心的中点」当切点，实测会把 "2026.9.23" 从中间切开。 */
      var tk = coarse.filter(function (t) { return /\d/.test(t.text) && t.h > 0; })
                     .sort(function (a, b) { return a.x - b.x; });
      /* 字符高度中位数：Tesseract 的最佳字符高度约 30—40px，
         过度放大（如 ×15 得 150px）会触发内部降采样，识别反而变差 */
      var hArr = coarse.filter(function (t) { return t.h > 0; })
                       .map(function (t) { return t.h; }).sort(function (a, b) { return a - b; });
      var medH = hArr.length ? hArr[Math.floor(hArr.length / 2)] : 10;

      /* ⭐ 切点优先来自「图像白列」，不依赖粗识别。
         原先只用 OCR token 的空隙算切点：一旦粗识别把数字读错（微信压缩图上很常见），
         token 位置就跟着错 → 切点落到数字中间 → 整行报废。
         实测 854×248 的营收日报：token 法只切出 4 块（bounds 274/490/647），
         日期列被 0—274 那块切成两半，6 行日报最终只重建出 1 行。
         白列法按像素找列与列之间的空白，与识别质量无关，同一张图能切出 12 列。 */
      /* ⭐ 优先用「表格竖线」定列（见 analyzeTable 的说明）；
         竖线法不适用于非表格图时，逐级回退到旧的白列法 / token 法。 */
      var tbl = analyzeTable(img);
      var charH = tbl.charH || medH || 10;
      var cuts = tbl.cols;
      var cutSrc = 'vline';
      if (cuts.length < 2) { cuts = inkCuts(img); cutSrc = 'ink'; }
      if (cuts.length < 2) {
        cutSrc = 'token';
        var groups = [];
        tk.forEach(function (t) {
          var right = t.x + (t.w || t.h * 0.6 * String(t.text).length);
          var g = groups[groups.length - 1];
          if (g && t.x <= g.x1 + Math.max(3, t.h * 0.45)) g.x1 = Math.max(g.x1, right);
          else groups.push({ x0: t.x, x1: right });
        });
        var gaps = [];
        for (var gi = 1; gi < groups.length; gi++) {
          var ga = groups[gi - 1].x1, gb = groups[gi].x0;
          if (gb - ga > Math.max(3, W * 0.004)) gaps.push({ c: (ga + gb) / 2, w: gb - ga });
        }
        gaps.sort(function (a, b) { return b.w - a.w; });
        var minW = W * 0.17;
        gaps.forEach(function (g) {
          if (cuts.every(function (c) { return Math.abs(c - g.c) >= minW; }) && g.c >= minW && W - g.c >= minW) cuts.push(g.c);
        });
        cuts.sort(function (a, b) { return a - b; });
      }
      if (cuts.length < 2) { cuts = [Math.round(W / 3), Math.round(W * 2 / 3)]; cutSrc = 'fallback'; }
      try {
        window.__ocrCuts = { src: cutSrc, cuts: cuts.map(function (c) { return Math.round(c); }),
                             charH: charH, rows: tbl.rows, hlines: tbl.hlines };
      } catch (e) { }
      var bounds = [0].concat(cuts).concat([W]);
      var blocks = [];
      for (var b = 0; b < bounds.length - 1; b++) {
        var x0 = bounds[b], x1 = bounds[b + 1];
        if (x1 - x0 < W * 0.03) continue;
        /* 留少量重叠，避免边界数字被切断。
           竖线法的边界本身就是表格线（数字不会压线），故重叠只需 3%、下限 2px；
           用旧白列法时切点可能略偏，留同样比例也够（旧版曾用全图宽 6% = 51px，过大）。 */
        var ov = Math.max(2, Math.round((x1 - x0) * 0.03));
        blocks.push({ x0: Math.max(0, x0 - (b ? ov : 0)), x1: Math.min(W, x1 + (b < bounds.length - 2 ? ov : 0)) });
      }
      note('识别中：' + blocks.length + ' 块');
      /* ⭐ 识别阶段的进度按「块宽加权」——宽块识别更久，等权会明显偏快再突然不动。
         块内用 worker 自报的 progress 插值，所以百分比是连续走的，不再只有 8/14 这种跳变。 */
      var _totW = 0;
      blocks.forEach(function (b) { _totW += (b.x1 - b.x0); });
      ocrJob = { base: 0, cur: 0, total: _totW || 1, shown: 0, label: '识别中' };
      /* ③ 逐块放大识别 */
      var collected = [];
      var blockTexts = [];
      var chain = Promise.resolve();
      /* 块识别结果的 token 抽取器（psm 11 与 psm 6 共用） */
      var extractTokens = function (r, bl, sc) {
        var got = [];
        wordsOf(r.data).forEach(function (x) {
          var raw = String(x.text || '').trim();
          if (!raw) return;
          var v = numToken(raw);
          if (DATE_RE.test(raw) || findDate(raw)) v = null;   // 日期不是金额
          if (v == null && !findDate(raw)) return;
          got.push({
            text: raw, v: v,
            x: bl.x0 + x.bbox.x0 / sc, xc: bl.x0 + (x.bbox.x0 + x.bbox.x1) / 2 / sc,
            /* y 要补回「数据区起点」的偏移，否则分组时会把不同行带串在一起 */
            y: (tbl.dataTop || 0) + (x.bbox.y0 + x.bbox.y1) / 2 / sc,
            h: (x.bbox.y1 - x.bbox.y0) / sc
          });
        });
        return got;
      };
      /* ⭐ 逐块「psm 11 优先 + 智能回退 psm 6」。为什么：
         psm 6 假定「单一均匀文本块」，会被表格横线分隔开的独立数字整块丢弃 ——
         实测对门诊收入 / 当月累计两列输出空串（0/7）；切到 psm 11（稀疏文本）后
         门诊收入 7/7、在院收入 7/7、当日合计 7/7、当月累计 7/7、
         门诊环比 7/7、在院环比 7/7，日期列 14 个日期全对。
         但 1—2 位小整数窄列（初诊 / 入院）反而 psm 6 更好（psm 11 上下文不足 → 0）。
         故：psm 11 读到的数字不足 3 个时，用 psm 6 重跑该块并取更优者。 */
      blocks.forEach(function (bl, idx) {
        chain = chain.then(function () {
          ocrJob.base = ocrJob.shown || 0;
          ocrJob.cur = bl.x1 - bl.x0;
          ocrProgress(ocrJobText(0));
          /* ⭐ 倍数按「字符高」定，不再按块宽凑 1200px。
             实测量化（854×248 营收日报，逐列裁剪）三次：
               · psm 6  ×2（字符高 40px）→ 门诊收入 1/2；×3 → 2/2
               · psm 11 ×3 → 六列金额全部 7/7；×4 / ×5 略降（当月累计出现 1369264 .20）
             原口径按块宽算会到 ×8（字符高 160px），明显过大。
             故取「目标字符高 60px」，并夹在 2—6 倍之间。 */
          var sc = Math.max(2, Math.min(6, Math.round(60 / Math.max(6, charH))));
          /* binarize 参数保留但默认关闭：实测对本项目这张微信压缩截图反而使日期列丢失 */
          var cv = cropScale(img, bl.x0, bl.x1, sc, false, tbl.dataTop, tbl.dataBot);
          var OCRD = { blocks: true, text: true };
          return w.recognize(cv, {}, OCRD).then(function (r) {
            var g1 = extractTokens(r, bl, sc);
            var n1 = g1.filter(function (t) { return t.v != null; }).length;
            blockTexts.push('[11/' + idx + '] ' + String(r.data.text || '').replace(/\n+/g, ' | ').slice(0, 130));
            if (n1 >= 3) return g1;                      // psm 11 已读够 → 不回退
            return w.setParameters({ tessedit_pageseg_mode: '6' }).then(function () {
              return w.recognize(cv, {}, OCRD);
            }).then(function (r2) {
              var g2 = extractTokens(r2, bl, sc);
              var n2 = g2.filter(function (t) { return t.v != null; }).length;
              blockTexts.push('[6/' + idx + '] ' + String(r2.data.text || '').replace(/\n+/g, ' | ').slice(0, 130));
              return (n2 > n1) ? g2 : g1;
            }).then(function (best) {
              return w.setParameters({ tessedit_pageseg_mode: '11' }).then(function () { return best; });
            });
          }).then(function (got) {
            got.forEach(function (t) { collected.push(t); });
            ocrJob.shown = (ocrJob.base || 0) + (ocrJob.cur || 0);   // 本块完成 → 累计前进
          });
        });
      });
      return chain.then(function () {
        return { img: img, tokens: collected,
                 meta: { blocks: blocks.length, bounds: bounds, coarse: coarse.length,
                         texts: blockTexts, medH: medH } };
      });
    }).then(function (ctx) {
      /* ④ 去重（重叠区会产生重复 token） */
      var toks = ctx.tokens.slice().sort(function (a, b) { return (a.xc - b.xc); });
      var kept = [];
      toks.forEach(function (t) {
        for (var i = 0; i < kept.length; i++) {
          var k = kept[i];
          if (Math.abs(k.xc - t.xc) < Math.max(4, t.h * 0.5) && Math.abs(k.y - t.y) < Math.max(4, t.h * 0.7)) {
            // 同位置：取更长的数字文本（重叠切割常导致残缺）
            if (String(t.text).replace(/\D/g, '').length > String(k.text).replace(/\D/g, '').length) kept[i] = t;
            return;
          }
        }
        kept.push(t);
      });
      /* ⑤ 重建表格 */
      var rows = groupRows(kept);
      var out = [], lastDate = null;
      rows.forEach(function (r) {
        var joined = r.ts.map(function (t) { return t.text; }).join(' ');
        var ds = findDate(joined);
        if (!ds) {
          /* 日期列被 OCR 吃掉时无法可靠定位是哪一天 —— 曾按「上一行 +1」推断，
             实测把 9.24 误标成 9.21，因此不再推断：保留该行数值、日期留空，由用户指定。 */
          var nv = r.ts.filter(function (t) { return t.v != null && Math.abs(t.v) >= 500; }).sort(function (a, b) { return b.v - a.v; });
          if (nv.length < 2) return;
          out.push({
            date: '', raw: joined.slice(0, 140), verified: false, undated: true,
            out: normMoney(nv[nv.length - 1].v), inp: normMoney(nv[nv.length - 2].v),
            nums: r.ts.filter(function (t) { return t.v != null; }).map(function (t) { return { v: t.v, xc: t.xc }; })
          });
          return;
        }
        var nums = r.ts.filter(function (t) { return t.v != null && Math.abs(t.v) >= 0.005; });
        /* 三数自校验：门诊 + 在院 = 当日合计 —— 语言无关，可定位并自证 */
        var best = null;
        for (var i = 0; i < nums.length; i++) for (var j = i + 1; j < nums.length; j++) for (var k = 0; k < nums.length; k++) {
          if (k === i || k === j) continue;
          var A = nums[i], B = nums[j], C = nums[k];
          var fit = tryTriple(A.v, B.v, C.v);
          if (!fit) continue;
          var sc = fit.C - fit.fixes * 1e9;   // 优先「缩放次数少」，其次合计更大
          if (!best || sc > best.sc) best = { A: A, B: B, C: C, fit: fit, sc: sc };
        }
        var rec = {
          date: ds,
          raw: joined.slice(0, 140), verified: !!best,
          /* ⭐ 2026-10-09：nums **无条件**保存。
             原先只在三数自校验成功时才挂 nums，导致「校验失败→金额留空」
             连兜底都拿不到数字（下文 ③ 的兜底需要它）。 */
          nums: nums.map(function (t) { return { v: t.v, xc: t.xc }; })
        };
        if (best) {
          var L = best.A.xc <= best.B.xc ? best.A : best.B;
          var Rr = best.A.xc <= best.B.xc ? best.B : best.A;
          var vA = best.fit.A, vB = best.fit.B;
          var leftIsOut = best.A.xc <= best.B.xc;
          rec.out = leftIsOut ? vA : vB;
          rec.inp = leftIsOut ? vB : vA;
          rec.total = best.fit.C;
          rec.fixed = best.fit.fixes > 0;
          rec.nums = nums.map(function (t) { return { v: t.v, xc: t.xc }; });
          /* 人数：优先按「列号」取值（表格列边界已知且精确），避免前移顶替。
             列序（以本类营收日报为例）：
               门诊收入 → 门诊环比 → 初诊 → 复诊 → 在院收入
                        → 在院环比 → 在院 → 入院 → 出院初次 → 出院多次 → 当日合计
             即：初诊 = 门诊收入列 +2、复诊 = +3；
                 在院 = 在院收入列 +2、入院 = +3、出院初次 = +4、出院多次 = +5。
             若某列没读出，宁可留空（由用户核对补全），也不要让后面的值顶上 ——
             实测旧相对取法会把「复诊 79」写成「初诊 79」。 */
          /* ⚠ 必须用 ctx.meta —— 函数后面的 `var meta = ctx.meta` 在重建循环之后才赋值，
             在此处因变量提升而是 undefined，会导致永远走回退分支。 */
          var bnd = (ctx.meta && ctx.meta.bounds) || [];
          var colOf = function (xc) {
            for (var ci = 0; ci < bnd.length - 1; ci++) if (xc >= bnd[ci] && xc < bnd[ci + 1]) return ci;
            return -1;
          };
          var cA = colOf(L.xc), cB = colOf(Rr.xc);
          /* ⭐ 2026-10-09：当日合计所在的列号 —— 用来给「在院侧人数」设上界。 */
          var cC = best.C ? colOf(best.C.xc) : -1;
          var pickCol = function (ci) {
            if (ci < 0 || ci >= bnd.length) return null;
            var hit = nums.filter(function (t) {
              return t !== L && t !== Rr && t !== best.C &&
                     t.v > 0 && t.v < 500 && t.v % 1 === 0 && colOf(t.xc) === ci;
            });
            return hit.length === 1 ? hit[0].v : null;   // 唯一命中才采信
          };
          if (cA >= 0 && cB > cA) {
            /* ⚠⚠ 人数列一律**按列序设边界**，不得只按下标取。
               实测：一张只含「日期｜门诊收入｜在院收入｜当日合计」的裁剪图，
               在院列 +2 落到合计列上，把「117010.55」的小数片段 95 写成了「初诊」。
               真实营收日报的列序恒满足下面两条（见上方注释），故不会误伤；
               列被裁掉时取不到值 → 留空交用户核对，好过写错。 */
            var f1 = (cA + 2 < cB) ? pickCol(cA + 2) : null;
            var f2 = (cA + 3 < cB) ? pickCol(cA + 3) : null;
            var p1 = (cC < 0 || cB + 2 < cC) ? pickCol(cB + 2) : null;
            var p2 = (cC < 0 || cB + 3 < cC) ? pickCol(cB + 3) : null;
            /* ⚠⚠ 出院列：必须先分清「列不存在」与「列存在但没读出」。
               原写法 `(p3||0)+(p4||0)` 把「没读出」静默当成 0 ——
               本图实证：10.7 行 出院初次 4 + 出院多次 2 应为 6，却写成 4（出院人数偏小）。
               ⇒ 列存在却没读出时**不猜**，置 dischPending（留空 + 界面提示用户核对）。 */
            var hasP3 = (cC < 0) || (cB + 4 < cC);
            var hasP4 = (cC < 0) || (cB + 5 < cC);
            var p3 = hasP3 ? pickCol(cB + 4) : null;
            var p4 = hasP4 ? pickCol(cB + 5) : null;
            if (f1 != null) rec.first = f1;
            if (f2 != null) rec.again = f2;
            if (p1 != null) rec.inhos = p1;
            if (p2 != null) rec.admit = p2;
            var dischComplete = (p3 != null || !hasP3) && (p4 != null || !hasP4);
            if (dischComplete) {
              if (p3 != null || p4 != null) rec.disch = (p3 || 0) + (p4 || 0);
            } else if (p3 != null || p4 != null) {
              /* 只读出一列 → 不做加法、也不拿单列充数，标「待核对」让界面提示 */
              rec.dischPending = true;
            }
          } else {
            /* 回退：没有列边界时，仍按「夹在两组收入之间的第 n 个小整数」取，但要求不模糊 */
            var small = function (a, b) {
              return nums.filter(function (t) {
                return t !== L && t !== Rr && t !== best.C &&
                       t.v > 0 && t.v < 500 && t.v % 1 === 0 &&
                       t.xc > a && t.xc < b;
              }).sort(function (x, y) { return x.xc - y.xc; });
            };
            var leftSide = small(L.xc, Rr.xc);
            if (leftSide.length <= 2) {
              if (leftSide[0]) rec.first = leftSide[0].v;
              if (leftSide[1]) rec.again = leftSide[1].v;
            }
            var rightSide = small(Rr.xc, best.C.xc);
            if (rightSide.length <= 4) {
              if (rightSide[0]) rec.inhos = rightSide[0].v;
              if (rightSide[1]) rec.admit = rightSide[1].v;
              if (rightSide[2]) rec.disch = (rightSide[2].v || 0) + (rightSide[3] ? rightSide[3].v : 0);
            }
          }
        }
        out.push(rec);
      });

      /* 累计递推校验：营收日报的「当月累计收入」逐日递增，相邻两日之差就是当日合计。
         该列金额大、变化明显，OCR 反而最稳；用它来锁定当日合计，可排除
         「两个错数恰好也能配平」的情况（实测 9.21 行曾被误判为 77200 + 2979）。 */
      var cumRows = out.filter(function (r) {
        var c = null;
        (r.nums || []).forEach(function (n) {
          var vv = normMoney(n.v);
          if (vv >= 300000 && (!c || vv > c)) c = vv;    // 累计列是该行最大的金额
        });
        if (!c) return false;
        r.cum = c; return true;
      });
      cumRows.sort(function (a, b) { return a.date < b.date ? -1 : (a.date > b.date ? 1 : 0); });
      for (var ci = 1; ci < cumRows.length; ci++) {
        var gap2 = cumRows[ci].cum - cumRows[ci - 1].cum;
        if (gap2 > 500 && gap2 < 800000) { cumRows[ci].cumDiff = gap2; }
      }
      cumRows.forEach(function (r) {
        if (!r.cumDiff || !r.nums || r.nums.length < 2) return;
        var hit = null;
        for (var i = 0; i < r.nums.length && !hit; i++) {
          for (var j = i + 1; j < r.nums.length && !hit; j++) {
            var fit = pairSum(r.nums[i].v, r.nums[j].v, r.cumDiff);
            if (fit) hit = { i: i, j: j, fit: fit };
          }
        }
        if (hit) {
          var A = r.nums[hit.i], B = r.nums[hit.j];
          var left2 = A.xc <= B.xc;
          r.verified = true; r.byCum = true; r.total = r.cumDiff;
          r.out = left2 ? hit.fit.A : hit.fit.B;
          r.inp = left2 ? hit.fit.B : hit.fit.A;
        } else {
          r.verified = false;   // 用累计差也凑不出 → 判为待核对，不写入
        }
      });

      /* ⭐⭐⭐ 2026-10-09 兜底：三数自校验与累计差**都失败**时，rec.out/inp 会完全为空
         → verifyRows 判 invalid → 界面显示「暂无可写入的有效行」，
         用户明明看到那一天的数据却提交不了（业主本轮实证）。
         这里退化为「排除累计列后取最大的两个金额，按横向位置分配」：
           · 排除 >= 300000 —— 营收日报里只有「当月累计」会到 30 万以上（与上文累计列判据一致），
             当日门诊/在院/合计都在 30 万以下（10 月单日最高 16.22 万）；
           · 左＝门诊收入、右＝在院收入 —— 与源表列序一致（门诊在左）。
         ⚠ 标 needCheck=true：这是**降级推断**，不是自证，界面按「待核对」呈现，
           用户扫一眼即可改对，比留空让他从零手输好得多，也**能被提交**。 */
      out.forEach(function (r) {
        if (r.out != null || r.inp != null) return;
        if (!r.nums || !r.nums.length) return;
        /* 候选金额：排除累计列（>=30 万，营收日报只有「当月累计」会到）与非金额（<500 是人数） */
        var cand = r.nums.map(function (t) { return { v: normMoney(t.v), xc: t.xc }; })
          .filter(function (t) { return t.v >= 500 && t.v < 300000; })
          .sort(function (a, b) { return b.v - a.v; });
        if (!cand.length) return;
        /* 把「识别到了哪些金额」留给界面 —— 用户最需要的是知道系统读到了什么，
           而不是对着一片空白猜（业主反馈原话：「明明拖入的图片里有总金额」）。 */
        r.hints = cand.slice(0, 4).map(function (t) { return t.v; });

        /* ① 优先找 C ≈ A+B：**自动排除「当日合计」列**。
           ⚠ 不能简单「取最大两个」—— 门诊/在院/合计 三个都在时，最大两个是
           「合计 + 门诊」，会把合计当门诊静默填错。容差放宽到 0.8%
           （三数自校验用的是 0.06 或 C×0.0008，此处更宽松，因为已经是降级路径）。 */
        var trio = null;
        for (var i2 = 0; i2 < cand.length; i2++)
          for (var j2 = i2 + 1; j2 < cand.length; j2++)
            for (var k2 = 0; k2 < cand.length; k2++) {
              if (k2 === i2 || k2 === j2) continue;
              var tol2 = Math.max(0.06, cand[k2].v * 0.008);
              if (Math.abs(cand[i2].v + cand[j2].v - cand[k2].v) <= tol2) {
                /* 取「缩放次数少」= 直接优先，这里已无缩放信息，取和为最大者更可能是真合计 */
                if (!trio || cand[k2].v > trio.total) trio = { a: cand[i2], b: cand[j2], total: cand[k2].v };
              }
            }
        var pair = null;
        if (trio) { pair = [trio.a, trio.b]; r.hintTotal = trio.total; }
        else if (cand.length >= 2) { pair = [cand[0], cand[1]]; }

        if (pair) {
          pair.sort(function (a, b) { return a.xc - b.xc; });   // 左 → 门诊，右 → 在院
          r.out = pair[0].v; r.inp = pair[1].v; r.needCheck = true;
        } else {
          /* ③ 只识别到 1 个金额：**不自动填**（单个数更可能是「当日合计」，
             当成门诊会污染数据），但记入 hints，界面会把这数字显示出来让用户填。 */
          r.needCheck = true; r.single = true;
        }
      });

      /* 既没有日期、又无法用累计差验证的行，绝大多数是数字残片（如 "800 | 1959"），
         直接丢弃，否则会把噪声灌进识别表。
         ⚠ 2026-10-09：条件里补上「已推断出金额」—— 兜底刚填过 out/inp 的行，
           即便日期没认出来也应保留，让用户补个日期就能用。 */
      out = out.filter(function (r) { return r.date || r.verified || r.needCheck; });

      var meta = ctx.meta || { blocks: 0, bounds: [], coarse: 0 };
      try {
        window.__ocrDebug = { blocks: meta.blocks, bounds: meta.bounds, coarse: meta.coarse, medH: meta.medH,
                              collected: toks.length, kept: kept.length, rows: rows.length, blocks: meta.texts,
                              parsed: out.length, verified: out.filter(function (r4) { return r4.verified; }).length,
                              byCum: out.filter(function (r4) { return r4.byCum; }).length, sample: out.slice(0, 8),
                              lines: rows.map(function (r3) {
                                return r3.ts.map(function (t) { return t.text; }).join(' ').slice(0, 110);
                              }).slice(0, 12) };
      } catch (e) { }
      var okN = out.filter(function (r2) { return r2.verified; }).length;
      ocrProgress(out.length
        ? ('识别到 ' + out.length + ' 行：' + okN + ' 行数值自洽可直接使用，其余请在下方核对补全')
        : ('未提取到数据行（共识别 ' + kept.length + ' 个数字 / ' + rows.length + ' 行文本）。可改用「粘贴文本」或手工填写'));
      return out;
    });
  }
// ============================================================================

  /* ============================ 抽屉 UI ============================ */
  var host = document.createElement('div');
  host.className = 'import-backdrop';
  host.id = 'importBackdrop';
  host.innerHTML = '<section class="import-drawer" role="dialog" aria-modal="true" aria-label="导入并更新分析数据">'
    + '<header class="import-head"><div><h2>导入并更新分析数据</h2><p>解析 → 校验 → 更新。原数据快照自动保留，可整体回退</p></div>'
    + '<button class="import-close" aria-label="关闭">×</button></header>'
    + '<div class="import-body">'
    + '  <input id="importFile" type="file" multiple accept=".csv,.tsv,.txt,.xlsx,.png,.jpg,.jpeg,.webp,image/*" hidden>'
    + '  <div class="drop-zone" id="dropZone"><div class="drop-icon">⇧</div><b>拖入图片或表格文件</b>'
    + '<span>CSV / XLSX 自动解析；图片自动识别日期、门诊/在院收入与入出院人数，结果可在下方核对修改</span></div>'
    + '  <div class="ocr-status" id="ocrStatus" style="display:none"></div>'
    + '  <div class="store-warn" id="storeWarn" style="display:none"></div>'
    + '  <div class="import-steps"><div class="import-step active" data-n="1">上传</div><div class="import-step" data-n="2">识别</div>'
    + '<div class="import-step" data-n="3">校验</div><div class="import-step" data-n="4">确认更新</div></div>'
    + '  <section class="import-card"><h3>本次文件<span class="card-hint" id="fileCount"></span></h3><div id="fileList"></div></section>'
    + '  <section class="import-card"><h3>粘贴识别文本 <span class="card-hint">可选 · 从日报或截图转文字后直接粘</span></h3>'
    + '  <textarea id="pasteBox" class="paste-box" spellcheck="false" placeholder="9.23 门诊 25087.04 在院 30216.77&#10;9.24 门诊 31000 在院 29000&#10;也可直接粘贴 CSV 内容"></textarea>'
    + '  <button class="paste-apply" id="pasteApply">解析粘贴内容</button></section>'
    + '  <section class="import-card"><h3>识别结果 <span class="card-hint">可直接修改 · 单位：元（也可写 7.62万）</span></h3>'
    + '  <div id="rowEditor" class="row-editor"></div>'
    + '  <button class="paste-apply" id="addRow">+ 手工添加一行</button></section>'
    + '  <section class="import-card"><h3>数据校验</h3><div class="verify-grid" id="verifyGrid"></div>'
    + '  <div id="conflictArea"></div>'
    + '  <label class="audit"><input type="checkbox" checked id="snapChk"> 保存本次导入前的数据快照，并记录来源与导入时间</label>'
    + '  <div class="reset-line"><button class="link-btn" id="resetBtn">恢复初始数据（清除本机导入）</button><span id="metaLine" class="meta-line"></span></div>'
    + '  </section></div>'
    + '<footer class="import-footer"><button class="cancel">取消</button><button class="export" id="exportBtn">复制数据块</button>'
    + '<button class="confirm" id="confirmBtn">确认更新</button></footer></section>';
  document.body.appendChild(host);

  var toast = document.createElement('div');
  toast.className = 'demo-toast';
  document.body.appendChild(toast);
  var toastTimer = null;
  function showToast(msg, ms) {
    toast.textContent = msg;
    toast.classList.add('show');
    if (toastTimer) clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { toast.classList.remove('show'); }, ms || 3600);
  }

  /* ⭐ 2026-10-09：拖图/粘贴只是「识别」，**必须点「确认更新」才写入并保存到本机**。
     用户常以为拖进去就自动保存了 → 关掉抽屉、刷新、发现没变 → 反馈「拖图不保存」。
     这里在「有未保存的新/改动行」时提醒一次（不阻塞关闭，不打扰纯查看）。
     ⚠ verdict 在本行之后才 var 声明，但其值在关闭时已就绪（var 提升 + 延迟执行）。 */
  var close = function () {
    try {
      var pend = verdict && verdict.rows.filter(function (r) { return r.status === 'new' || r.status === 'update'; }).length;
      if (pend) showToast('还有 ' + pend + ' 天的识别结果未保存：点「确认更新」才会写入并保存到本机', 6000);
    } catch (e) { }
    host.classList.remove('show');
  };
  var open = function () { host.classList.add('show'); var d = host.querySelector('.import-drawer'); if (d) d.scrollTop = 0; refreshMeta(); };
  host.querySelector('.import-close').onclick = close;
  host.querySelector('.cancel').onclick = close;
  host.addEventListener('click', function (e) { if (e.target === host) close(); });
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape' && host.classList.contains('show')) close(); });

  var tools = document.querySelector('.sales-month-tools');
  if (tools) { var tb = document.createElement('button'); tb.className = 'data-update-btn'; tb.innerHTML = '⇧ 更新数据'; tb.onclick = open; tools.prepend(tb); }
  var v2Import = document.querySelector('.mkt-import'); if (v2Import) v2Import.onclick = open;
  var edit = document.getElementById('salesEdit'); if (edit) edit.onclick = open;

  /* ⭐ 营销面板头部的「拖图即可更新」提示（2026-10-07）。
     营销面板开屏自动展开、盖住整页，用户最先看到的操作区就是这里；
     此前没有任何提示，用户不知道可以「就地拖图」——加了提示 + 全局落点后，
     拖到面板任意位置都能导入，不必先找「更新数据」按钮。 */
  (function addDropTip() {
    var actions = document.querySelector('.mkt-actions');
    if (!actions || actions.querySelector('.mkt-drop-tip')) return;
    var tip = document.createElement('span');
    tip.className = 'mkt-drop-tip';
    tip.innerHTML = '<i>⇧</i>把日报截图拖到页面任意处即可更新';
    actions.insertBefore(tip, actions.firstChild);
  })();

  /* ---------- 状态 ---------- */
  var files = [];      // {name,size,type,kind,rows,error,thumb}
  var rows = [];       // 编辑区行
  var verdict = null;  // verifyRows 结果

  var fileList = host.querySelector('#fileList');
  var rowEditor = host.querySelector('#rowEditor');
  var verifyGrid = host.querySelector('#verifyGrid');
  var conflictArea = host.querySelector('#conflictArea');
  var confirmBtn = host.querySelector('#confirmBtn');
  var input = host.querySelector('#importFile');
  var dz = host.querySelector('#dropZone');

  /* ---------- 文件处理 ---------- */
  function kindOf(f) {
    var n = (f.name || '').toLowerCase();
    if (/\.(png|jpe?g|webp|gif|bmp)$/.test(n) || /^image\//.test(f.type)) return 'image';
    if (/\.csv$/.test(n) || /\.tsv$/.test(n) || /\.txt$/.test(n)) return 'csv';
    if (/\.xlsx$/.test(n)) return 'xlsx';
    if (/\.xls$/.test(n)) return 'xls';
    return 'other';
  }
  function readText(f) {
    return f.arrayBuffer().then(function (buf) {
      var txt = new TextDecoder('utf-8').decode(buf);
      if (txt.indexOf('\uFFFD') >= 0) { try { txt = new TextDecoder('gbk').decode(buf); } catch (e) { } }
      return txt;
    });
  }
  function nextMissingDate() {
    var used = {};
    rows.forEach(function (r) { var d = normDate(r.date); if (d) used[d] = 1; });
    var miss = summary(loadDaily()).missing.filter(function (d) { return !used[d]; });
    return miss.length ? miss[0] : null;
  }
  function guessDateFromName(name) {
    var m = String(name).match(/(\d{4}[-._]?\d{1,2}[-._]?\d{1,2}|\d{1,2}[-._月]\d{1,2})/);
    return m ? normDate(m[1]) : null;
  }
  function handleFiles(list) {
    var arr = Array.prototype.slice.call(list || []);
    if (!arr.length) return;
    var jobs = arr.map(function (f) {
      var kind = kindOf(f);
      var rec = { name: f.name, size: f.size, kind: kind, rows: [], error: null, thumb: null, status: '识别中' };
      files.push(rec);
      var p;
      if (kind === 'csv') p = readText(f).then(function (t) { rec.rows = rowsFromTable(splitCSV(t)); });
      else if (kind === 'xlsx') p = f.arrayBuffer().then(function (b) { return parseXLSX(b); }).then(function (r) { rec.rows = r; });
      else if (kind === 'xls') p = Promise.reject(new Error('旧版 .xls 无法在浏览器解析，请另存为 .xlsx 或 .csv'));
      else if (kind === 'image') {
        rec.thumb = URL.createObjectURL(f);
        rec.rows = [];
        var myGen = ocrGen;
        p = queueOcr(function () {
          rec.status = '排队中…'; renderFiles();
          ocrCancelBtn(true);
          return ocrRevenueImage(rec.thumb, function (n) {
            if (myGen === ocrGen) { rec.status = n; renderFiles(); }
          }).then(function (got) {
            if (myGen !== ocrGen) { rec.status = '已取消'; rec.rows = []; return; }
            rec.rows = got || [];
          }).catch(function (e) {
            if (myGen !== ocrGen) { rec.status = '已取消'; rec.rows = []; return; }
            rec.ocrError = (e && e.message) ? e.message : String(e);
          }).then(function () {
            if (myGen === ocrGen) ocrCancelBtn(false);
          });
        });
      }
      else p = Promise.reject(new Error('不支持的文件类型'));
      return p.then(function () {
        if (!rec.rows.length) {
          if (kind === 'image') {
            rec.status = rec.ocrError ? ('识别失败：' + rec.ocrError) : '未识别到数字，请手工填写';
            var g = guessDateFromName(f.name);
            if (g && g > SOURCE_CUTOFF) g = null;   // 晚于数据截止日 → 多为文件生成/接收时间，不作数据日期
            g = g || nextMissingDate();
            if (g) rowEditorAdd({ date: g, out: null, inp: null });
          } else { rec.status = '未识别到数据行'; rec.error = '未识别到「日期 + 门诊/在院收入」的数据行'; }
        } else {
          var good = rec.rows.filter(function (r) { return r.verified; });
          rec.status = '识别到 ' + rec.rows.length + ' 行，其中 ' + good.length + ' 行数值自洽';
          /* ⚠⚠⚠ 2026-10-09 修（业主报「明明有新一天数据，却更新不了」）：
             原先是三分支 ——「verified → 传全字段」/「有日期 → **只传日期**」/「其它」。
             中间那条会把**已经识别出来的金额丢掉**：只要没通过三数自校验（verified=false），
             即便 rec.out/rec.inp 有值（兜底已填），也仅带出日期。
             ⇒ 结果表只有日期没有金额 → verifyRows 判 invalid → 按钮「请先补齐…」。
             实测反查：__ocrDebug.sample[0] = {date:'2026-10-08', out:76890, inp:40120.55}
             金额就在 rec 上，纯粹是这一步没传。
             现在合并为一条：**有什么带什么**，缺的留空由用户补。
             顺带修掉原第三个分支 `else if (r.verified)` 不可达、「有金额无日期」被丢弃的问题。 */
          rec.rows.forEach(function (r) {
            /* ⭐ 2026-10-09：过滤「幻影行」——**只有日期、别的什么都没有**。
               来源：报表标题 / 表头里带的日期（如「营收日报 2026-10-08」）会被当成一条记录，
               但它没有金额也没有候选，带进结果表只会多出一行「待补」，让界面喊「请先补齐数据」，
               反而把「金额没填上」这个真问题掩盖掉。
               判据：日期之外**必须**至少有一项内容（金额 / 人数 / 金额候选）才带出来。
               ⚠ 与「只识别到 1 个金额」的行不冲突 —— 那种行 hints 非空，照常显示。 */
            var hasContent = r.out != null || r.inp != null
              || r.first != null || r.again != null || r.inhos != null
              || r.admit != null || r.disch != null
              || (r.hints && r.hints.length);
            if (!hasContent) return;
            rowEditorAdd({ date: r.date, out: r.out, inp: r.inp, first: r.first, again: r.again,
                           inhos: r.inhos, admit: r.admit, disch: r.disch, dischPending: r.dischPending,
                           needCheck: r.needCheck, single: r.single, hints: r.hints, hintTotal: r.hintTotal });
          });
        }
      }).catch(function (err) {
        rec.error = err && err.message ? err.message : String(err);
        rec.status = '解析失败';
      });
    });
    Promise.all(jobs).then(function () {
      renderFiles();
      renderRows();
      setStep(3);
      revalidate();
    });
  }

  function renderFiles() {
    if (!files.length) { fileList.innerHTML = '<div class="import-empty">尚未选择文件</div>'; }
    else {
      fileList.innerHTML = files.map(function (f, i) {
        var type = f.kind === 'image' ? 'IMG' : (f.name.split('.').pop() || 'FILE').toUpperCase();
        var cls = f.error ? 'status-bad' : (f.kind === 'image' ? 'status-warn' : 'status-ok');
        var thumb = f.thumb ? '<img class="thumb" src="' + f.thumb + '" alt="预览">' : '';
        return '<div class="file-row">' + thumb + '<div class="file-type ' + (f.kind === 'image' ? 'image' : '') + '">' + type + '</div>'
          + '<div class="file-meta"><b>' + esc(f.name) + '</b><span>' + Math.max(1, Math.round(f.size / 1024)) + ' KB · ' + esc(f.status)
          + (f.error ? ' · ' + esc(f.error) : '') + '</span></div>'
          + '<em class="' + cls + '">' + (f.error ? '需处理' : 'OK') + '</em>'
          + '<button class="row-del" data-fdel="' + i + '" title="移除">×</button></div>';
      }).join('');
    }
    var n = files.length;
    host.querySelector('#fileCount').textContent = n ? n + ' 个文件' : '';
    $$('[data-fdel]', fileList).forEach(function (b) {
      b.onclick = function () { var i = +b.dataset.fdel; if (files[i] && files[i].thumb) URL.revokeObjectURL(files[i].thumb); files.splice(i, 1); renderFiles(); };
    });
    $$('.file-row .thumb', fileList).forEach(function (img, i) {
      img.title = '点击放大对照录入';
      img.onclick = function () {
        var row = img.closest('.file-row');
        var big = row.querySelector('.thumb-big');
        if (big) { big.remove(); return; }
        $$('.thumb-big', fileList).forEach(function (x) { x.remove(); });
        var el = document.createElement('img');
        el.className = 'thumb-big';
        el.src = img.src;
        el.alt = '原图预览';
        row.appendChild(el);
      };
    });
  }

  /* ---------- 行编辑 ---------- */
  var NUMKEYS = ['out', 'inp', 'first', 'again', 'inhos', 'admit', 'disch'];
  function rowEditorAdd(r) {
    var d = normDate(r.date) || r.date || '';
    var dup = rows.filter(function (x) {
      return (normDate(x.date) || x.date || '') === d && x.out === r.out && x.inp === r.inp;
    }).length;
    if (dup) return;
    var row = { date: r.date || '' };
    NUMKEYS.forEach(function (k) { row[k] = (r[k] == null || r[k] === '') ? '' : r[k]; });
    /* ⭐ 2026-10-09：带上「金额是自动推断的」标记 + 「识别到的金额候选」，
       结果表据此显示核对提示，让用户知道系统到底读到了什么。 */
    if (r.needCheck) row.needCheck = true;
    if (r.single) row.single = true;
    if (r.hints && r.hints.length) row.hints = r.hints.slice();
    if (r.hintTotal != null) row.hintTotal = r.hintTotal;
    /* ⭐ 出院列（初次 + 多次）只读出一列 → 总数未知，不许当成 0 */
    if (r.dischPending) row.dischPending = true;
    rows.push(row);
  }
  function renderRows() {
    if (!rows.length) { rowEditor.innerHTML = '<div class="import-empty">暂无识别结果 —— 拖入图片或表格、粘贴文本，或手工添加一行</div>'; return; }
    /* ⭐ 2026-10-09：数值列的空提示一律用「—」，**不再放示例数字**。
       原因（业主两轮反馈都撞在这上面）：灰色示例值会被当成真实数据 ——
         · 「出院」示例 1，而真值是「出院初次 + 出院多次」之和（常为 6、甚至 0）；
         · 「入院」示例 3，在确认为 0 的行里也显示 3。
       placeholder 只表示「这里空着」，格式提示交给表头与 inputmode。
       ⚠ 日期列保留 '9.23'：那是格式提示，不会被误读成金额。 */
    var EMPTY = '—';
    var cols = [['date', '日期', '9.23'], ['out', '门诊收入', EMPTY], ['inp', '在院收入', EMPTY],
                ['first', '初诊', EMPTY], ['again', '复诊', EMPTY], ['inhos', '在院', EMPTY],
                ['admit', '入院', EMPTY], ['disch', '出院', EMPTY]];
    rowEditor.innerHTML = '<div class="edit-scroll"><table class="edit-table"><thead><tr>'
      + cols.map(function (c) { return '<th>' + c[1] + '</th>'; }).join('')
      + '<th>合计</th><th></th></tr></thead><tbody>'
      + rows.map(function (r, i) {
        var o = toNum(r.out), p = toNum(r.inp);
        var tot = (o || 0) + (p || 0);
        return '<tr>' + cols.map(function (c) {
          var cls = c[0] === 'date' ? 'cell-in date' : 'cell-in';
          /* ⭐ 2026-10-09：待核对/留空的格子，把**灰色示例数字**换成文字说明。
             否则「故意留空」会被 placeholder 的示例值（如出院列示例「1」）盖住，
             用户看不出这里是空的、还可能误以为是 0 —— 与「缺值→待补、不得默认 0」口径冲突。 */
          var ph = c[2];
          if (c[0] === 'disch' && r.dischPending) { ph = '两列相加'; cls += ' cell-need'; }
          return '<td><input class="' + cls + '" data-i="' + i + '" data-k="' + c[0] + '" value="' + esc(c[0] === 'date' ? shortDate(r.date) : r[c[0]]) + '" placeholder="' + ph + '" inputmode="decimal"></td>';
        }).join('')
          + '<td class="cell-total">' + (tot ? wan(tot, 2) + '万' : '—') + '</td>'
          + '<td><button class="row-del" data-rdel="' + i + '" title="删除">×</button></td></tr>';
      }).join('') + '</tbody></table></div>';
    $$('.cell-in', rowEditor).forEach(function (el) {
      el.oninput = function () {
        var i = +el.dataset.i, k = el.dataset.k;
        if (!rows[i]) return;
        rows[i][k] = el.value;
        var tr = el.closest('tr');
        var o = toNum(rows[i].out), p = toNum(rows[i].inp), tot = (o || 0) + (p || 0);
        if (tr) tr.querySelector('.cell-total').textContent = tot ? wan(tot, 2) + '万' : '—';
        scheduleValidate();
      };
    });
    $$('[data-rdel]', rowEditor).forEach(function (b) {
      b.onclick = function () { rows.splice(+b.dataset.rdel, 1); renderRows(); revalidate(); };
    });
    markConflicts();
  }
  var vt = null;
  function scheduleValidate() { if (vt) clearTimeout(vt); vt = setTimeout(revalidate, 260); }

  /* ---------- 校验 ---------- */
  function revalidate() {
    var daily = loadDaily();
    var parsed = rows.map(function (r) {
      var o = { date: normDate(r.date) || '', out: toNull(r.out), inp: toNull(r.inp), raw: '' };
      ['first', 'again', 'inhos', 'admit', 'disch'].forEach(function (k) { o[k] = toNull(r[k]); });
      return o;
    }).filter(function (r) { return r.date || r.out != null || r.inp != null; });
    verdict = verifyRows(parsed, daily);
    var v = verdict.rows, c = { new: 0, update: 0, same: 0, conflict: 0, invalid: 0 };
    v.forEach(function (r) { c[r.status] = (c[r.status] || 0) + 1; });
    var unitTxt = verdict.unit === 10000 ? '按「万元」解析' : '按「元」解析';
    verifyGrid.innerHTML = '<div><b>' + c.new + '</b>新增</div><div><b>' + c.update + '</b>更新</div>'
      + '<div><b>' + c.same + '</b>一致</div><div class="' + (c.conflict ? 'conflict' : '') + '"><b>' + c.conflict + '</b>冲突</div>'
      + '<div><b>' + c.invalid + '</b>无效</div><div class="unit-cell">' + unitTxt + '</div>';
    // 明细表
    var det = v.filter(function (r) { return r.status !== 'same'; });
    var html = '';
    if (det.length) {
      html += '<table class="map-table"><thead><tr><th>日期</th><th>看板指标</th><th>新值</th><th>状态</th></tr></thead><tbody>'
        + det.map(function (r) {
          var st = { new: '<span class="tag">新增</span>', update: '<span class="tag tag-up">更新</span>', conflict: '<span class="tag tag-bad">冲突</span>', invalid: '<span class="tag tag-bad">无效</span>' }[r.status] || '';
          var val = (r.out != null ? '门诊 ' + wan(r.out, 2) + '万' : '') + (r.inp != null ? '　在院 ' + wan(r.inp, 2) + '万' : '')
            + ((r.first != null || r.admit != null || r.disch != null)
              ? '<div class="old-val">' + (r.first != null ? '初诊 ' + r.first + '　' : '') + (r.admit != null ? '入院 ' + r.admit + '　' : '') + (r.disch != null ? '出院 ' + r.disch : '') + '</div>' : '');
          var old = r.old ? '<div class="old-val">原：门诊 ' + wan(r.old[0], 2) + '万　在院 ' + wan(r.old[1], 2) + '万</div>' : '';
          var note = r.notes && r.notes.length ? '<div class="old-val">' + esc(r.notes.join('；')) + '</div>' : '';
          return '<tr><td>' + (r.date ? (r.date.slice(5, 7) + '.' + r.date.slice(8)) : '—') + '</td><td>当日营业额</td><td>' + val + old + note + '</td><td>' + st + '</td></tr>';
        }).join('') + '</tbody></table>';
    } else if (v.length) {
      html = '<div class="import-empty">所有行与现有数据一致，确认后仅更新记录时间。</div>';
    } else {
      html = '<div class="import-empty">还没有可校验的数据行。</div>';
    }
    conflictArea.innerHTML = html;

    /* ⭐⭐ 结果表上方提示：**把识别到的金额摆出来**。
       业主原话「说要补齐数据，但明明拖入的图片里有总金额啊」——
       症结不是没识别到，而是识别到了既不告诉他、也没填进去。 */
    (function () {
      var tip = document.getElementById('autoFillTip');
      if (!tip) {
        tip = document.createElement('div');
        tip.id = 'autoFillTip';
        tip.className = 'import-empty';
        var ra = document.getElementById('rowEditor');
        if (ra && ra.parentNode) ra.parentNode.insertBefore(tip, ra);
      }
      var autoN = rows.filter(function (r) { return r.needCheck && !r.single; }).length;
      var singleR = rows.filter(function (r) { return r.single; });
      var allHints = [];
      rows.forEach(function (r) {
        (r.hints || []).forEach(function (v) { if (allHints.indexOf(v) < 0) allHints.push(v); });
      });
      allHints.sort(function (a, b) { return b - a; });
      var fmtM = function (v) { return v >= 10000 ? (v / 10000).toFixed(2) + ' 万' : v.toFixed(2) + ' 元'; };

      var msgs = [];
      if (autoN) {
        msgs.push('⚠ 有 ' + autoN + ' 行的金额已自动填入（合计列未读出或只有单日数据，无法自证），'
          + '请核对「门诊收入 / 在院收入」两列后再提交。');
      }
      if (singleR.length) {
        var one = (singleR[0].hints || [])[0];
        msgs.push('⚠ 有 ' + singleR.length + ' 行只识别到 <b>1 个金额</b>'
          + (one != null ? '（' + fmtM(one) + '）' : '') + '，<b>疑似「当日合计」</b>，未自动填入。'
          + '请把门诊收入 / 在院收入两列填上（若该数就是合计，可只填门诊或按拆分填写）。');
      }
      /* ⭐ 出院列读不全：**必须说清楚**，否则用户看到空值会以为是「当天 0 人出院」 */
      var pendDisch = rows.filter(function (r) { return r.dischPending; }).length;
      if (pendDisch) {
        msgs.push('⚠ 有 ' + pendDisch + ' 行的<b>「出院」人数未读全</b>'
          + '（该表把出院拆成「出院初次 + 出院多次」两列，只读出了其中一列）。'
          + '为避免把「没读出」当成 0，这里<b>故意留空</b>：请对照原图把两列相加后填入。');
      }
      if (allHints.length) {
        msgs.push('本次识别到的金额候选（按大小）：<b>'
          + allHints.slice(0, 5).map(fmtM).join('</b> · <b>') + '</b>'
          + '　—— 若其中包含「当日合计」，它不会计入门诊/在院，请按列拆分填写。');
      }
      /* ⭐ 一条可校验的行都没有 / 全被判无效，且**没有金额候选可解释**时 → 大概率
         **不是营收日报截图**（例如把分析报告页面截图拖了进来）。
         把系统实际读到的原文摆出来，让用户自己判断，而不是干巴巴一句「未提取到数据行」。
         ⚠ 触发条件必须**排除「已有有效行」的正常场景**：
           `c.new + c.update + c.same === 0` 才说明一张能用的行都没有。
           （原先用 c.invalid>0 判断会误报：手工补好一行后按钮已可点，诊断却还挂着。） */
      if (!msgs.length && files.length && (c.new + c.update + c.same) === 0) {
        var dbg = window.__ocrDebug || {};
        var lines = (dbg.lines || []).slice(0, 3);
        var lack = files.filter(function (f2) { return f2.error; });
        msgs.push('<b>未从图中识别出「日期 ＋ 门诊收入 / 在院收入」结构。</b>'
          + (lack.length ? '（' + lack.length + ' 个文件解析失败：' + esc(lack[0].error || '') + '）' : '')
          + '<br>请确认拖入的是<b>营收日报截图</b>（含日期与门诊/在院收入两列）。'
          + '若图里确实有这些数字，可改用下方「粘贴识别文本」或手工添加一行。');
        if (lines.length) {
          msgs.push('系统实际读到的内容（前 ' + lines.length + ' 行）：'
            + lines.map(function (l) { return '<br>· ' + esc(l.slice(0, 80)); }).join(''));
        }
      }
      if (msgs.length) {
        tip.innerHTML = msgs.join('<br>');
        tip.style.display = '';
      } else {
        tip.innerHTML = '';
        tip.style.display = 'none';
      }
    })();
    var hasConflict = c.conflict > 0;
    var allInvalid = v.length > 0 && c.invalid === v.length;
    confirmBtn.disabled = !v.length || allInvalid || hasConflict;
    confirmBtn.textContent = hasConflict
      ? '存在 ' + c.conflict + ' 处冲突 · 请修改上方标红的行'
      : (allInvalid ? '请先补齐标红行的日期或金额'
        : (v.length
          ? ((c.new + c.update)
            ? ('确认更新（' + (c.new + c.update) + ' 天有变化）')
            : ('确认更新（' + c.same + ' 天与现值一致）'))
          : '确认更新'));
    confirmBtn.classList.toggle('has-conflict', hasConflict);
    markConflicts();
    setStep(v.length ? 4 : (files.length ? 3 : 1));
  }
  function toNull(v) {
    if (v === '' || v == null) return null;
    var n = toNum(v);
    return n == null ? null : n;
  }

  function markConflicts() {
    if (!verdict) return;
    var bad = {};
    verdict.rows.forEach(function (r) { if (r.status === 'conflict' || r.status === 'invalid') bad[r.date] = r.status; });
    $$('#rowEditor tbody tr').forEach(function (tr) {
      var inp = tr.querySelector('input.date');
      var d = inp ? normDate(inp.value) : null;
      tr.classList.toggle('row-conflict', !!(d && bad[d] === 'conflict'));
      tr.classList.toggle('row-invalid', !!(d && bad[d] === 'invalid'));
    });
  }
  function setStep(n) {
    var steps = $$('.import-step');
    steps.forEach(function (s, i) {
      s.classList.toggle('done', i + 1 < n);
      s.classList.toggle('active', i + 1 === n);
    });
  }
  function refreshMeta() {
    var m = importedMeta();
    var el = host.querySelector('#metaLine');
    if (el) {
      el.textContent = m.updatedAt ? ('上次导入 ' + m.updatedAt.slice(0, 16).replace('T', ' ') + ' · ' + (m.files || []).join('、')) : '本机尚无导入记录';
    }
    /* ⭐ 存储不可用时，进面板第一眼就看到原因，而不是等刷新后才发现数据没了 */
    var w = host.querySelector('#storeWarn');
    if (w) {
      var h = storageHint();
      if (h) { w.innerHTML = h; w.style.display = ''; }
      else { w.innerHTML = ''; w.style.display = 'none'; }
    }
  }

  /* ---------- 执行 ---------- */
  function applyImport() {
    /* ⚠ 识别结果表用 260ms 防抖重算 verdict；用户填完立刻点确认时，
       verdict 可能还是上一轮的值 → 刚填的人数被丢掉。写入前强制重算一次。 */
    try { revalidate(); } catch (e) { }
    if (!verdict) return;
    var ok = verdict.rows.filter(function (r) { return r.status === 'new' || r.status === 'update' || r.status === 'same'; });
    if (!ok.length) { showToast('没有可写入的数据行'); return; }
    var daily = loadDaily();
    if (host.querySelector('#snapChk').checked) snapshotBefore(daily, files.map(function (f) { return f.name; }));
    var beforeCut = summary(daily).revCut;
    var touched = 0;
    var FK = { out: F_OUT, inp: F_INP, first: F_FIRST, again: F_AGAIN, inhos: F_INHOS, admit: F_ADMIT, disch: F_DISCH };
    ok.forEach(function (r) {
      if (r.out == null && r.inp == null) return;
      var cur = daily[r.date] || [];
      var arr = [];
      for (var i = 0; i < 7; i++) arr[i] = (cur[i] === undefined ? null : cur[i]);
      Object.keys(FK).forEach(function (k) { if (r[k] != null) arr[FK[k]] = r[k]; });
      if (arr[F_OUT] == null) arr[F_OUT] = 0;
      if (arr[F_INP] == null) arr[F_INP] = 0;
      daily[r.date] = arr;
      touched++;
    });
    var saved = saveDaily(daily);
    /* ⚠ 存不进本机就别写 meta（否则「上次导入」那行会骗人，显示成已成功导入） */
    if (saved.ok) writeJSON(LS_META, { updatedAt: new Date().toISOString(), files: files.map(function (f) { return f.name; }), rows: touched });
    /* 提交给服务端：这是「别的设备也能看到」的唯一一步。
       写库 + 重算快照都在服务端做，成功后顶部 KPI 与营收表口径才会一致
       （此前 KPI 走快照、营收表走 localStorage，同页会自相矛盾）。 */
    var payload = ok.map(function (r) {
      var a = daily[r.date] || [];
      return { date: r.date, outpatient: a[0], inpatient: a[1], visitsNew: a[2],
               visitsReturn: a[3], ward: a[4], admit: a[5], discharge: a[6] };
    });
    var dates = payload.map(function (r) { return r.date; });
    markPending(dates);
    pushToServer(payload, files.map(function (f) { return f.name; })).then(function (res) {
      if (res.ok) {
        clearPending(dates);
        if (saved.ok) {
          showToast('已更新 ' + touched + ' 天营收数据'
            + (beforeCut && afterCut && beforeCut !== afterCut ? ('，营收截止日 ' + mdOf(beforeCut) + ' → ' + mdOf(afterCut)) : '')
            + ' · 已写入数据库，其他设备刷新即可见', 6000);
        }
        // 服务端刚重算过快照，立刻拉一次，别等 30 秒轮询
        syncFromServer();
        try { window.dispatchEvent(new CustomEvent('ops:snapshot-updated')); } catch (e) { }
        try { if (window.OpsLiveSync && window.OpsLiveSync.refresh) window.OpsLiveSync.refresh(); } catch (e) { }
      } else if (saved.ok) {
        showToast('已更新 ' + touched + ' 天，但只存在本机：云端同步失败（' + res.reason
          + '）。其他设备看不到这次修改，本机刷新仍保留', 12000);
      }
    });
    /* ⚠ 必须在这里刷新「上次导入」那一行：原先只在 open() 里刷，
       导入成功、抽屉一关，界面仍写着「本机尚无导入记录」—— 用户以为没存下来。 */
    refreshMeta();
    refreshWindow();   // 新数据可能推进了「本周」，先对齐窗口再重绘

    /* 只保留「当月 + 上月 + 下月」的日记（防止历史脏数据无限堆积）。
       ⚠ 两个旧问题：① 原先写死 '2026-09-'，跨月后新月份数据会被当成脏数据；
                     ② 原先只 delete 内存副本、没有 saveDaily 回写，等于没清，还会误导后人。
       现在按 MONTH_FROM 推导月份前缀，并在清理后重新落盘。 */
    /* ⚠ MONTH_FROM 是完整日期（'2026-09-01'），而比较用的是 d.slice(0,7)（'2026-09'）。
       若直接放进 keepPrefix，'2026-09' === '2026-09-01' 恒不成立 →
       **当月数据会被整批当成历史脏数据删掉**（实测 dropped=26，落库后立刻清空）。
       必须统一取月份前缀。 */
    var mPrefix = MONTH_FROM.slice(0, 7);
    var keepPrefix = [mPrefix, shiftMonth(MONTH_FROM, -1), shiftMonth(MONTH_FROM, 1)];
    var dropped = 0;
    Object.keys(daily).forEach(function (d) {
      var ok = keepPrefix.some(function (p) { return d.slice(0, 7) === p; });
      if (!ok) { delete daily[d]; dropped++; }
    });
    if (dropped) { var saved2 = saveDaily(daily); if (!saved2.ok) saved = saved2; }
    renderRevenue();
    var afterCut = summary(daily).revCut;
    close();
    /* ⚠ 月份必须从日期里取：原文把 '9.' 写死，10 月数据推进后会显示
       「营收截止日 9.6 → 9.7」（把 10 月标成 9 月）。与 shortRange 同类坑。 */
    var mdOf = function (d) { return d ? ((+d.slice(5, 7)) + '.' + (+d.slice(8))) : ''; };
    if (!saved.ok) {
      /* ⭐⭐⭐ 关键：**存不住时绝不能报「已更新…已同步」**。
         原本文案是无条件的，用户在无痕/受限环境里会看到成功提示、
         刷新后回退，再回来问「为什么没保存」—— 就是本次反馈的成因。 */
      showToast('⚠ 已更新 ' + touched + ' 天，但本机未能保存（' + saved.reason + '）：刷新后会回到上一版。请用普通浏览器重试', 12000);
    }
    /* 成功路径的提示延后到服务端提交结果出来再发（见上方 pushToServer().then），
       否则会先弹「已保存到本机」再弹一次结果，用户不知道以哪句为准。 */
    files.forEach(function (f) { if (f.thumb) URL.revokeObjectURL(f.thumb); });
    files = []; rows = []; verdict = null;
    host.querySelector('#pasteBox').value = '';
    renderFiles(); renderRows(); revalidate();
    try { window.dispatchEvent(new CustomEvent('ops:revenue-updated', { detail: summary(loadDaily()) })); } catch (e) { }
  }

  host.querySelector('#confirmBtn').onclick = applyImport;

  host.querySelector('#exportBtn').onclick = function () {
    var daily = loadDaily(), ks = Object.keys(daily).sort(), lines = [];
    ks.forEach(function (d) { lines.push("    '" + d + "': [" + daily[d][0] + ', ' + daily[d][1] + ']'); });
    var code = 'var SEED = {\n' + lines.join(',\n') + '\n};';
    var done = function () { showToast('数据块已复制，可直接替换源码中的 SEED'); };
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(code).then(done, function () { fallbackCopy(code, done); });
    } else fallbackCopy(code, done);
  };
  function fallbackCopy(text, cb) {
    var ta = document.createElement('textarea');
    ta.value = text; ta.style.position = 'fixed'; ta.style.opacity = '0';
    document.body.appendChild(ta); ta.select();
    try { document.execCommand('copy'); cb(); } catch (e) { showToast('复制失败，请手动选择'); }
    document.body.removeChild(ta);
  }

  host.querySelector('#resetBtn').onclick = function () {
    resetDaily();
    renderRevenue(); refreshMeta();
    showToast('已恢复为源码中的初始数据');
  };

  host.querySelector('#pasteApply').onclick = function () {
    var t = host.querySelector('#pasteBox').value;
    var got = parsePasted(t);
    if (!got.length) { showToast('没有解析到「日期 + 金额」的行，请检查格式'); return; }
    got.forEach(function (r) { rowEditorAdd({ date: r.date, out: r.out, inp: r.inp }); });
    renderRows();
    files.push({ name: '粘贴文本', size: t.length, kind: 'csv', rows: got, error: null, thumb: null, status: '已解析 ' + got.length + ' 行' });
    renderFiles(); revalidate();
    showToast('已解析 ' + got.length + ' 行');
  };
  host.querySelector('#addRow').onclick = function () { rows.push({ date: '', out: '', inp: '' }); renderRows(); };

  /* ---------- 拖拽 ---------- */
  dz.onclick = function () { input.click(); };
  ['dragenter', 'dragover'].forEach(function (x) { dz.addEventListener(x, function (e) { e.preventDefault(); dz.classList.add('drag'); }); });
  ['dragleave', 'drop'].forEach(function (x) { dz.addEventListener(x, function (e) { e.preventDefault(); dz.classList.remove('drag'); }); });
  dz.addEventListener('drop', function (e) { handleFiles(e.dataTransfer.files); });
  input.addEventListener('change', function () { handleFiles(input.files); input.value = ''; });

  /* ---------- 全局拖拽守卫 + 就地导入 ----------
     ⚠⚠ 为什么必须在 document 上拦（2026-10-07 修「拖进去就不能用了」）：
       页面此前**只在拖拽区那一小块**绑了 dragover/drop，没有全局拦截。
       而营销分析面板是**开屏自动展开**的（#salesWorkspace，z-index 120，覆盖整页），
       用户的动作是「打开看板 → 往眼前的营销面板上拖日报截图」——
       落点不在拖拽区里 → 浏览器执行**默认行为：直接打开这张图片**，
       整个看板被替换成图片、数据一条没进 → 表现就是「这个功能又坏了」。
     这里做三件事：
       ① document 上对文件拖拽永远 preventDefault → 浏览器不再导航、看板不会丢；
       ② 拖到页面**任意位置**松手都当作导入（不必先开抽屉、不必对准拖拽区）；
       ③ 拖拽悬停时显示全屏提示「松开即可识别」，让用户知道这里能放。 */
  var dragHint = null, dragDepth = 0;
  function dragHintEl() {
    if (dragHint && document.body.contains(dragHint)) return dragHint;
    dragHint = document.createElement('div');
    dragHint.className = 'drag-hint';
    dragHint.innerHTML = '<div class="drag-hint-box"><div class="drag-hint-icon">⇧</div>'
      + '<b>松开即可识别日报</b><span>支持 PNG / JPG / WEBP 截图，以及 CSV / XLSX；识别完可在弹窗里核对</span></div>';
    document.body.appendChild(dragHint);
    return dragHint;
  }
  function dragHintShow(on) { var h = dragHintEl(); h.classList[on ? 'add' : 'remove']('show'); }
  /* 只接管「文件」拖拽；拖选中的文字/链接不应被拦（否则会影响正常复制粘贴） */
  function isFileDrag(e) {
    var dt = e.dataTransfer;
    if (!dt) return false;
    if (dt.types && Array.prototype.indexOf.call(dt.types, 'Files') >= 0) return true;
    return !!(dt.files && dt.files.length);
  }
  document.addEventListener('dragenter', function (e) {
    if (!isFileDrag(e)) return;
    e.preventDefault();
    dragDepth++;
    dragHintShow(true);
  }, false);
  document.addEventListener('dragover', function (e) {
    if (!isFileDrag(e)) return;
    e.preventDefault();                       // ⭐ 关键：阻止浏览器把文件当导航目标
    try { e.dataTransfer.dropEffect = 'copy'; } catch (err) { }
    dragHintShow(true);
  }, false);
  document.addEventListener('dragleave', function () {
    /* ⚠ 不判 isFileDrag：离开窗口时浏览器可能已清空 types，判了会让遮罩卡住不消失 */
    dragDepth = Math.max(0, dragDepth - 1);
    if (!dragDepth) dragHintShow(false);
  }, false);
  document.addEventListener('drop', function (e) {
    if (!isFileDrag(e)) return;
    e.preventDefault();                       // ⭐ 关键：同样阻止导航
    dragDepth = 0;
    dragHintShow(false);
    /* 拖拽区自己的 drop 监听已在目标阶段处理过 → 这里跳过，避免同一份文件导入两次 */
    if (e.target === dz || (dz.contains && dz.contains(e.target))) return;
    var list = e.dataTransfer.files;
    if (!list || !list.length) return;
    open();                                   // 先开抽屉，识别过程与结果都看得见
    handleFiles(list);
  }, false);
  /* 拖出窗口 / 取消拖拽（Esc）时兜底收掉遮罩 */
  window.addEventListener('dragend', function () { dragDepth = 0; dragHintShow(false); }, false);

  /* ⭐ 预热识别引擎（2026-10-08）。为什么：引擎与模型共约 6.7MB **不随看板发货**，
     冷态首次导入要等 12—13 秒（实测 898×258 日报图：下载 12.8s + 识别 1.7s）。
     原先下载从「用户拖图那一刻」才开始；这里改到页面空闲时提前建好，
     用户拖图时直接进入识别（约 2 秒），把等待挪到用户没在等的时段。
     ⚠ 预热必须静默：失败不弹错、不打扰，用户真拖图时会正常重试并报错。
     ⚠ 预热不得改动 pageseg 参数 —— 真实识别前由调用方自己 setParameters('11')。 */
  (function warmUpOcr() {
    /* ⭐⭐⭐ 2026-10-09：预热必须**跑到一次真实 recognize**，只建 worker 不够。
       实测：createWorker() 仅 0.36s，而「本浏览器进程第一次跑 recognize」要 36s
       —— wasm 的大头编译是**延迟到首次 recognize** 才做的。
       原先预热只 getWorker()，于是这 36s 原封不动落到了用户拖图那一刻，
       表现就是「拖进去半天识别不出来」。
       现在：worker 就绪后立刻用一张 80×32 合成图跑一次识别，把编译与 JIT 提前付清。
       用户之后拖真图 ≈1s（实测全新端口冷态 0.93s、引擎热 1.18s）。 */
    function warmRecognize(w) {
      try {
        var c = document.createElement('canvas');
        c.width = 80; c.height = 32;
        var x = c.getContext('2d');
        if (!x) return Promise.resolve();
        x.fillStyle = '#fff'; x.fillRect(0, 0, 80, 32);
        x.fillStyle = '#000'; x.font = '20px monospace'; x.fillText('8', 6, 24);
        /* ⚠ 走 queueOcr：同一 worker 上并发 recognize 会互相污染（psm 被改掉不还原）。
           ⚠ 不改 pageseg 参数 —— 真实识别前由调用方自己 setParameters('11')。 */
        return queueOcr(function () { return w.recognize(c); });
      } catch (e) { return Promise.resolve(); }
    }
    function go() {
      if (ocrWorker) { warmRecognize(ocrWorker).catch(function () { }); return; }
      if (ocrWorkerPromise) {
        ocrWorkerPromise.then(function (w) { return warmRecognize(w); }).catch(function () { });
        return;
      }
      getWorker(true).then(function (w) { return warmRecognize(w); }).catch(function () { });
    }
    var idle = window.requestIdleCallback || function (f) { return setTimeout(f, 1500); };
    /* timeout 4000 → 1500：首次编译要几十秒，越早开始越好（反正要占 CPU），
       1.5s 仍能避开首屏渲染高峰。 */
    idle(go, { timeout: 1500 });
  })();

  host.addEventListener('paste', function (e) {
    var box = host.querySelector('#pasteBox');
    if (document.activeElement === box) return;
    var t = e.clipboardData && e.clipboardData.getData('text');
    if (t) { box.value = t; }
  });

  /* ---------- 对外只读接口 ----------
     供主面板 / 其他模块取当前营收口径（不写 DOM，避免循环依赖） */
  window.OPS_REVENUE = {
    summary: function () { return summary(loadDaily()); },
    daily: function () { return loadDaily(); },
    render: function () { try { renderRevenue(); } catch (e) { console.warn('renderRevenue', e); } },
    /* 供统一数据源（september-revenue-data.js）回调：
       rows 来自其 12 字段结构，换算回本仓的 7 位数组后写入唯一真源。
       这样「从外部模块拖拽导入」也能落到同一份数据上。 */
    applyRows: function (rows, meta) {
      if (!Array.isArray(rows) || !rows.length) return;
      var daily = loadDaily();
      rows.forEach(function (r) {
        if (!r || !r.date) return;
        var cur = daily[r.date] || [];
        var arr = [];
        for (var i = 0; i < 7; i++) arr[i] = (cur[i] === undefined ? null : cur[i]);
        arr[F_OUT] = numOr(r.outpatient, arr[F_OUT]);
        arr[F_INP] = numOr(r.inpatient, arr[F_INP]);
        arr[F_FIRST] = numOr(r.first, arr[F_FIRST]);
        arr[F_AGAIN] = numOr(r.repeat, arr[F_AGAIN]);
        arr[F_INHOS] = numOr(r.ward, arr[F_INHOS]);
        arr[F_ADMIT] = numOr(r.admit, arr[F_ADMIT]);
        arr[F_DISCH] = numOr(toNum(r.dischargeFirst) + toNum(r.dischargeRepeat), arr[F_DISCH]);
        daily[r.date] = arr;
      });
      var savedR = saveDaily(daily);
      if (savedR.ok) writeJSON(LS_META, { updatedAt: new Date().toISOString(), files: [(meta && meta.source) || 'september-revenue-data'], rows: rows.length });
      else { try { console.error('[OPS] 营收数据未能保存到本机：' + savedR.reason + '（刷新后会回退）'); } catch (e) { } }
      refreshWindow();   // 新数据可能推进了「本周」，先对齐窗口再重绘
      renderRevenue();
      refreshMeta();
      /* ⚠ 必须与 applyImport 一样派发 ops:revenue-updated：
         否则「从外部模块拖入」这条路只重绘了营销面板自己，
         问题地图、医生部门卡、财务经营分析、9月指挥中心与营销报告
         （后两者经 september-revenue-data.js 转发的 september-revenue-updated）
         全都收不到通知 → 表现为「图拖进去了、数字也进库了，但面板没变／刷新后又变回去」。 */
      try { window.dispatchEvent(new CustomEvent('ops:revenue-updated', { detail: summary(loadDaily()) })); } catch (e) { }
    },
    reset: function () { resetDaily(); renderRevenue(); refreshMeta(); },
    open: open
  };
  function numOr(v, dflt) { var x = toNum(v); return x == null ? dflt : x; }
  /* 与脱敏副本（psyc.harness 的 hospital-operations-dashboard）对齐：开放导入面板入口，
     便于从侧栏 / 顶栏 / 脚本调用，而不只依赖营销面板里那个按钮 */
  window.openDataImport = open;

  /* ---------- 启动 ---------- */
  function boot() {
    renderFiles(); renderRows(); revalidate(); refreshMeta();
    /* ⭐ 首屏自检：受限环境（无痕 / 微信内置浏览器）在这里就把话说明白，
       不要让用户拖完图、刷新、再回来问「为什么没保存」。 */
    (function () {
      var c = storageCheck();
      if (!c.ok) {
        try { console.warn('[OPS] 本机存储不可用：' + c.reason + ' → 看板的导入数据在刷新后会回退。'); } catch (e) { }
        showToast('⚠ 本机无法保存数据（' + c.reason + '）：所有更新刷新后会回退，请换普通浏览器打开', 12000);
      }
    })();
    /* 首屏与「导入后」走同一条渲染路径：renderRevenue 内部会一并刷新营销面板与主面板 */
    try { renderRevenue(); } catch (e) { console.warn('renderRevenue', e); }
    /* ⭐ 拉服务端覆盖层：跨设备同步的入口。纯静态部署时这里失败，
       下面整条链路保持原样（只认 localStorage + SEED），不弹任何错误。 */
    syncFromServer().then(function (ok) {
      if (ok) {
        try { renderRevenue(); } catch (e) { }
        try { window.dispatchEvent(new CustomEvent('ops:revenue-updated', { detail: summary(loadDaily()) })); } catch (e) { }
      }
    });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', function () { setTimeout(boot, 300); });
  else setTimeout(boot, 300);

  /* ⚠ 原先此处又整体覆盖了一次 window.OPS_REVENUE，把上面的 applyRows / reset 抹掉，
     导致「统一数据源回写」链路失效。现改为只补充缺失能力，不再覆盖对象。 */
  /* 抓取日（其他模块统一引用，避免各自硬编码） */
  window.OPS_INGEST_DATE = TODAY;
})();
