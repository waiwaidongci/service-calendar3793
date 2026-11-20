from datetime import datetime
from src.services.biztime import business_minutes,business_slots
CLUSTER_FIELDS=('department','opened','closed','priority')  # 影响聚簇的底稿字段；期间标签变更不触发重算
def _ts(s):return datetime.fromisoformat(s).timestamp()
def timeout_orders(orders,policy):
 """超时单：营业分钟 > 该优先级SLA阈值（恰等于阈值不算超时）。"""
 sla=policy['sla_minutes'];out={}
 for key,d in orders.items():
  if d['priority'] not in sla:raise ValueError('优先级无SLA口径：'+d['priority'])
  if business_minutes(d['opened'],d['closed'],policy)>sla[d['priority']]:out[key]=d
 return out
def cluster_group(items,policy):
 """同组超时单按营业时段重叠聚簇，间接相连（传递闭包）算同簇。
 按(营业日,时窗)裁剪区间后扫描线+并查集，O(n log n)，不逐对比较。
 items: [(key,data)]；返回成员按(开始,编号)排序的簇列表，簇间按(最早开始,首成员)排序。"""
 parent={k:k for k,_ in items}
 def find(x):
  while parent[x]!=x:parent[x]=parent[parent[x]];x=parent[x]
  return x
 def union(a,b):
  a,b=find(a),find(b)
  if a!=b:parent[max(a,b)]=min(a,b)
 slots={}
 for key,d in items:
  for day,idx,lo,hi in business_slots(d['opened'],d['closed'],policy):slots.setdefault((day,idx),[]).append((lo,hi,key))
 for spans in slots.values():
  spans.sort();cur_hi=None;cur_key=None
  for lo,hi,key in spans:
   if cur_hi is None or lo>=cur_hi:cur_hi,cur_key=hi,key  # 边界相接(lo==cur_hi)零重叠，不算
   else:
    union(key,cur_key)
    if hi>cur_hi:cur_hi,cur_key=hi,key
 ts={k:_ts(d['opened']) for k,d in items}
 groups={}
 for k,_ in items:groups.setdefault(find(k),[]).append(k)
 clusters=[sorted(v,key=lambda k:(ts[k],k)) for v in groups.values()]
 clusters.sort(key=lambda ms:(ts[ms[0]],ms[0]))
 return clusters
def plan_update(old_clusters,old_orders,new_orders,policy,next_number):
 """增量换版纯函数：仅受更正波及的组重聚簇；旧簇号传给仍在簿且仍成簇的最早旧成员，
 新簇收到多个号留最小号，没领到号的另编新号；成员与号均未变的簇复用原行。
 old_clusters: [{'row_id','number','group_key','members'}]；old/new_orders: {底稿编号: 数据}。
 返回 (inserts, closes, events, next_number)：待插入簇、待关闭旧行row_id、拆合来路事件、新序列值。"""
 changed=[k for k in set(old_orders)|set(new_orders) if k not in old_orders or k not in new_orders or any(old_orders[k][f]!=new_orders[k][f] for f in CLUSTER_FIELDS)]
 affected=set()
 for k in changed:
  if k in old_orders:affected.add(old_orders[k]['department'])
  if k in new_orders:affected.add(new_orders[k]['department'])
 dissolved=[c for c in old_clusters if c['group_key'] in affected]
 by_group={}
 for k,d in new_orders.items():
  if d['department'] in affected:by_group.setdefault(d['department'],[]).append((k,d))
 ts={k:_ts(d['opened']) for k,d in new_orders.items()}
 new_clusters=[]
 for g in sorted(by_group):
  over=timeout_orders(dict(by_group[g]),policy)
  for members in cluster_group(sorted(over.items()),policy):new_clusters.append({'group_key':g,'members':members})
 home={}
 for i,c in enumerate(new_clusters):
  for k in c['members']:home[k]=i
 claims={}
 for c in dissolved:
  cand=[k for k in c['members'] if k in home]
  if cand:claims.setdefault(home[min(cand,key=lambda k:(ts[k],k))],[]).append(c['number'])
 numbers={i:min(nums) for i,nums in claims.items()}  # 新簇收到多个号就留最小号
 def first(c):return c['members'][0]
 fresh=sorted((i for i in range(len(new_clusters)) if i not in numbers),key=lambda i:(ts[first(new_clusters[i])],new_clusters[i]['group_key'],first(new_clusters[i])))
 for i in fresh:numbers[i]='INC-%05d'%next_number;next_number+=1  # 没领到号的另编
 old_by_number={c['number']:c for c in dissolved}
 reused_rows=set();reused_new=set()
 for i,c in enumerate(new_clusters):
  old=old_by_number.get(numbers[i])
  if old and old['group_key']==c['group_key'] and sorted(old['members'])==sorted(c['members']):reused_rows.add(old['row_id']);reused_new.add(i)
 closes=[c['row_id'] for c in dissolved if c['row_id'] not in reused_rows]
 events=[]
 for c in dissolved:
  cand=[k for k in c['members'] if k in home]
  if not cand:
   events.append({'kind':'retire','from_number':c['number'],'to_number':None,'detail':'无仍在簿成员，编号注销'})
   continue
  target=home[min(cand,key=lambda k:(ts[k],k))]
  if target in reused_new:pass  # 整簇原样传承，不记事件
  elif numbers[target]==c['number']:events.append({'kind':'carry','from_number':c['number'],'to_number':c['number'],'detail':'号随最早在簿成员传承'})
  else:events.append({'kind':'merge','from_number':c['number'],'to_number':numbers[target],'detail':'并入小号，大号注销'})
  for o in sorted({home[k] for k in cand}-{target}):events.append({'kind':'split','from_number':c['number'],'to_number':numbers[o],'detail':'旧簇成员拆出至新簇'})
 for i in fresh:events.append({'kind':'fresh','from_number':None,'to_number':numbers[i],'detail':'新簇另编号'})
 inserts=[]
 for i,c in enumerate(new_clusters):
  if i in reused_new:continue
  ms=c['members'];last=max(ms,key=lambda k:_ts(new_orders[k]['closed']))
  inserts.append({'number':numbers[i],'group_key':c['group_key'],'members':ms,'member_count':len(ms),'first_opened':new_orders[ms[0]]['opened'],'last_closed':new_orders[last]['closed']})
 return inserts,closes,events,next_number
