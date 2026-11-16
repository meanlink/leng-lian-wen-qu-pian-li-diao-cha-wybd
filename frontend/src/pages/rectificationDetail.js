import {rectifications} from '../api/entities.js';
import {workspace} from '../stores/workspace.js';
import {session} from '../stores/session.js';
import {heading} from '../components/common/shell.js';
import {RectStatus,MeasureStatus,PackageStatus,DisputeStatus,DisputeKind,Resolution,FieldLabel,RectEvent} from '../constants/enums.js';
import {esc,date,notify} from '../utils/dom.js';
import {submit} from '../hooks/forms.js';
const pill=(cls,label)=>'<span class="status '+esc(cls)+'">'+esc(label)+'</span>';
const fmtVal=v=>v===undefined||v===null||v===''?'（空）':typeof v==='boolean'?(v?'是':'否'):Array.isArray(v)?(v.length?v.join('；'):'（空）'):String(v);
const show=v=>v===undefined||v===null||v===''?'<i>（空）</i>':typeof v==='boolean'?(v?'已完成':'未完成'):Array.isArray(v)?(v.length?esc(v.join('；')):'<i>（空）</i>'):esc(String(v));
function measureCard(m,canEdit){
 return '<article class="measure-card"><header><strong>#'+m.id+' · '+esc(m.title)+'</strong><span class="measure-meta">'+pill(m.status,MeasureStatus[m.status]||m.status)+'<small>v'+m.version+'</small></span></header>'
 +(m.detail?'<p class="m-detail">'+esc(m.detail)+'</p>':'')
 +'<div class="m-meta"><span>责任人 '+esc(m.assignee)+'</span><span>更新 '+date(m.updated_at)+'</span>'+(m.completed_at?'<span>完成 '+date(m.completed_at)+'</span>':'')+'</div>'
 +'<dl class="m-body"><dt>整改说明</dt><dd>'+show(m.note)+'</dd><dt>证据</dt><dd>'+(m.evidence&&m.evidence.length?'<ul>'+m.evidence.map(e=>'<li>'+esc(e)+'</li>').join('')+'</ul>':'<i>（无）</i>')+'</dd></dl>'
 +(canEdit?'<div class="m-actions"><button class="text-button" data-edit="'+m.id+'">在线修改</button>'+(m.status!=='revoked'?'<button class="text-button danger" data-revoke="'+m.id+'">撤销措施</button>':'')+'</div>'
 +'<form class="edit-form" data-form="'+m.id+'" hidden><div class="parameter-grid"><label>标题<input name="title" value="'+esc(m.title)+'" required minlength="2" maxlength="160"></label><label>责任人（改派将使原责任人未回传包失效）<input name="assignee" value="'+esc(m.assignee)+'" required minlength="2" maxlength="80"></label></div><label>说明<textarea name="detail" rows="2" maxlength="500">'+esc(m.detail)+'</textarea></label><label>整改说明（在线改动，与回传同项异改将转待裁定）<textarea name="note" rows="2" maxlength="1000">'+esc(m.note)+'</textarea></label><label>证据（每行一条）<textarea name="evidence" rows="2">'+esc((m.evidence||[]).join('\n'))+'</textarea></label><button type="submit" class="primary small">保存在线改动</button></form>':'')
 +'</article>';
}
function decisionText(d){
 if(d.decision==='take_package')return '采用回传 · 「'+d.title+'」'+(FieldLabel[d.field]||d.field||'')+'（领取后线上未变更）';
 if(d.decision==='same_change')return '双方一致 · 「'+d.title+'」'+(FieldLabel[d.field]||d.field||'')+'，无需取舍';
 return '转待裁定 · 「'+d.title+'」'+(d.field?(FieldLabel[d.field]||d.field):'整项措施')+'（'+d.reason+'）';
}
function pkgCard(p){
 return '<article class="pkg-card"><div><strong>包 #'+p.id+' · '+esc(p.assignee)+'</strong><p>第 '+p.round+' 轮 · '+esc(PackageStatus[p.status]||p.status)+(p.void_reason?' · '+esc(p.void_reason):'')+'</p><small>'+esc(p.claimed_by)+' 领于 '+date(p.claimed_at)+(p.returned_at?' · 回传 '+date(p.returned_at):'')+'</small></div><div class="pkg-actions"><button class="text-button" data-pkg-content="'+p.id+'">查看内容</button></div></article>'
 +(p.result&&p.result.summary?'<details class="receipt"><summary>合并回执：采用 '+p.result.summary.applied+' · 一致 '+p.result.summary.same+' · 转裁定 '+p.result.summary.disputes+'</summary><ul>'+(p.result.decisions||[]).map(d=>'<li>'+esc(decisionText(d))+'</li>').join('')+(p.result.decisions&&p.result.decisions.length?'':'<li>回传内容与领取时一致，无改动。</li>')+'</ul></details>':'');
}
function disputeValues(d){
 if(d.kind==='conflict')return '<div class="values3"><div><span>领取时</span>'+show(d.base_value.value)+'</div><div><span>线上现值（保留中）</span>'+show(d.online_value.value)+'</div><div><span>回传值</span>'+show(d.incoming_value.value)+'</div></div>';
 const base=d.base_value.changes||{},inc=d.incoming_value.changes||{};
 return '<div class="values3"><div><span>领取时</span>'+Object.entries(base).map(([f,v])=>esc((FieldLabel[f]||f)+'：'+fmtVal(v))).join('<br>')+'</div><div><span>线上现值</span>措施已撤销</div><div><span>回传修改</span>'+Object.entries(inc).map(([f,v])=>esc((FieldLabel[f]||f)+' → '+fmtVal(v))).join('<br>')+'</div></div>';
}
function disputeCard(d,measures,isAdmin,open){
 const m=measures.find(x=>x.id===d.measure_id)||{};
 return '<article class="dispute-card"><header><strong>争议 #'+d.id+' · '+esc(m.title||'措施 '+d.measure_id)+'</strong><span>'+pill(d.kind,DisputeKind[d.kind]||d.kind)+' '+pill(d.status,DisputeStatus[d.status]||d.status)+'</span></header>'
 +'<p class="d-meta">'+esc(d.kind==='conflict'?'字段 '+(FieldLabel[d.field]||d.field):'整项措施（已撤销）')+' · 争议时版本 v'+d.measure_version+' · 当前 v'+(m.version||'?')+' · '+date(d.created_at)+'</p>'
 +disputeValues(d)
 +(d.status==='pending'
   ?(isAdmin&&open?'<div class="d-actions"><button class="button small" data-resolve="'+d.id+':keep_online" data-measure="'+d.measure_id+'">保留线上</button><button class="button small primary" data-resolve="'+d.id+':take_package" data-measure="'+d.measure_id+'">采用回传</button></div><p class="hint">若裁定期间措施有新的在线改动，将拒绝覆盖新值并提示刷新。</p>':'<p class="hint">待业务负责人裁定。</p>')
   :'<p class="d-meta">已裁定：'+esc(Resolution[d.resolution]||d.resolution)+' · '+esc(d.resolved_by)+' · '+date(d.resolved_at)+'</p>')
 +'</article>';
}
function eventDetail(e){
 const d=e.detail||{};
 switch(e.action){
  case 'order.created':return '来源调查 #'+d.job_id+' · 措施 '+d.measures+' 项';
  case 'measure.added':return '「'+d.title+'」→ '+d.assignee;
  case 'measure.edited':return '「'+d.measure+'」修改 '+Object.keys(d.fields||{}).join('、');
  case 'measure.reassigned':return '「'+d.measure+'」'+d.from+' → '+d.to+(d.voided_packages&&d.voided_packages.length?'，作废旧包 '+d.voided_packages.map(p=>'#'+p).join('、'):'');
  case 'measure.revoked':return '「'+d.measure+'」';
  case 'package.claimed':return '包 #'+d.package+' · '+d.assignee+' · 第 '+d.round+' 轮 · 含措施 '+(d.measures||[]).length+' 项';
  case 'package.returned':return '包 #'+d.package+' · 采用 '+((d.summary||{}).applied||0)+' · 一致 '+((d.summary||{}).same||0)+' · 转裁定 '+((d.summary||{}).disputes||0);
  case 'package.voided':return '包 #'+d.package+' · '+d.reason;
  case 'merge.take_package':return '「'+d.measure+'」'+d.field_label+'：领取后线上未变，采用回传「'+fmtVal(d.value)+'」';
  case 'merge.same_change':return '「'+d.measure+'」'+d.field_label+'：双方一致「'+fmtVal(d.value)+'」';
  case 'merge.to_dispute':return '「'+d.measure+'」'+(d.field_label||'整项措施')+'：'+(d.kind==='revoked'?'措施已在线撤销':'同项异改')+'，保留线上并转待裁定';
  case 'dispute.raised':return '争议 #'+d.dispute+' · 「'+d.measure+'」'+(d.field_label||'整项措施');
  case 'dispute.resolved':return '争议 #'+d.dispute+' · '+esc(Resolution[d.resolution]||d.resolution)+' · 「'+d.measure+'」→ v'+d.version;
  case 'order.accepted':return '第 '+d.round+' 轮 · 固定 '+d.measures+' 项措施与证据';
  case 'order.returned':return '第 '+d.from_round+' 轮 → 第 '+d.to_round+' 轮 · 重开 '+d.reopened+' 项'+(d.note?' · '+d.note:'');
  default:return '';
 }
}
export async function rectDetail(id){
 const d=await rectifications.get(id);workspace.rect=d;
 const o=d.order,measures=d.measures,packages=d.packages,disputes=d.disputes,events=d.events;
 if(workspace.rectClaimed&&workspace.rectClaimed.order_id!==o.id)workspace.rectClaimed=null;
 if(workspace.rectClaimed){const fresh=packages.find(p=>p.id===workspace.rectClaimed.id);if(fresh)workspace.rectClaimed={...fresh,content:workspace.rectClaimed.content};}
 const open=o.status==='open',canEdit=open&&session.user.role!=='viewer',isAdmin=session.user.role==='admin';
 const total=measures.length,closed=measures.filter(m=>m.status==='done'||m.status==='revoked').length;
 const pending=disputes.filter(x=>x.status==='pending');
 const okMeasures=total>0&&closed===total,okDisputes=pending.length===0;
 const assignees=[...new Set(measures.filter(m=>m.status!=='revoked').map(m=>m.assignee))];
 const claimed=workspace.rectClaimed;
 const snap=o.snapshot||{};
 return heading('05 / RECTIFICATION','整改单 #'+o.id+' · '+o.title,'来源调查 #'+o.job_id+' · '+esc(o.created_by)+' 建立于 '+date(o.created_at)+'。','<a class="button" href="#/rectifications">← 整改单列表</a> <button class="button" id="refresh-rectd">刷新 ↻</button>')
 +'<div class="result-selector">'+pill(o.status,RectStatus[o.status]||o.status)+'<span class="round-badge">第 '+o.round+' 轮</span><span>措施 '+closed+'/'+total+' 完成</span>'+(pending.length?'<span class="flag">'+pending.length+' 项争议待裁定</span>':'<span>无待裁定争议</span>')+(o.accepted_at?'<span>验收于 '+date(o.accepted_at)+'</span>':'')+'</div>'
 +(!open?'<section class="panel accepted-banner"><div class="section-title"><h2>已验收固定</h2><span>第 '+(snap.round||o.round)+' 轮 · '+esc(snap.accepted_by||'')+'</span></div><p>验收时冻结的全部措施与证据快照如下，内容不可再变更。</p>'+(snap.measures||[]).map(m=>'<div class="snap-row"><header><strong>'+esc(m.title)+'</strong><span>'+esc(MeasureStatus[m.status]||m.status)+' · '+esc(m.assignee)+'</span></header><p>'+esc(m.note||'（无整改说明）')+'</p><small>证据：'+((m.evidence||[]).join('；')||'无')+'</small></div>').join('')+'</section>':'')
 +'<div class="rect-detail-grid"><div>'
 +'<section class="panel"><div class="section-title"><h2>整改措施</h2><span>'+total+' 项</span></div>'+measures.map(m=>measureCard(m,canEdit)).join('')
 +(canEdit?'<form id="add-measure-form" class="add-measure"><div class="section-title"><h2>追加措施</h2></div><div class="parameter-grid"><label>标题<input name="title" required minlength="2" maxlength="160"></label><label>责任人<input name="assignee" required minlength="2" maxlength="80"></label></div><label>说明<textarea name="detail" rows="2" maxlength="500"></textarea></label><button type="submit" class="primary small">添加措施</button></form>':'')
 +'</section></div><div>'
 +'<section class="panel"><div class="section-title"><h2>领包 · 离线填写</h2><span>领取时内容冻结为对照基线</span></div>'
 +(canEdit?(assignees.length?'<form id="claim-form" class="inline-form"><label>责任人<select name="assignee">'+assignees.map(a=>'<option>'+esc(a)+'</option>').join('')+'</select></label><button type="submit" class="primary">领取填写包</button></form><p class="hint">同一责任人同一轮次重复领取返回原包；重新指派后原责任人的未回传包失效。</p>':'<p class="hint">当前没有可领取的措施。</p>'):'<p class="hint">'+(open?'观察员仅可查看。':'已验收，不可再领取。')+'</p>')
 +(claimed?'<div class="claimed-box"><div class="section-title"><h2>包 #'+claimed.id+' · '+esc(claimed.assignee)+'</h2><span>第 '+claimed.round+' 轮 · '+esc(PackageStatus[claimed.status]||claimed.status)+'</span></div><pre class="pkg">'+esc(JSON.stringify(claimed.content,null,2))+'</pre><button class="button small" id="download-pkg">下载填写包 JSON</button>'+(claimed.status==='claimed'&&canEdit?' <button class="button small" id="fill-now">在页面中离线填写</button>':'')+'</div>':'')
 +'<div class="pkg-list">'+packages.map(pkgCard).join('')+'</div></section>'
 +'<section class="panel"><div class="section-title"><h2>回传 · 合并变动</h2><span>中断可直接重试，不重复登记</span></div>'
 +(canEdit?'<div class="return-tools"><input type="file" id="pkg-file" accept=".json"><button type="button" class="button small" id="load-draft">载入本机离线草稿</button></div><div id="fill-area"></div><form id="return-form"><label>回传内容（填写包 JSON）<textarea name="payload" rows="8" required placeholder="领取填写包后离线填写，粘贴或上传 JSON"></textarea></label><button type="submit" class="primary">提交回传并合并</button></form><p class="hint">对照领取时与线上现值合并：互不影响的修改各自保留，同项异改或已撤销措施转待裁定。同一包重复提交返回原回执；同一包换了内容将被拒收。</p>':'<p class="hint">观察员仅可查看。</p>')
 +'</section>'
 +'<section class="panel"><div class="section-title"><h2>裁定</h2><span>'+pending.length+' 项待裁定</span></div>'
 +(disputes.length?disputes.map(x=>disputeCard(x,measures,isAdmin,open)).join(''):'<p class="empty">暂无争议。回传与线上同项异改时，争议会出现在这里。</p>')
 +'</section>'
 +'<section class="panel"><div class="section-title"><h2>验收</h2><span>验收后固定全部措施与证据</span></div>'
 +'<div class="checkline '+(okMeasures?'ok':'')+'">'+(okMeasures?'✓':'✗')+' 全部措施已完成或撤销（'+closed+'/'+total+'）</div>'
 +'<div class="checkline '+(okDisputes?'ok':'')+'">'+(okDisputes?'✓':'✗')+' 无待裁定争议（'+pending.length+' 项未清）</div>'
 +(open?(isAdmin?'<div class="d-actions"><button class="primary" id="accept-order" '+((okMeasures&&okDisputes)?'':'disabled')+'>验收固定</button></div><form id="sendback-form" class="inline-form"><label>退回说明<input name="note" placeholder="退回原因（可选）" maxlength="300"></label><button type="submit" class="button" '+(okDisputes?'':'disabled')+'>退回整改，开启新一轮</button></form><p class="hint">争议未清不验收。退回后已完成措施重新打开，未回传的旧包失效，旧包不能关闭新一轮措施。</p>':'<p class="hint">由业务负责人验收或退回。</p>'):'')
 +'</section></div></div>'
 +'<section class="panel"><div class="section-title"><h2>取舍依据</h2><span>'+events.length+' 条记录</span></div><ul class="timeline rect-events">'+events.map(e=>'<li><div><strong>'+esc(RectEvent[e.action]||e.action)+'</strong><p>'+eventDetail(e)+'</p></div><span>'+esc(e.actor)+' · '+date(e.at)+'</span></li>').join('')+'</ul></section>';
}
function renderFill(draft){
 return '<div class="section-title"><h2>离线填写 · 包 #'+draft.package_id+'（'+esc(draft.assignee)+'）</h2><span>第 '+draft.round+' 轮</span></div>'
 +draft.measures.map(m=>'<fieldset class="fill-measure" data-fill="'+m.id+'"><legend>#'+m.id+' · '+esc(m.title)+'</legend><label class="checkline"><input type="checkbox" data-done '+(m.done?'checked':'')+'> 现场已完成</label><label>整改说明<input data-note value="'+esc(m.note||'')+'" maxlength="1000"></label><label>证据（每行一条）<textarea data-evidence rows="2">'+esc((m.evidence||[]).join('\n'))+'</textarea></label></fieldset>').join('')
 +'<button type="button" class="button small" id="gen-payload">生成回传 JSON →</button>';
}
export function bindRectDetail(refresh,id){
 const openDraft=draft=>{
  const area=document.querySelector('#fill-area');if(!area)return;
  area.innerHTML=renderFill(draft);
  document.querySelector('#gen-payload').onclick=()=>{
   const payload={package_id:draft.package_id,order_id:draft.order_id,round:draft.round,assignee:draft.assignee,
    measures:[...area.querySelectorAll('[data-fill]')].map(fs=>({id:Number(fs.dataset.fill),done:fs.querySelector('[data-done]').checked,note:fs.querySelector('[data-note]').value,evidence:fs.querySelector('[data-evidence]').value.split('\n').map(s=>s.trim()).filter(Boolean)}))};
   document.querySelector('[name=payload]').value=JSON.stringify(payload,null,2);
   notify('已生成回传 JSON，可提交回传');
  };
 };
 document.querySelector('#refresh-rectd').onclick=refresh;
 submit(document.querySelector('#add-measure-form'),async f=>{await rectifications.addMeasure(id,{title:f.get('title'),assignee:f.get('assignee'),detail:f.get('detail')});notify('措施已添加');await refresh();});
 document.querySelectorAll('[data-edit]').forEach(b=>b.onclick=()=>{const f=document.querySelector('[data-form="'+b.dataset.edit+'"]');if(f)f.hidden=!f.hidden;});
 document.querySelectorAll('.edit-form').forEach(form=>submit(form,async f=>{
  await rectifications.patchMeasure(id,form.dataset.form,{title:f.get('title'),assignee:f.get('assignee'),detail:f.get('detail'),note:f.get('note'),evidence:f.get('evidence').split('\n').map(s=>s.trim()).filter(Boolean)});
  notify('在线改动已保存');await refresh();
 }));
 document.querySelectorAll('[data-revoke]').forEach(b=>b.onclick=async()=>{if(!confirm('确定撤销该措施？之后回传对它的修改将转待裁定。'))return;try{await rectifications.patchMeasure(id,b.dataset.revoke,{revoke:true});notify('措施已撤销');await refresh();}catch(e){notify(e.message,true);}});
 const claimForm=document.querySelector('#claim-form');
 if(claimForm)submit(claimForm,async f=>{
  const pkg=await rectifications.claim(id,f.get('assignee'));
  localStorage.setItem('rectpkg-'+id,JSON.stringify(pkg.content));
  workspace.rectClaimed=pkg;notify('填写包 #'+pkg.id+' 已领取，内容已存为本机离线草稿');await refresh();
 });
 document.querySelectorAll('[data-pkg-content]').forEach(b=>b.onclick=async()=>{try{workspace.rectClaimed=await rectifications.getPackage(id,b.dataset.pkgContent);await refresh();}catch(e){notify(e.message,true);}});
 const dl=document.querySelector('#download-pkg');
 if(dl)dl.onclick=()=>{const c=workspace.rectClaimed;const u=URL.createObjectURL(new Blob([JSON.stringify(c.content,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=u;a.download='整改填写包-'+c.id+'.json';a.click();setTimeout(()=>URL.revokeObjectURL(u),1000);};
 const fillNow=document.querySelector('#fill-now');
 if(fillNow)fillNow.onclick=()=>{const c=workspace.rectClaimed;localStorage.setItem('rectpkg-'+id,JSON.stringify(c.content));openDraft(c.content);};
 const loadDraft=document.querySelector('#load-draft');
 if(loadDraft)loadDraft.onclick=()=>{
  const raw=localStorage.getItem('rectpkg-'+id);
  if(!raw){notify('本机没有该整改单的离线草稿，请先领取填写包',true);return;}
  try{openDraft(JSON.parse(raw));}catch(e){notify('草稿已损坏，请重新领取填写包',true);}
 };
 const fileInput=document.querySelector('#pkg-file');
 if(fileInput)fileInput.addEventListener('change',async e=>{const file=e.target.files[0];if(!file)return;try{const parsed=JSON.parse(await file.text());document.querySelector('[name=payload]').value=JSON.stringify(parsed,null,2);}catch(err){notify('文件不是有效的填写包 JSON',true);}});
 const returnForm=document.querySelector('#return-form');
 if(returnForm)submit(returnForm,async f=>{
  let payload;try{payload=JSON.parse(f.get('payload'));}catch(e){throw new Error('回传内容不是有效 JSON');}
  if(!payload||!payload.package_id)throw new Error('回传内容缺少 package_id');
  const res=await rectifications.returnPackage(id,payload.package_id,payload);
  const s=(res.result&&res.result.summary)||{applied:0,same:0,disputes:0};
  notify('回传已合并：采用 '+s.applied+' 项 · 双方一致 '+s.same+' 项 · 转待裁定 '+s.disputes+' 项');
  const raw=localStorage.getItem('rectpkg-'+id);
  if(raw){try{if(JSON.parse(raw).package_id===payload.package_id)localStorage.removeItem('rectpkg-'+id);}catch(e){}}
  if(workspace.rectClaimed&&workspace.rectClaimed.id===payload.package_id)workspace.rectClaimed=null;
  await refresh();
 });
 document.querySelectorAll('[data-resolve]').forEach(b=>b.onclick=async()=>{
  const parts=b.dataset.resolve.split(':'),did=Number(parts[0]),resolution=parts[1];
  const m=(workspace.rect.measures||[]).find(x=>x.id===Number(b.dataset.measure));
  try{await rectifications.resolve(id,did,{resolution,expected_version:m?m.version:0});notify('裁定已登记');}catch(e){notify(e.message,true);}
  await refresh();
 });
 const acceptBtn=document.querySelector('#accept-order');
 if(acceptBtn)acceptBtn.onclick=async()=>{try{await rectifications.accept(id);notify('已验收固定，全部措施与证据已冻结');}catch(e){notify(e.message,true);}await refresh();};
 const sendbackForm=document.querySelector('#sendback-form');
 if(sendbackForm)submit(sendbackForm,async f=>{const o=await rectifications.sendBack(id,f.get('note')||'');notify('已退回整改，开启第 '+o.round+' 轮');await refresh();});
}
