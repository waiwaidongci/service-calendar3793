import time
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func,or_
from src.models.run import Run
from src.models.incident import IncidentBook,IncidentCluster,IncidentLineage,IncidentApply
from src.services.clustering import plan_update
from src.services.validation import validate_source,validate_policy
from src.services.audit import log
def _get_or_create_book(db,period,policy_version):
 book=db.query(IncidentBook).filter_by(period=period,policy_version=policy_version).first()
 if book:return book
 db.add(IncidentBook(period=period,policy_version=policy_version,version=0,next_number=1,last_report_created=0,updated=time.time()))
 try:db.commit()
 except IntegrityError:db.rollback()  # 并发建簿：唯一约束兜底，重查即可
 return db.query(IncidentBook).filter_by(period=period,policy_version=policy_version).first()
def apply_report(db,user,report_id,base_version):
 """用同期间、同口径的已复核报告换版更新事故簿。基准已变或报告更旧则拒绝；
 编号、成员、拆合来路在同一事务原子切换；同一报告重试为幂等空操作。"""
 report=db.get(Run,report_id)
 if not report:raise HTTPException(404,'报告不存在')
 if not report.approved:raise HTTPException(409,'仅已复核报告可更新事故簿')
 snap=report.snapshot or {};keys=snap.get('source_keys');sources=snap.get('sources') or []
 if not keys or len(keys)!=len(sources):raise HTTPException(422,'该报告快照缺底稿编号，仅供原用途，不能更新事故簿')
 if len(set(keys))!=len(keys):raise HTTPException(422,'报告快照底稿编号重复')
 policy=snap['policy'];validate_policy(policy)
 new_orders={}
 for k,d in zip(keys,sources):validate_source(d);new_orders[k]=d
 period=snap['period'];pv=policy['version']
 book=_get_or_create_book(db,period,pv)
 book=db.query(IncidentBook).filter_by(id=book.id).with_for_update().first()  # 行锁串行化并发换版
 if book.last_report_id==report.id:return detail(db,book,note='同一报告已应用，重试不新增编号')
 if (report.created,report.id)<(book.last_report_created or 0,book.last_report_id or 0):raise HTTPException(409,'报告较簿中基准更旧，已拒绝')
 if base_version!=book.version:raise HTTPException(409,'事故簿基准已变，请刷新后重试')
 old_orders={}
 if book.last_report_id:
  prev=db.get(Run,book.last_report_id)
  if prev and prev.snapshot.get('source_keys'):old_orders=dict(zip(prev.snapshot['source_keys'],prev.snapshot['sources']))
 old_clusters=[{'row_id':c.id,'number':c.number,'group_key':c.group_key,'members':list(c.members)} for c in db.query(IncidentCluster).filter_by(book_id=book.id,until_version=None).all()]
 inserts,closes,events,next_number=plan_update(old_clusters,old_orders,new_orders,policy,book.next_number)
 new_version=book.version+1
 if closes:
  for c in db.query(IncidentCluster).filter(IncidentCluster.id.in_(closes)).all():c.until_version=new_version
 for i in inserts:db.add(IncidentCluster(book_id=book.id,since_version=new_version,until_version=None,**i))
 for e in events:db.add(IncidentLineage(book_id=book.id,version=new_version,**e))
 book.version=new_version;book.next_number=next_number;book.last_report_id=report.id;book.last_report_created=report.created;book.updated=time.time()
 db.add(IncidentApply(book_id=book.id,report_id=report.id,version=new_version,at=time.time()))
 log(db,user.email,'incident.apply',f'{period}/{pv} v{new_version} 报告#{report.id}')
 bid=book.id
 try:db.commit()
 except IntegrityError:  # 幂等记录唯一约束兜底：并发重试返回现有状态
  db.rollback();return detail(db,db.get(IncidentBook,bid),note='并发重试，已返回簿现有状态')
 return detail(db,book)
def list_books(db):
 books=db.query(IncidentBook).order_by(IncidentBook.id).all()
 counts=dict(db.query(IncidentCluster.book_id,func.count()).filter(IncidentCluster.until_version==None).group_by(IncidentCluster.book_id).all())
 return [{'id':b.id,'period':b.period,'policy_version':b.policy_version,'version':b.version,'last_report_id':b.last_report_id,'updated':b.updated,'cluster_count':counts.get(b.id,0)} for b in books]
def detail(db,book,note=None):
 clusters=db.query(IncidentCluster).filter_by(book_id=book.id,until_version=None).order_by(IncidentCluster.number).all()
 events=db.query(IncidentLineage).filter_by(book_id=book.id).order_by(IncidentLineage.version.desc(),IncidentLineage.id.desc()).limit(200).all()
 return {'id':book.id,'period':book.period,'policy_version':book.policy_version,'version':book.version,'last_report_id':book.last_report_id,'updated':book.updated,'note':note,
 'clusters':[{'number':c.number,'group_key':c.group_key,'member_count':c.member_count,'first_opened':c.first_opened,'last_closed':c.last_closed,'members':c.members,'since_version':c.since_version} for c in clusters],
 'events':[{'version':e.version,'kind':e.kind,'from_number':e.from_number,'to_number':e.to_number,'detail':e.detail} for e in events]}
def number_history(db,book_id,number):
 """沿事故号查历次成员：该号各版本区间的成员构成与相关拆合来路。"""
 states=db.query(IncidentCluster).filter_by(book_id=book_id,number=number).order_by(IncidentCluster.since_version).all()
 events=db.query(IncidentLineage).filter_by(book_id=book_id).filter(or_(IncidentLineage.from_number==number,IncidentLineage.to_number==number)).order_by(IncidentLineage.version,IncidentLineage.id).all()
 if not states and not events:raise HTTPException(404,'事故编号不在该簿')
 return {'number':number,
 'states':[{'since_version':s.since_version,'until_version':s.until_version,'group_key':s.group_key,'member_count':s.member_count,'members':s.members,'first_opened':s.first_opened,'last_closed':s.last_closed} for s in states],
 'events':[{'version':e.version,'kind':e.kind,'from_number':e.from_number,'to_number':e.to_number,'detail':e.detail} for e in events]}
