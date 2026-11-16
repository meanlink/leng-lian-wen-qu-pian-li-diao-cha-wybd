import time, json
from sqlalchemy import select, func
from src.config.database import Session
from migrations.initial import migrate
from src.models import User, Dataset, Job, Report, Delivery, Audit, RectificationOrder, RectificationMeasure, RectificationEvent
from src.services.business import metadata, seed_records, analyze
from src.services.reports import deliver
from src.utils.security import hash_password
from src.utils.serialization import checksum
def seed():
    migrate()
    with Session() as db:
        for role,name in [('admin','林知 · 业务负责人'),('analyst','陈舟 · 分析员'),('viewer','周禾 · 观察员')]:
            email=role+'@demo.local'
            if not db.scalar(select(User).where(User.email==email)):
                db.add(User(email=email,name=name,role=role,password=hash_password('Demo123!')))
        db.flush()
        m=metadata()
        d=db.scalar(select(Dataset).where(Dataset.name==m['dataset_name']))
        if not d:
            rows=seed_records()
            d=Dataset(name=m['dataset_name'],source=m['short']+'-202611.csv',records=rows,checksum=checksum(rows),created_at=time.time())
            db.add(d); db.flush()
        if not db.scalar(select(Job).where(Job.name=='基线复核 · '+m['name'])):
            params={p['key']:p['default'] for p in m.get('parameters',[])}
            result=analyze(d.records,params)
            json.dumps(result,ensure_ascii=False,allow_nan=False)
            admin=db.scalar(select(User).where(User.role=='admin'))
            j=Job(name='基线复核 · '+m['name'],dataset_id=d.id,params=params,status='completed',result=result,created_by=admin.id,created_at=time.time()-3600,finished_at=time.time()-3595,approved=True)
            db.add(j);db.flush()
            r=Report(name='每日业务复核简报',job_id=j.id,destination='业务复核组 · 本地收件箱',interval_seconds=86400,next_run=time.time()+86400,enabled=True)
            db.add(r);db.flush();deliver(db,r)
            db.add(Audit(actor='seed',action='demo.baseline',detail={'dataset':d.id},at=time.time()))
        baseline=db.scalar(select(Job).where(Job.name=='基线复核 · '+m['name']))
        if baseline and not db.scalar(select(func.count()).select_from(RectificationOrder)):
            order=RectificationOrder(job_id=baseline.id,title='B 线保温包装复核整改',status='open',round=1,snapshot={},created_by='seed',created_at=time.time())
            db.add(order);db.flush()
            items=[('更换 B 线 3 号冷藏车门封条','基线复核显示 56–72 分钟段温度抬升约 1.8°C，怀疑门封条老化。','陈舟'),
                   ('B 线保温箱冰排补足至 6 块','超温时段集中在午后班次，按装载规范补足冰排并拍照留证。','陈舟'),
                   ('复核装卸月台停留时长上限','与调度确认月台停留是否超过 15 分钟上限并记录。','林知')]
            for title,detail,assignee in items:
                mm=RectificationMeasure(order_id=order.id,title=title,detail=detail,assignee=assignee,status='open',note='',evidence=[],version=1,updated_at=time.time())
                db.add(mm);db.flush()
                db.add(RectificationEvent(order_id=order.id,package_id=None,measure_id=mm.id,action='measure.added',detail={'title':title,'assignee':assignee},actor='seed',at=time.time()))
            db.add(RectificationEvent(order_id=order.id,package_id=None,measure_id=None,action='order.created',detail={'job_id':baseline.id,'title':order.title,'measures':len(items)},actor='seed',at=time.time()))
        db.commit()
        counts={model.__tablename__:db.scalar(select(func.count()).select_from(model)) for model in [User,Dataset,Job,Report,Delivery,Audit,RectificationOrder]}
        print(json.dumps(counts,ensure_ascii=False))
        return counts
if __name__=='__main__':seed()
