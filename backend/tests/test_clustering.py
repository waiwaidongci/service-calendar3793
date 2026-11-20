import unittest,random,time
from src.services.clustering import timeout_orders,cluster_group,plan_update
POLICY={'version':'测试口径','timezone':'Asia/Shanghai','weekdays':[0,1,2,3,4],'windows':[[540,720],[780,1080]],'holidays':['2026-11-16'],'sla_minutes':{'普通':480,'紧急':120}}
def mk(key,dept,opened,closed,pri='紧急',period='2026-11'):
 return key,{'period':period,'department':dept,'opened':opened,'closed':closed,'priority':pri}
def orders_of(*items):return dict(items)
def full_partition(orders):
 """全量重算的分区（用于对照增量结果）。"""
 groups={}
 for k,d in orders.items():groups.setdefault(d['department'],[]).append((k,d))
 out=set()
 for g,items in groups.items():
  for members in cluster_group(sorted(timeout_orders(dict(items),POLICY).items()),POLICY):out.add(frozenset(members))
 return out
def apply_plan(state,new_orders,next_number):
 """模拟一次换版：state为{'orders','clusters'}，clusters为[{row_id,number,group_key,members}]。"""
 inserts,closes,events,nn=plan_update(state['clusters'],state['orders'],new_orders,POLICY,next_number)
 closed=set(closes)
 kept=[c for c in state['clusters'] if c['row_id'] not in closed]
 rid=max([c['row_id'] for c in state['clusters']]+[0])
 for i in inserts:
  rid+=1;kept.append({'row_id':rid,**i})
 return {'orders':new_orders,'clusters':kept},events,nn
def partition(state):return {frozenset(c['members']) for c in state['clusters']}
def numbers(state):return {c['number']:frozenset(c['members']) for c in state['clusters']}
class ClusteringTest(unittest.TestCase):
 def test_overlap_and_transitive(self):
  items=[mk('A','组','2026-11-13T09:00:00+08:00','2026-11-13T10:30:00+08:00'),mk('B','组','2026-11-13T10:00:00+08:00','2026-11-13T11:00:00+08:00'),mk('C','组','2026-11-13T11:30:00+08:00','2026-11-13T12:00:00+08:00'),mk('D','组','2026-11-13T10:30:00+08:00','2026-11-13T11:45:00+08:00')]
  self.assertEqual(cluster_group(items,POLICY),[['A','B','D','C']])  # 间接相连也算同簇，成员按开始时间排序
  self.assertEqual(cluster_group(items[:3],POLICY),[['A','B'],['C']])  # 去掉桥接D则C独立
 def test_boundary_touch_not_overlap(self):
  items=[mk('A','组','2026-11-13T09:00:00+08:00','2026-11-13T10:00:00+08:00'),mk('B','组','2026-11-13T10:00:00+08:00','2026-11-13T11:00:00+08:00')]
  self.assertEqual(cluster_group(items,POLICY),[['A'],['B']])  # 边界分钟相接零重叠
 def test_lunch_break_gap(self):
  items=[mk('A','组','2026-11-13T11:00:00+08:00','2026-11-13T13:00:00+08:00'),mk('B','组','2026-11-13T13:00:00+08:00','2026-11-13T14:00:00+08:00'),mk('C','组','2026-11-13T11:30:00+08:00','2026-11-13T12:30:00+08:00')]
  self.assertEqual(cluster_group(items,POLICY),[['A','C'],['B']])  # 午休分隔，跨午休不重叠
 def test_holiday_excluded(self):
  o=orders_of(mk('H','组','2026-11-16T09:00:00+08:00','2026-11-16T18:00:00+08:00'))
  self.assertEqual(timeout_orders(o,POLICY),{})  # 假日无营业分钟，不构成超时单
 def test_sla_threshold_boundary(self):
  exact=orders_of(mk('E','组','2026-11-13T09:00:00+08:00','2026-11-13T18:00:00+08:00','普通'))
  over=orders_of(mk('O','组','2026-11-13T09:00:00+08:00','2026-11-13T11:01:00+08:00'))
  exact2=orders_of(mk('Q','组','2026-11-13T09:00:00+08:00','2026-11-13T11:00:00+08:00'))
  self.assertEqual(timeout_orders(exact,POLICY),{})  # 恰等于480分钟不算超时
  self.assertEqual(timeout_orders(exact2,POLICY),{})  # 恰等于120分钟不算超时
  self.assertIn('O',timeout_orders(over,POLICY))  # 121分钟超时
 def test_cross_day_overlap(self):
  items=[mk('A','组','2026-11-13T16:00:00+08:00','2026-11-17T10:00:00+08:00'),mk('B','组','2026-11-17T09:00:00+08:00','2026-11-17T12:00:00+08:00')]
  self.assertEqual(cluster_group(items,POLICY),[['A','B']])  # 跨日订单周一时段重叠
 def test_groups_separate(self):
  o=orders_of(mk('A','一组','2026-11-13T09:00:00+08:00','2026-11-13T12:00:00+08:00'),mk('B','二组','2026-11-13T09:00:00+08:00','2026-11-13T12:00:00+08:00'))
  state,_,_=apply_plan({'orders':{},'clusters':[]},o,1)
  self.assertEqual(partition(state),{frozenset({'A'}),frozenset({'B'})})  # 同时段不同组不聚簇
 def test_missing_sla_rejected(self):
  with self.assertRaises(ValueError):timeout_orders(orders_of(mk('X','组','2026-11-13T09:00:00+08:00','2026-11-13T12:00:00+08:00','特急')),POLICY)
