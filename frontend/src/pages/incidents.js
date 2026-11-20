import {heading} from '../components/common/header.js';import {esc,time} from '../utils/format.js';import {eventsTable,historyHtml} from '../components/incident.js';import {store} from '../stores/business.js';
export function incidents(c,d){
 const books=d['incident-books'],b=store.bookDetail;
 let out=heading('INCIDENT BOOK / 05','事故簿','同组超时单营业时段重叠即为一簇，间接相连也算；已复核报告按同期间同口径换版更新，号随最早在簿旧成员传承。');
 out+=books.length?`<div class="run-layout"><aside class="run-list">${books.map(x=>`<button class="select-book" data-id="${x.id}">${esc(x.period)} · ${esc(x.policy_version)} · v${x.version} · ${x.cluster_count}簇</button>`).join('')}</aside><div>${b?bookHtml(b):'<p class="empty">选择一簿查看在簿簇与拆合来路。</p>'}</div></div>`:'<p class="empty">尚无事故簿。复核含底稿编号的报告后，在核算页将其更新入簿。</p>';
 return out}
function bookHtml(b){
 const clusters=b.clusters.map(x=>`<tr><td><button class="num-link" data-num="${esc(x.number)}">${esc(x.number)}</button></td><td>${esc(x.group_key)}</td><td>${x.member_count}</td><td>${esc(x.first_opened)}</td><td>${esc(x.last_closed)}</td><td>${esc((x.members||[]).join('、'))}</td></tr>`).join('');
 return `<h2>${esc(b.period)} · ${esc(b.policy_version)} · 簿版本 v${b.version}</h2><p>最近入簿报告 #${b.last_report_id||'—'} · 更新于 ${b.updated?time(b.updated):'—'}</p>
 <h3>在簿簇（${b.clusters.length}）</h3><div class="table-wrap"><table><thead><tr><th>事故编号</th><th>小组</th><th>成员数</th><th>最早开始</th><th>最晚结束</th><th>成员底稿编号</th></tr></thead><tbody>${clusters||'<tr><td colspan="6">在簿无簇</td></tr>'}</tbody></table></div>
 <h3>拆合来路</h3>${eventsTable(b.events)}
 <form id="number-history" data-book="${b.id}" class="inline-form"><label>沿事故号查历次成员<input name="number" placeholder="INC-00001" required></label><button>查询</button></form><div id="history-result">${historyHtml(store.history)}</div>`}
