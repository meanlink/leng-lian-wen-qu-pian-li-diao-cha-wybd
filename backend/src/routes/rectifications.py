from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from src.config.database import get_db
from src.models import RectificationOrder, RectificationMeasure, RectificationPackage, RectificationDispute
from src.schemas.rectification import OrderInput, MeasureInput, MeasurePatch, ClaimInput, ReturnInput, ResolveInput, SendBackInput
from src.middlewares.auth import current_user, can_write, admin_only
from src.services import rectification as svc
from src.services.audit import record
from src.utils.serialization import (rect_order_dict, rect_measure_dict, rect_package_dict,
                                     rect_dispute_dict, rect_event_dict)
router = APIRouter(prefix='/rectifications')


def _counts(db, ids):
    measures, disputes = {}, {}
    if ids:
        for oid, status, n in db.execute(select(RectificationMeasure.order_id, RectificationMeasure.status, func.count())
                                         .where(RectificationMeasure.order_id.in_(ids))
                                         .group_by(RectificationMeasure.order_id, RectificationMeasure.status)):
            measures.setdefault(oid, {})[status] = n
        disputes = dict(db.execute(select(RectificationDispute.order_id, func.count())
                                   .where(RectificationDispute.order_id.in_(ids), RectificationDispute.status == 'pending')
                                   .group_by(RectificationDispute.order_id)).all())
    return measures, disputes


@router.get('')
def listing(db=Depends(get_db), u=Depends(current_user)):
    orders = list(db.scalars(select(RectificationOrder).order_by(RectificationOrder.id.desc()).limit(100)))
    ids = [o.id for o in orders]
    measures, disputes = _counts(db, ids)
    out = []
    for o in orders:
        mc = measures.get(o.id, {})
        counts = {'measures': sum(mc.values()), 'done': mc.get('done', 0), 'revoked': mc.get('revoked', 0),
                  'disputes_pending': disputes.get(o.id, 0)}
        out.append(rect_order_dict(o, counts))
    return out


@router.post('', status_code=201)
def create(data: OrderInput, db=Depends(get_db), u=Depends(can_write)):
    o = svc.create_order(db, data, u)
    record(db, u.email, 'rectification.create', {'id': o.id, 'job_id': o.job_id, 'title': o.title})
    db.commit()
    return rect_order_dict(o)


@router.get('/{oid}')
def get_detail(oid: int, db=Depends(get_db), u=Depends(current_user)):
    order = svc.get_order(db, oid)
    _, measures, packages, disputes, events = svc.detail_payload(db, order)
    return {'order': rect_order_dict(order),
            'measures': [rect_measure_dict(m) for m in measures],
            'packages': [rect_package_dict(p) for p in packages],
            'disputes': [rect_dispute_dict(d) for d in disputes],
            'events': [rect_event_dict(e) for e in events]}


@router.post('/{oid}/measures', status_code=201)
def add_measure(oid: int, data: MeasureInput, db=Depends(get_db), u=Depends(can_write)):
    order = svc.get_order(db, oid, lock=True)
    svc.require_open(order)
    m = svc.add_measure(db, order, data, u.email)
    record(db, u.email, 'rectification.measure.add', {'order': oid, 'id': m.id})
    db.commit()
    return rect_measure_dict(m)


@router.patch('/{oid}/measures/{mid}')
def patch_measure(oid: int, mid: int, data: MeasurePatch, db=Depends(get_db), u=Depends(can_write)):
    order = svc.get_order(db, oid, lock=True)
    svc.require_open(order)
    m = db.get(RectificationMeasure, mid, with_for_update=True)
    if not m or m.order_id != oid:
        raise HTTPException(404, '措施不存在')
    svc.update_measure(db, order, m, data, u.email)
    record(db, u.email, 'rectification.measure.update', {'order': oid, 'id': mid})
    db.commit()
    return rect_measure_dict(m)


@router.post('/{oid}/packages')
def claim(oid: int, data: ClaimInput, db=Depends(get_db), u=Depends(can_write)):
    order = svc.get_order(db, oid, lock=True)
    svc.require_open(order)
    pkg, created = svc.claim_package(db, order, data.assignee, u)
    if created:
        record(db, u.email, 'rectification.package.claim', {'order': oid, 'id': pkg.id, 'assignee': pkg.assignee})
    db.commit()
    return rect_package_dict(pkg, content=True)


@router.get('/{oid}/packages/{pid}')
def get_package(oid: int, pid: int, db=Depends(get_db), u=Depends(current_user)):
    pkg = db.get(RectificationPackage, pid)
    if not pkg or pkg.order_id != oid:
        raise HTTPException(404, '填写包不存在')
    return rect_package_dict(pkg, content=True)


@router.post('/{oid}/packages/{pid}/return')
def return_package(oid: int, pid: int, data: ReturnInput, db=Depends(get_db), u=Depends(can_write)):
    pkg = db.get(RectificationPackage, pid, with_for_update=True)
    if not pkg or pkg.order_id != oid:
        raise HTTPException(404, '填写包不存在')
    pkg, receipt, fresh = svc.return_package(db, pkg, data.payload, u.email)
    record(db, u.email, 'rectification.package.return', {'order': oid, 'id': pid, 'replayed': not fresh})
    db.commit()
    return rect_package_dict(pkg)


@router.post('/{oid}/disputes/{did}/resolve')
def resolve(oid: int, did: int, data: ResolveInput, db=Depends(get_db), u=Depends(admin_only)):
    d = db.get(RectificationDispute, did, with_for_update=True)
    if not d or d.order_id != oid:
        raise HTTPException(404, '争议不存在')
    svc.resolve_dispute(db, d, data, u.email)
    record(db, u.email, 'rectification.dispute.resolve', {'order': oid, 'id': did, 'resolution': data.resolution})
    db.commit()
    return rect_dispute_dict(d)


@router.post('/{oid}/accept')
def accept(oid: int, db=Depends(get_db), u=Depends(admin_only)):
    order = svc.get_order(db, oid, lock=True)
    svc.accept_order(db, order, u.email)
    record(db, u.email, 'rectification.accept', {'id': oid, 'round': order.round})
    db.commit()
    return rect_order_dict(order)


@router.post('/{oid}/send-back')
def send_back(oid: int, data: SendBackInput, db=Depends(get_db), u=Depends(admin_only)):
    order = svc.get_order(db, oid, lock=True)
    svc.send_back(db, order, data.note, u.email)
    record(db, u.email, 'rectification.sendback', {'id': oid, 'round': order.round})
    db.commit()
    return rect_order_dict(order)