class InheritanceTest(unittest.TestCase):
 def base_orders(self):
  return orders_of(
   mk('A','一组','2026-11-13T09:00:00+08:00','2026-11-13T12:00:00+08:00'),
   mk('B','一组','2026-11-13T10:00:00+08:00','2026-11-13T13:30:00+08:00'),
   mk('C','二组','2026-11-13T09:00:00+08:00','2026-11-13T12:00:00+08:00'))
 def test_first_apply_fresh_numbers(self):
  state,events,nn=apply_plan({'orders':{},'clusters':[]},self.base_orders(),1)
  self.assertEqual(numbers(state),{'INC-00001':frozenset({'A','B'}),'INC-00002':frozenset({'C'})})
  self.assertEqual(sorted(e['kind'] for e in events),['fresh','fresh']);self.assertEqual(nn,3)
 def test_noop_correction_reuses_rows(self):
  state,_,nn=apply_plan({'orders':{},'clusters':[]},self.base_orders(),1)
  rows_before={c['row_id'] for c in state['clusters']}
  state2,events,nn2=apply_plan(state,dict(state['orders']),nn)
  self.assertEqual(events,[]);self.assertEqual(nn2,nn)
  self.assertEqual({c['row_id'] for c in state2['clusters']},rows_before)  # 无更正不重写
 def test_number_follows_earliest_survivor(self):
  state,_,nn=apply_plan({'orders':{},'clusters':[]},self.base_orders(),1)
  new=dict(state['orders']);del new['A'];del new['C']  # 一组删最早成员A，二组整簇删C
  state2,events,_=apply_plan(state,new,nn)
  self.assertEqual(numbers(state2),{'INC-00001':frozenset({'B'})})  # 号传给仍在簿最早旧成员B
  kinds={(e['kind'],e['from_number'],e['to_number']) for e in events}
  self.assertIn(('carry','INC-00001','INC-00001'),kinds)
  self.assertIn(('retire','INC-00002',None),kinds)  # 无在簿成员注销
 def test_merge_keeps_smallest(self):
  o=orders_of(mk('A','组','2026-11-13T09:00:00+08:00','2026-11-13T12:00:00+08:00'),mk('B','组','2026-11-13T13:00:00+08:00','2026-11-13T18:00:00+08:00'))
  state,_,nn=apply_plan({'orders':{},'clusters':[]},o,1)
  self.assertEqual(sorted(numbers(state)),['INC-00001','INC-00002'])
  new=dict(state['orders']);new['X']={'period':'2026-11','department':'组','opened':'2026-11-13T11:00:00+08:00','closed':'2026-11-13T14:30:00+08:00','priority':'紧急'}
  state2,events,_=apply_plan(state,new,nn)
  self.assertEqual(numbers(state2),{'INC-00001':frozenset({'A','B','X'})})  # 多号留最小
  self.assertIn(('merge','INC-00002','INC-00001'),{(e['kind'],e['from_number'],e['to_number']) for e in events})
 def test_split_assigns_fresh(self):
  o=orders_of(mk('A','组','2026-11-13T09:00:00+08:00','2026-11-13T12:00:00+08:00'),mk('X','组','2026-11-13T11:00:00+08:00','2026-11-13T14:30:00+08:00'),mk('B','组','2026-11-13T13:00:00+08:00','2026-11-13T18:00:00+08:00'))
  state,_,nn=apply_plan({'orders':{},'clusters':[]},o,1)
  self.assertEqual(numbers(state),{'INC-00001':frozenset({'A','X','B'})})
  new=dict(state['orders']);del new['X']  # 拆桥
  state2,events,_=apply_plan(state,new,nn)
  self.assertEqual(numbers(state2),{'INC-00001':frozenset({'A'}),'INC-00002':frozenset({'B'})})  # 拆出方另编
  self.assertIn(('split','INC-00001','INC-00002'),{(e['kind'],e['from_number'],e['to_number']) for e in events})
 def test_unaffected_group_untouched(self):
  state,_,nn=apply_plan({'orders':{},'clusters':[]},self.base_orders(),1)
  row_c=[c['row_id'] for c in state['clusters'] if c['group_key']=='二组'][0]
  new=dict(state['orders']);new['A']={**new['A'],'opened':'2026-11-13T10:30:00+08:00'}  # 仅动一组：A缩为90分钟退出超时
  state2,events,_=apply_plan(state,new,nn)
  kept={c['row_id'] for c in state2['clusters']}
  self.assertIn(row_c,kept)  # 未波及组原行保留
  self.assertEqual(numbers(state2),{'INC-00001':frozenset({'B'}),'INC-00002':frozenset({'C'})})
  self.assertFalse(any(e['kind']!='carry' for e in events))
 def test_department_move_reclusters_both(self):
  state,_,nn=apply_plan({'orders':{},'clusters':[]},self.base_orders(),1)
  new=dict(state['orders']);new['B']={**new['B'],'department':'二组'}  # B从一组挪到二组，与C重叠
  state2,events,_=apply_plan(state,new,nn)
  self.assertEqual(partition(state2),{frozenset({'A'}),frozenset({'B','C'})})
  self.assertEqual(partition(state2),full_partition(new))  # 与全量重算一致
 def test_lone_member_move_closes_old_row(self):
  o=orders_of(mk('A','一组','2026-11-13T09:00:00+08:00','2026-11-13T12:00:00+08:00'),mk('B','二组','2026-11-13T13:00:00+08:00','2026-11-13T18:00:00+08:00'))
  state,_,nn=apply_plan({'orders':{},'clusters':[]},o,1)
  row_a=[c for c in state['clusters'] if c['group_key']=='一组'][0]
  new=dict(state['orders']);new['A']={**new['A'],'department':'三组'}  # A单独挪组，成员集不变
  state2,events,_=apply_plan(state,new,nn)
  moved=[c for c in state2['clusters'] if 'A' in c['members']][0]
  self.assertEqual(moved['group_key'],'三组');self.assertEqual(moved['number'],row_a['number'])  # 号随人跨组
  self.assertNotEqual(moved['row_id'],row_a['row_id'])  # 组变不得复用旧行
  self.assertEqual(partition(state2),full_partition(new))
