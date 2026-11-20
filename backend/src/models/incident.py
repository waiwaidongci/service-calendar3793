from sqlalchemy import Column,Integer,String,JSON,Float,UniqueConstraint,Index
from src.config.database import Base
class IncidentBook(Base):
 """事故簿：按(期间,口径版本)一簿；version为乐观锁基准，next_number为事故编号序列。"""
 __tablename__='incident_books'
 id=Column(Integer,primary_key=True); period=Column(String(120)); policy_version=Column(String(120))
 version=Column(Integer,default=0); next_number=Column(Integer,default=1)
 last_report_id=Column(Integer); last_report_created=Column(Float,default=0); updated=Column(Float)
 __table_args__=(UniqueConstraint('period','policy_version'),)
class IncidentCluster(Base):
 """簇成员按版本区间生效：until_version为空即在簿；历史行保留供沿事故号查历次成员。"""
 __tablename__='incident_clusters'
 id=Column(Integer,primary_key=True); book_id=Column(Integer,index=True); number=Column(String(20),index=True)
 group_key=Column(String(120)); members=Column(JSON); member_count=Column(Integer)
 first_opened=Column(String(40)); last_closed=Column(String(40))
 since_version=Column(Integer); until_version=Column(Integer,nullable=True)
 __table_args__=(Index('ix_cluster_book_current','book_id','until_version'),)
class IncidentLineage(Base):
 """拆合来路：carry传承 / merge并入小号 / split拆出 / retire注销 / fresh另编。"""
 __tablename__='incident_lineage'
 id=Column(Integer,primary_key=True); book_id=Column(Integer,index=True); version=Column(Integer)
 kind=Column(String(10)); from_number=Column(String(20),nullable=True); to_number=Column(String(20),nullable=True); detail=Column(String(250))
class IncidentApply(Base):
 """幂等记录：(簿,报告)唯一，重试不新增编号。"""
 __tablename__='incident_applies'
 id=Column(Integer,primary_key=True); book_id=Column(Integer); report_id=Column(Integer); version=Column(Integer); at=Column(Float)
 __table_args__=(UniqueConstraint('book_id','report_id'),)
