import {request} from './client.js';
export const loadAll=async()=>Object.fromEntries(await Promise.all(['sources','periods','policies','runs','schedules','deliveries','audits','incident-books'].map(async k=>[k,await request('/'+k)])));
export const saveSource=(data,id)=>request('/sources'+(id?'/'+id:''),id?'PUT':'POST',{data});
export const savePolicy=data=>request('/policies','POST',{data});
export const submitRun=data=>request('/runs','POST',data);
export const approveRun=(id,note)=>request('/runs/'+id+'/approve','POST',{note});
export const applyBook=(report_id,base_version)=>request('/incident-books/apply','POST',{report_id,base_version});
export const fetchBook=id=>request('/incident-books/'+id);
export const fetchNumberHistory=(id,number)=>request('/incident-books/'+id+'/numbers/'+encodeURIComponent(number));
