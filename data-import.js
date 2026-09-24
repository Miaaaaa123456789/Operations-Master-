(function(){
  const host=document.createElement('div');
  host.className='import-backdrop';host.id='importBackdrop';
  host.innerHTML=`<section class="import-drawer" role="dialog" aria-modal="true" aria-label="导入并更新分析数据">
    <header class="import-head"><div><h2>导入并更新分析数据</h2><p>识别、校验后再更新，原始数据不会被直接覆盖</p></div><button class="import-close" aria-label="关闭">×</button></header>
    <div class="import-body">
      <input id="importFile" type="file" multiple accept=".png,.jpg,.jpeg,.csv,.xlsx,.xls" hidden>
      <div class="drop-zone" id="dropZone"><div class="drop-icon">⇧</div><b>拖入图片或表格文件</b><span>支持 PNG、JPG、CSV、XLSX、XLS · 可多选</span></div>
      <div class="import-steps"><div class="import-step active" data-n="1">上传</div><div class="import-step" data-n="2">识别</div><div class="import-step" data-n="3">校验</div><div class="import-step" data-n="4">确认更新</div></div>
      <section class="import-card"><h3>本次文件</h3><div id="fileList"><div class="file-row"><div class="file-type">XLSX</div><div><b>9月营业日报.xlsx</b><span>28 KB · 字段表头已识别</span></div><em class="status-ok">解析完成</em></div><div class="file-row"><div class="file-type image">IMG</div><div><b>医生工作量截图.png</b><span>1.8 MB · OCR 识别 96%</span></div><em class="status-ok">待校验</em></div></div></section>
      <section class="import-card"><h3>字段映射预览</h3><table class="map-table"><thead><tr><th>识别字段</th><th>看板指标</th><th>新值</th><th>状态</th></tr></thead><tbody id="mapRows"><tr><td>当日收入合计</td><td>营业额</td><td>153.89万</td><td><span class="tag">匹配</span></td></tr><tr><td>门诊收入</td><td>收入结构</td><td>92.40万</td><td><span class="tag">匹配</span></td></tr><tr><td>入院</td><td>转化漏斗</td><td>15人</td><td><span class="tag">待核</span></td></tr></tbody></table></section>
      <section class="import-card"><h3>数据校验</h3><div class="verify-grid"><div><b>12</b>新增</div><div><b>6</b>更新</div><div class="conflict"><b>2</b>冲突</div><div><b>1</b>缺失</div></div><div class="conflict-box"><b>冲突：入院人数</b><p>营业日报为 14 人，医生工作量截图为 15 人。请选择采用值，或保留为待核。</p><div class="choice-row"><button data-choice="14">采用表格 14</button><button data-choice="15">采用截图 15</button><button data-choice="pending">标记待核</button></div></div><label class="audit"><input type="checkbox" checked> 保存本次导入前的数据快照，并记录来源、导入时间、操作人与规则版本</label></section>
    </div><footer class="import-footer"><button class="cancel">取消</button><button class="confirm" disabled>解决冲突后确认更新</button></footer></section>`;
  document.body.appendChild(host);
  const toast=document.createElement('div');toast.className='demo-toast';document.body.appendChild(toast);
  const close=()=>host.classList.remove('show');
  const open=()=>{host.classList.add('show');document.querySelector('.import-drawer').scrollTop=0};
  host.querySelector('.import-close').onclick=close;host.querySelector('.cancel').onclick=close;
  host.addEventListener('click',e=>{if(e.target===host)close()});
  const tools=document.querySelector('.sales-month-tools');
  if(tools){const b=document.createElement('button');b.className='data-update-btn';b.innerHTML='⇧ 更新数据';b.onclick=open;tools.prepend(b)}
  const v2Import=document.querySelector('.mkt-import');if(v2Import)v2Import.onclick=open;
  const edit=document.getElementById('salesEdit');if(edit)edit.onclick=open;
  const dz=host.querySelector('#dropZone'),input=host.querySelector('#importFile'),list=host.querySelector('#fileList');
  dz.onclick=()=>input.click();['dragenter','dragover'].forEach(x=>dz.addEventListener(x,e=>{e.preventDefault();dz.classList.add('drag')}));['dragleave','drop'].forEach(x=>dz.addEventListener(x,e=>{e.preventDefault();dz.classList.remove('drag')}));
  dz.addEventListener('drop',e=>handle(e.dataTransfer.files));input.addEventListener('change',()=>handle(input.files));
  function handle(files){if(!files.length)return;list.innerHTML='';Array.from(files).forEach((f,i)=>{const image=/image/.test(f.type),row=document.createElement('div');row.className='file-row';row.innerHTML=`<div class="file-type ${image?'image':''}">${image?'IMG':(f.name.split('.').pop()||'FILE').toUpperCase()}</div><div><b>${f.name.replace(/[<>]/g,'')}</b><span>${Math.max(1,Math.round(f.size/1024))} KB · ${image?'正在进行 OCR 识别':'正在解析表头与数据行'}</span></div><em class="status-ok">识别中</em>`;list.appendChild(row);setTimeout(()=>{row.querySelector('span').textContent=`${Math.max(1,Math.round(f.size/1024))} KB · ${image?'OCR 识别 96%':'字段表头已识别'}`;row.querySelector('em').textContent=i?'待校验':'解析完成'},650+i*260)});host.querySelectorAll('.import-step').forEach((s,i)=>s.classList.toggle('done',i<2));host.querySelectorAll('.import-step')[2].classList.add('active')}
  host.querySelectorAll('[data-choice]').forEach(b=>b.onclick=()=>{host.querySelectorAll('[data-choice]').forEach(x=>x.classList.remove('active'));b.classList.add('active');const c=host.querySelector('.confirm');c.disabled=false;c.textContent=b.dataset.choice==='pending'?'保留待核并更新其余数据':'确认更新分析数据'});
  host.querySelector('.confirm').onclick=()=>{close();toast.textContent='已生成更新预览：原数据快照已保留';toast.classList.add('show');setTimeout(()=>toast.classList.remove('show'),2400)};
  document.addEventListener('keydown',e=>{if(e.key==='Escape'&&host.classList.contains('show'))close()});
  const nursing=document.getElementById('sideNursingPerf');if(nursing)nursing.remove();
})();
