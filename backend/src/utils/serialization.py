import hashlib, json
def checksum(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()
def dataset_dict(d):
    return {'id':d.id, 'name':d.name, 'source':d.source, 'rows':len(d.records), 'checksum':d.checksum, 'created_at':d.created_at}
def job_dict(j):
    return {k:getattr(j,k) for k in ['id','name','dataset_id','params','status','result','error','approved','created_at','finished_at']}
def report_dict(r):
    return {k:getattr(r,k) for k in ['id','name','job_id','destination','interval_seconds','next_run','enabled']}
def delivery_dict(d):
    return {k:getattr(d,k) for k in ['id','report_id','created_at','checksum','filename','destination']}
def rect_order_dict(o,counts=None):
    d={k:getattr(o,k) for k in ['id','job_id','title','status','round','created_by','created_at','accepted_at']}
    d['snapshot']=o.snapshot or {}
    if counts is not None:d['counts']=counts
    return d
def rect_measure_dict(m):
    return {k:getattr(m,k) for k in ['id','order_id','title','detail','assignee','status','note','evidence','version','updated_at','completed_at']}
def rect_package_dict(p,content=False):
    d={k:getattr(p,k) for k in ['id','order_id','round','assignee','status','void_reason','claimed_by','claimed_at','returned_at']}
    d['content_hash']=p.content_hash
    d['result']=p.result or None
    if content:d['content']=p.base_snapshot
    return d
def rect_dispute_dict(d):
    return {k:getattr(d,k) for k in ['id','order_id','measure_id','package_id','kind','field','base_value','online_value','incoming_value','measure_version','status','resolution','resolved_by','resolved_at','created_at']}
def rect_event_dict(e):
    return {k:getattr(e,k) for k in ['id','order_id','package_id','measure_id','action','detail','actor','at']}
