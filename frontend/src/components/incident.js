import {esc} from '../utils/format.js';import {table} from './common/table.js';
export const KIND={carry:'传承',merge:'合并',split:'拆分',retire:'注销',fresh:'新编'};
export const eventsTable=events=>table(events.map(e=>({版本:'v'+e.version,类型:KIND[e.kind]||e.kind,从编号:e.from_number||'—',到编号:e.to_number||'—',说明:e.detail||''})));
export const historyHtml=h=>!h?'':`<h3>事故号 ${esc(h.number)} 历次成员</h3>`+table(h.states.map(s=>({生效版本:'v'+s.since_version,失效版本:s.until_version?'v'+s.until_version:'在簿',小组:s.group_key,成员数:s.member_count,成员底稿编号:(s.members||[]).join('、')})))+eventsTable(h.events);
