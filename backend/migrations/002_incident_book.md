# 002 事故簿

SQLAlchemy启动创建以下新表，不影响001既有表：

- `incident_books`：事故簿，(period, policy_version)唯一；version为乐观锁基准，next_number为事故编号序列，last_report_id/last_report_created记录簿基准报告。
- `incident_clusters`：簇成员按版本区间生效，until_version为空即在簿；历史行不删除，供沿事故号查历次成员。索引(book_id, until_version)供在簿查询，number索引供编号追溯。
- `incident_lineage`：拆合来路事件（carry/merge/split/retire/fresh），与编号、成员同事务写入。
- `incident_applies`：(book_id, report_id)唯一幂等记录，重试不新增编号。

同时`sla_runs.snapshot`新增`source_keys`（与sources对齐的底稿编号数组）；缺该字段的旧报告仅供原用途，不能更新事故簿。已有数据库升级需先备份，由启动时create_all补表。
