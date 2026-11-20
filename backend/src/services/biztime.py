from datetime import datetime,timedelta,time
from zoneinfo import ZoneInfo
def business_minutes(opened,closed,policy):
 zone=ZoneInfo(policy['timezone']);a=datetime.fromisoformat(opened).astimezone(zone);b=datetime.fromisoformat(closed).astimezone(zone)
 if b<a:raise ValueError('结束时间早于开始时间')
 day=a.date();total=0
 while day<=b.date():
  if day.weekday() in policy['weekdays'] and day.isoformat() not in policy.get('holidays',[]):
   midnight=datetime.combine(day,time(),zone)
   for start,end in policy['windows']:
    lo=max(a,midnight+timedelta(minutes=start));hi=min(b,midnight+timedelta(minutes=end));total+=max(0,(hi-lo).total_seconds()/60)
  day+=timedelta(days=1)
 return total
def business_slots(opened,closed,policy):
 """订单落在营业时段内的非空裁剪区间：[(日期, 时窗序号, lo, hi)]，lo<hi。用于重叠聚簇扫描。"""
 zone=ZoneInfo(policy['timezone']);a=datetime.fromisoformat(opened).astimezone(zone);b=datetime.fromisoformat(closed).astimezone(zone)
 if b<a:raise ValueError('结束时间早于开始时间')
 slots=[];day=a.date()
 while day<=b.date():
  if day.weekday() in policy['weekdays'] and day.isoformat() not in policy.get('holidays',[]):
   midnight=datetime.combine(day,time(),zone)
   for idx,(start,end) in enumerate(policy['windows']):
    lo=max(a,midnight+timedelta(minutes=start));hi=min(b,midnight+timedelta(minutes=end))
    if lo<hi:slots.append((day.isoformat(),idx,lo,hi))
  day+=timedelta(days=1)
 return slots
