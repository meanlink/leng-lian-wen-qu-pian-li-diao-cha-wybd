import {jobs,rectifications} from '../api/entities.js';
import {session} from '../stores/session.js';
import {heading} from '../components/common/shell.js';
import {RectStatus} from '../constants/enums.js';
import {esc,date,notify} from '../utils/dom.js';
import {submit} from '../hooks/forms.js';
const row='<div class="measure-row" data-row><input name="m-title" placeholder="措施标题，如：更换 3 号车门封条" required minlength="2" maxlength="160"><input name="m-assignee" placeholder="责任人" required minlength="2" maxlength="80"><input name="m-detail" placeholder="说明（可选）" maxlength="500"><button type="button" class="text-button" data-remove>移除</button></div>';
export async function rectPage(){
 const [list,allJobs]=await Promise.all([rectifications.list(),jobs.list()]);
 const approved=allJobs.filter(j=>j.approved&&j.status==='completed');
 const canDispatch=session.user.role!=='viewer'&&approved.length>0;
 return heading('05 / RECTIFICATION','整改闭环','从获批调查建立整改单，措施分派到责任人；现场领取填写包离线填写，回传时与线上内容对照合并，争议裁定后再验收。','<button class="button" id="refresh-rect">刷新 ↻</button>')
 +'<div class="rect-grid"><section class="panel"><div class="section-title"><h2>派单 · 建立整改单</h2><span>仅获批调查</span></div>'
 +'<form id="rect-form"><label>整改单名称<input name="title" required minlength="2" maxlength="160" value="B 线保温包装复核整改"></label><label>来源调查（已获批）<select name="job_id" required>'+approved.map(j=>'<option value="'+j.id+'">'+esc(j.name)+'</option>').join('')+'</select></label><div class="section-title"><h2>整改措施与责任人</h2><span>至少 1 项</span></div><div id="measure-rows">'+row+'</div><button type="button" class="button small" id="add-row">+ 添加措施</button><button type="submit" class="primary" '+(canDispatch?'':'disabled')+'>建立整改单并分派</button></form><p class="hint">建单后责任人可在详情页领取填写包；观察员只能查看。'+(approved.length?'':'暂无获批调查，请先在结果复核页批准结论。')+'</p></section>'
 +'<section><div class="section-title"><h2>整改单</h2><span>'+list.length+' 单</span></div><div class="order-list">'
 +(list.map(o=>{const c=o.counts||{};return '<a class="order-card" href="#/rectifications/'+o.id+'"><div><strong>'+esc(o.title)+'</strong><p>第 '+o.round+' 轮 · 措施 '+(c.done||0)+'/'+(c.measures||0)+' 完成'+(c.revoked?' · 撤销 '+c.revoked:'')+(c.disputes_pending?' · <b class="flag">'+c.disputes_pending+' 项待裁定</b>':'')+'</p><small>来源调查 #'+o.job_id+' · '+esc(o.created_by)+' · '+date(o.created_at)+'</small></div><span class="status '+o.status+'">'+esc(RectStatus[o.status]||o.status)+'</span></a>';}).join('')||'<p class="empty">尚无整改单。从左侧选择获批调查建立第一张整改单。</p>')
 +'</div><p class="hint">回传合并规则：对照领取时与线上现值，互不影响的修改各自保留；同项异改或已撤销措施的回传修改转待裁定；争议未清不验收。</p></section></div>';
}
export function bindRect(refresh){
 document.querySelector('#refresh-rect').onclick=refresh;
 document.querySelector('#add-row').onclick=()=>{document.querySelector('#measure-rows').insertAdjacentHTML('beforeend',row);bindRows();};
 const bindRows=()=>document.querySelectorAll('[data-remove]').forEach(b=>b.onclick=()=>{const rows=document.querySelectorAll('[data-row]');if(rows.length>1)b.closest('[data-row]').remove();else notify('至少保留一项措施',true);});
 bindRows();
 submit(document.querySelector('#rect-form'),async f=>{
  const measures=[...document.querySelectorAll('[data-row]')].map(r=>({title:r.querySelector('[name=m-title]').value.trim(),assignee:r.querySelector('[name=m-assignee]').value.trim(),detail:r.querySelector('[name=m-detail]').value.trim()}));
  const o=await rectifications.create({title:f.get('title'),job_id:Number(f.get('job_id')),measures});
  notify('整改单已建立并分派');location.hash='#/rectifications/'+o.id;
 });
}