class IncrementalTest(unittest.TestCase):
 def random_orders(self,rng,n,groups):
  out={}
  for i in range(n):
   day=2+rng.randrange(27);start=rng.randrange(540,1020);dur=rng.randrange(30,360)
   opened=f'2026-11-{day:02}T{start//60:02}:{start%60:02}:00+08:00';end=start+dur
   closed=f'2026-11-{day:02}T{end//60:02}:{end%60:02}:00+08:00'
   out[f'k{i}']={'period':'2026-11','department':f'组{rng.randrange(groups)}','opened':opened,'closed':closed,'priority':rng.choice(['普通','紧急'])}
  return out
 def test_incremental_equals_full(self):
  rng=random.Random(7);orders=self.random_orders(rng,300,6)
  state,_,nn=apply_plan({'orders':{},'clusters':[]},orders,1)
  self.assertEqual(partition(state),full_partition(orders))
  for _ in range(8):
   new=dict(state['orders'])
   for k in rng.sample(list(new),10):  # 随机更正：改时间/挪组/删除/新增
    action=rng.randrange(4)
    if action==0:del new[k]
    elif action==1:new[k]={**new[k],'department':f'组{rng.randrange(6)}'}
    elif action==2:new[k]={**new[k],'opened':new[k]['opened'].replace('T09','T10')}
    else:new[f'new{rng.randrange(10**6)}']={'period':'2026-11','department':f'组{rng.randrange(6)}','opened':'2026-11-13T09:00:00+08:00','closed':'2026-11-13T12:00:00+08:00','priority':'紧急'}
   state,_,nn=apply_plan(state,new,nn)
   self.assertEqual(partition(state),full_partition(new))  # 增量结果与全量重算一致
   self.assertEqual(len({c['number'] for c in state['clusters']}),len(state['clusters']))  # 编号不重复
 def test_scale_100k(self):
  rng=random.Random(42);orders=self.random_orders(rng,100000,50)
  t0=time.time();state,_,nn=apply_plan({'orders':{},'clusters':[]},orders,1);full=time.time()-t0
  self.assertEqual(partition(state),full_partition(orders))
  new=dict(state['orders'])
  for k in ['k1','k2','k3']:new[k]={**new[k],'department':'组0'}  # 小更正仅波及少数组
  t0=time.time();state2,events,_=apply_plan(state,new,nn);inc=time.time()-t0
  self.assertEqual(partition(state2),full_partition(new))
  print(f'\n十万单全量聚簇 {full:.2f}s，更正增量换版 {inc:.2f}s')
  self.assertLess(full,60);self.assertLess(inc,10)  # 宽限断言，主要验证不逐对比较的复杂度
if __name__=='__main__':unittest.main()
