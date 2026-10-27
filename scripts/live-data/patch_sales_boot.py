#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""修复「营销分析面板有时候不会自动弹出」（2026-10-26）。

原实现（2026-10-18 第三版）的三个偶发失败点：
  ① 只给 15 秒（75×200ms）、到点永久放弃 —— 弱网 / 微信 WebView 里 window.openSales 出现得晚，就再也不弹；
  ② 任何一次 Escape / 点 .mkt-close 都把 CLOSED 置真（**哪怕面板根本没开**），
     用户在搜索框按一下 Esc、或页面上任何一处 Esc，整页此后都不再弹；
  ③ 弹出后立即停止重试 —— 若被后来的脚本关掉（历史上 live-sync 就干过），只剩空白；
     且 `pageshow` 只处理 bfcache（persisted），普通回退 / 切回标签页不补弹。

本版改为：事件驱动 + 60 秒兜底轮询 + 弹出后 8 秒看护，并在 openSales 缺失时直接加 .show 兜底。
"""
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
IDX = os.path.join(ROOT, "index.html")

NEW_BOOT = r'''    if(window.applyOPSSnapshot)window.applyOPSSnapshot();
    /* 业主 2026-09-20 指示：点进链接时开屏先弹出营销分析面板。
       ⚠ 2026-10-18 修：原写法直接引用 salesWorkspace，而它是后面另一个 <script> 块里的
         const（块级作用域，不挂 window）→ 跨脚本访问必然 ReferenceError；
         外层又是 try{}catch(e){} 空吞，于是「静默不弹」，控制台也看不到报错。
         改为按 id 取节点 + 只调用已挂到 window 的 openSales，并把失败打到控制台。
       ⚠ 2026-10-26 再修（业主：「有时候不会自动弹出」）——上一版有四个会导致偶发不弹的坑：
         ① 只给 15 秒、到点永久放弃：弱网 / 微信 WebView 里 openSales 出现得晚，就再也不弹；
         ② 任何一次 Escape（**面板没开也算**）或点到 .mkt-close 就把 CLOSED 置真 ——
            用户在搜索框按一下 Esc，整页此后都不再自动弹；
         ③ 弹出后立即停止重试：一旦被后来的脚本关掉（历史上 live-sync 就这么干过），
            用户就看到「一闪就没了」，等同于没弹；
         ④ pageshow 只处理 bfcache（persisted），普通回退 / 切回标签页不补弹。
       本版：事件驱动（load / pageshow / visibilitychange）+ 60 秒兜底轮询，
       关闭意图只在「面板当时确实开着」时才记录；弹出后 8 秒内做一次「被关掉就补弹」的看护；
       openSales 不存在时直接加 .show 兜底，保证一定会出来。
       全程不重建 DOM、不改 onclick，只调页面自带的 window.openSales()。 */
    (function(){
      var CLOSED=false, TRIES=0, MAX=300, START=Date.now();   /* 300 × 200ms = 60s 兜底 */
      var WATCH=null, WARNED=false, REOPENED=0;
      window.__opsSalesClosed=false;
      function panel(){return document.getElementById('salesWorkspace')}
      function isOpen(){var w=panel();return !!(w&&w.classList.contains('show'))}
      function stopWatch(){if(WATCH){clearInterval(WATCH);WATCH=null}}
      function markClosed(){
        /* 关键：面板没开着时按 Esc / 点别处 ≠ 用户想关掉开屏弹窗，不能记关闭意图 */
        if(!isOpen())return;
        CLOSED=true;window.__opsSalesClosed=true;stopWatch();
      }
      document.addEventListener('click',function(e){
        var t=e.target;
        if(!t||!t.closest)return;
        if(t.closest('.mkt-close,.sales-close,[data-sales-close]'))markClosed();
      },true);
      document.addEventListener('keydown',function(e){if(e.key==='Escape')markClosed()},true);
      function forceShow(){
        var w=panel();
        if(!w)return false;
        if(typeof window.openSales==='function'){
          try{window.openSales()}catch(err){
            if(!WARNED){WARNED=true;console.warn('[sales] 开屏弹窗失败，改用直接展开：',err)}
          }
        }
        if(!w.classList.contains('show')){
          /* 退路：openSales 未就绪 / 内部报错时也要把面板露出来 */
          w.classList.add('show');
          try{document.body.style.overflow='hidden'}catch(e){}
        }
        return w.classList.contains('show');
      }
      function watchClosed(){
        if(WATCH||CLOSED)return;
        WATCH=setInterval(function(){
          if(CLOSED){stopWatch();return}
          if(!isOpen()){
            if(REOPENED<2&&Date.now()-START<60000){REOPENED++;forceShow();}
            else{stopWatch();}
          }
        },800);
        setTimeout(stopWatch,8000);
      }
      function tick(){
        if(CLOSED)return;
        if(isOpen()){watchClosed();return}         /* 已经弹出来了：进入看护，不再轮询 */
        if(forceShow()){watchClosed();return}
        if(++TRIES>=MAX||Date.now()-START>60000){
          if(!WARNED){WARNED=true;console.warn('[sales] 开屏弹窗 60 秒内未能弹出，放弃自动展开（手动入口仍在）')}
          return;
        }
        setTimeout(tick,200);
      }
      function start(){setTimeout(tick,100)}
      if(document.readyState==='loading'){document.addEventListener('DOMContentLoaded',start)}
      else{start()}
      /* 资源全部就绪后再催一次（图片/字体/大脚本加载完常常晚于 DOMContentLoaded） */
      window.addEventListener('load',function(){if(!CLOSED&&!isOpen())start()});
      /* 从往返缓存 / 普通回退 / 微信 WebView 恢复时都补弹 */
      window.addEventListener('pageshow',function(e){
        if(window.__opsSalesClosed)return;
        CLOSED=false;TRIES=0;START=Date.now();start();
      });
      /* 切回标签页时若还没弹过、也不在开的状态，补一次 */
      document.addEventListener('visibilitychange',function(){
        if(!document.hidden&&!CLOSED&&!isOpen()&&TRIES<MAX)start();
      });
    })();
'''


def main():
    s = io.open(IDX, encoding="utf-8").read()
    start = s.find("    if(window.applyOPSSnapshot)window.applyOPSSnapshot();")
    end = s.find("  </script>", start)
    assert start > 0 and end > start, "定位失败"
    old = s[start:end]
    assert "__opsSalesClosed" in old and "MAX=75" in old, "旧块内容与预期不符（可能已改过）"

    s = s[:start] + NEW_BOOT + s[end:]

    # 防御：这些旧 V1 元素在 marketing-redesign.js 重写外壳后可能不存在，
    # 原写法 `document.getElementById('salesUndo').onclick=...` 会抛 TypeError，
    # 并**中断本 script 块后续全部绑定**（deptDaily / openDeptV2 覆盖 / deptSalesList 全部失效）。
    reps = [
        ("    document.getElementById('salesUndo').onclick=()=>selectSalesMonth(9);",
         "    var _salesUndo=document.getElementById('salesUndo');if(_salesUndo)_salesUndo.onclick=()=>selectSalesMonth(9);"),
        ("    document.getElementById('salesEdit').onclick=()=>toast('当前为只读经营看板；数据按销售进度页和仓库已确认口径展示');",
         "    var _salesEdit=document.getElementById('salesEdit');if(_salesEdit)_salesEdit.onclick=()=>toast('当前为只读经营看板；数据按销售进度页和仓库已确认口径展示');"),
        ("    document.getElementById('salesReport').onclick=()=>{",
         "    var _salesReport=document.getElementById('salesReport');if(_salesReport)_salesReport.onclick=()=>{"),
    ]
    for a, b in reps:
        if s.count(a) == 1:
            s = s.replace(a, b)
        elif s.count(b) == 1:
            print("  · 已打过（跳过）：" + b[:60])
        else:
            print("  ⚠ 未匹配（跳过）：" + a[:60])

    io.open(IDX, "w", encoding="utf-8").write(s)
    print("开屏弹窗逻辑已替换：%d → %d 字符" % (len(old), len(NEW_BOOT)))
    print("MAX=75 残留：", s.count("MAX=75"))
    print("MAX=300 生效：", s.count("MAX=300"))


if __name__ == "__main__":
    main()
