"""整改闭环：派单、领取填写包、离线回传三向合并、争议裁定与验收固定。"""
import time
from fastapi import HTTPException
from sqlalchemy import select, func
from src.models import Job, RectificationOrder, RectificationMeasure, RectificationPackage, RectificationDispute, RectificationEvent
from src.utils.serialization import checksum

EDITABLE = ('done', 'note', 'evidence')  # 离线填写包可修改的字段
FIELD_LABELS = {'done': '完成标记', 'note': '整改说明', 'evidence': '证据清单'}


def log(db, order_id, action, actor, detail=None, package_id=None, measure_id=None):
    db.add(RectificationEvent(order_id=order_id, package_id=package_id, measure_id=measure_id,
                              action=action, detail=detail or {}, actor=actor, at=time.time()))


def norm_evidence(value):
    if value is None:
        return []
    if not isinstance(value, list):
        raise HTTPException(422, '证据清单须为字符串数组')
    out = []
    for item in value:
        s = str(item).strip()
        if s and s not in out:
            out.append(s[:200])
    if len(out) > 20:
        raise HTTPException(422, '证据清单最多 20 条')
    return out


def measure_state(m):
    return {'done': m.status == 'done', 'note': m.note, 'evidence': list(m.evidence or [])}


def get_order(db, order_id, lock=False):
    order = db.get(RectificationOrder, order_id, with_for_update=lock)
    if not order:
        raise HTTPException(404, '整改单不存在')
    return order


def require_open(order):
    if order.status != 'open':
        raise HTTPException(409, '整改单已验收固定，措施与证据不可再变更')


def create_order(db, data, user):
    job = db.get(Job, data.job_id)
    if not job:
        raise HTTPException(404, '分析任务不存在')
    if not (job.approved and job.status == 'completed'):
        raise HTTPException(409, '仅获批的调查结论可以建立整改单')
    order = RectificationOrder(job_id=job.id, title=data.title, status='open', round=1,
                               snapshot={}, created_by=user.email, created_at=time.time())
    db.add(order)
    db.flush()
    for item in data.measures:
        m = RectificationMeasure(order_id=order.id, title=item.title, detail=item.detail,
                                 assignee=item.assignee, status='open', note='', evidence=[],
                                 version=1, updated_at=time.time())
        db.add(m)
        db.flush()
        log(db, order.id, 'measure.added', user.email, {'title': m.title, 'assignee': m.assignee}, measure_id=m.id)
    log(db, order.id, 'order.created', user.email,
        {'job_id': job.id, 'title': order.title, 'measures': len(data.measures)})
    return order


def add_measure(db, order, data, actor):
    m = RectificationMeasure(order_id=order.id, title=data.title, detail=data.detail,
                             assignee=data.assignee, status='open', note='', evidence=[],
                             version=1, updated_at=time.time())
    db.add(m)
    db.flush()
    log(db, order.id, 'measure.added', actor, {'title': m.title, 'assignee': m.assignee, 'round': order.round}, measure_id=m.id)
    return m


def _void_packages(db, order, assignee, reason, actor, measure_id=None):
    """作废指定责任人仍处于待回传状态的填写包（可限定含某措施的包）。"""
    voided = []
    pkgs = db.scalars(select(RectificationPackage).where(
        RectificationPackage.order_id == order.id,
        RectificationPackage.status == 'claimed',
        RectificationPackage.assignee == assignee))
    for p in pkgs:
        ids = [m['id'] for m in (p.base_snapshot or {}).get('measures', [])]
        if measure_id is None or measure_id in ids:
            p.status = 'void'
            p.void_reason = reason
            voided.append(p.id)
            log(db, order.id, 'package.voided', actor,
                {'package': p.id, 'assignee': assignee, 'reason': reason}, package_id=p.id)
    return voided


def update_measure(db, order, measure, data, actor):
    """在线改动：编辑、重新指派（原责任人未回传包失效）、撤销。"""
    changes = {}
    for field in ('title', 'detail', 'note'):
        value = getattr(data, field)
        if value is not None and value != getattr(measure, field):
            changes[field] = {'from': getattr(measure, field), 'to': value}
            setattr(measure, field, value)
    if data.evidence is not None:
        value = norm_evidence(data.evidence)
        if value != (measure.evidence or []):
            changes['evidence'] = {'from': measure.evidence or [], 'to': value}
            measure.evidence = value
    if data.assignee is not None and data.assignee != measure.assignee:
        voided = _void_packages(db, order, measure.assignee, '措施已重新指派给 ' + data.assignee, actor, measure_id=measure.id)
        changes['assignee'] = {'from': measure.assignee, 'to': data.assignee, 'voided_packages': voided}
        measure.assignee = data.assignee
        log(db, order.id, 'measure.reassigned', actor,
            {'measure': measure.title, 'from': changes['assignee']['from'], 'to': data.assignee, 'voided_packages': voided},
            measure_id=measure.id)
    if data.revoke and measure.status != 'revoked':
        changes['status'] = {'from': measure.status, 'to': 'revoked'}
        measure.status = 'revoked'
        log(db, order.id, 'measure.revoked', actor, {'measure': measure.title}, measure_id=measure.id)
    if not changes:
        raise HTTPException(422, '没有需要保存的改动')
    measure.version += 1
    measure.updated_at = time.time()
    if any(k in changes for k in ('title', 'detail', 'note', 'evidence')):
        log(db, order.id, 'measure.edited', actor, {'measure': measure.title, 'fields': changes}, measure_id=measure.id)
    return measure


def claim_package(db, order, assignee, user):
    """领取填写包：同一责任人同一轮次重复领取返回原包（幂等）。"""
    existing = db.scalar(select(RectificationPackage).where(
        RectificationPackage.order_id == order.id,
        RectificationPackage.round == order.round,
        RectificationPackage.assignee == assignee,
        RectificationPackage.status == 'claimed'))
    if existing:
        return existing, False
    measures = list(db.scalars(select(RectificationMeasure).where(
        RectificationMeasure.order_id == order.id,
        RectificationMeasure.assignee == assignee,
        RectificationMeasure.status != 'revoked').order_by(RectificationMeasure.id)))
    if not measures:
        raise HTTPException(422, '该责任人在本轮没有可填写的措施')
    pkg = RectificationPackage(order_id=order.id, round=order.round, assignee=assignee,
                               status='claimed', claimed_by=user.email, claimed_at=time.time())
    db.add(pkg)
    db.flush()
    pkg.base_snapshot = {
        'package_id': pkg.id, 'order_id': order.id, 'round': order.round, 'assignee': assignee,
        'measures': [{'id': m.id, 'title': m.title, 'detail': m.detail,
                      'done': m.status == 'done', 'note': m.note, 'evidence': list(m.evidence or [])}
                     for m in measures]}
    log(db, order.id, 'package.claimed', user.email,
        {'package': pkg.id, 'assignee': assignee, 'round': order.round, 'measures': [m.id for m in measures]},
        package_id=pkg.id)
    return pkg, True


def _validate_payload(pkg, payload):
    if not isinstance(payload, dict):
        raise HTTPException(422, '回传内容须为领取的填写包 JSON')
    if payload.get('package_id') != pkg.id or payload.get('order_id') != pkg.order_id or payload.get('round') != pkg.round:
        raise HTTPException(422, '回传内容与领取包不一致（编号或轮次不符）')
    if payload.get('assignee') != pkg.assignee:
        raise HTTPException(422, '回传内容的责任人与领取包不一致')
    entries = payload.get('measures')
    if not isinstance(entries, list) or not entries:
        raise HTTPException(422, '回传内容缺少措施条目')
    base_ids = [m['id'] for m in pkg.base_snapshot.get('measures', [])]
    seen = set()
    for e in entries:
        if not isinstance(e, dict) or not isinstance(e.get('id'), int):
            raise HTTPException(422, '措施条目格式不正确')
        if e['id'] not in base_ids:
            raise HTTPException(422, '回传包含领取时不存在的措施 #%s' % e.get('id'))
        if e['id'] in seen:
            raise HTTPException(422, '措施 #%s 在回传内容中重复' % e['id'])
        seen.add(e['id'])
    return entries


def _raise_dispute(db, order, pkg, m, kind, field, base_value, online_value, incoming_value, actor):
    d = RectificationDispute(order_id=order.id, measure_id=m.id, package_id=pkg.id, kind=kind, field=field,
                             base_value=base_value, online_value=online_value, incoming_value=incoming_value,
                             measure_version=m.version, status='pending', created_at=time.time())
    db.add(d)
    db.flush()
    log(db, order.id, 'dispute.raised', actor,
        {'dispute': d.id, 'kind': kind, 'measure': m.title, 'field': field,
         'field_label': FIELD_LABELS.get(field, '整项措施')},
        package_id=pkg.id, measure_id=m.id)
    return d


def return_package(db, pkg, payload, actor):
    """回传合并：对照领取时内容与线上现值做三向合并。

    - 互不影响的修改各自保留；同项异改或措施已撤销的修改转待裁定，线上值不被覆盖；
    - 同一包同内容重试直接交还原回执（中断可接回，不重复登记）；同包换内容拒收。
    """
    order = get_order(db, pkg.order_id, lock=True)
    content_hash = checksum(payload)
    if pkg.status == 'returned':
        if pkg.content_hash == content_hash:
            return pkg, pkg.result, False  # 中断重试：交还已登记回执，不重复应用
        raise HTTPException(409, '同一回传包的内容与首次回传不一致，拒收')
    if pkg.status == 'void':
        raise HTTPException(409, '该填写包已失效：' + (pkg.void_reason or '请重新领取'))
    require_open(order)
    if pkg.round != order.round:
        pkg.status = 'void'
        pkg.void_reason = '已进入第 %d 轮整改' % order.round
        log(db, order.id, 'package.voided', actor, {'package': pkg.id, 'reason': pkg.void_reason}, package_id=pkg.id)
        raise HTTPException(409, '该包属于第 %d 轮，不能关闭第 %d 轮的措施' % (pkg.round, order.round))
    entries = _validate_payload(pkg, payload)
    base_map = {m['id']: m for m in pkg.base_snapshot.get('measures', [])}
    decisions = []
    for entry in entries:
        base = base_map[entry['id']]
        m = db.get(RectificationMeasure, entry['id'], with_for_update=True)
        if m is None or m.order_id != order.id:
            raise HTTPException(422, '回传包含不属于本整改单的措施')
        if m.assignee != pkg.assignee:
            pkg.status = 'void'
            pkg.void_reason = '措施已重新指派'
            log(db, order.id, 'package.voided', actor, {'package': pkg.id, 'reason': pkg.void_reason}, package_id=pkg.id)
            raise HTTPException(409, '措施「%s」已重新指派，本包失效' % base['title'])
        incoming = {'done': bool(entry.get('done', False)),
                    'note': str(entry.get('note') or '').strip()[:1000],
                    'evidence': norm_evidence(entry.get('evidence'))}
        if m.status == 'revoked':
            changed = {f: incoming[f] for f in EDITABLE if incoming[f] != base[f]}
            if changed:
                d = _raise_dispute(db, order, pkg, m, 'revoked', '',
                                   {'changes': {f: base[f] for f in changed}},
                                   {'status': 'revoked'},
                                   {'changes': changed}, actor)
                decisions.append({'measure_id': m.id, 'title': m.title, 'field': '', 'decision': 'to_dispute',
                                  'kind': 'revoked', 'dispute_id': d.id,
                                  'reason': '措施已在线撤销，回传修改转待裁定'})
                log(db, order.id, 'merge.to_dispute', actor,
                    {'package': pkg.id, 'measure': m.title, 'kind': 'revoked', 'changes': changed},
                    package_id=pkg.id, measure_id=m.id)
            continue
        state = measure_state(m)
        new_state = dict(state)
        applied = False
        for f in EDITABLE:
            if incoming[f] == base[f]:
                continue  # 离线未改动，保留线上
            if state[f] == base[f]:
                new_state[f] = incoming[f]
                applied = True
                decisions.append({'measure_id': m.id, 'title': m.title, 'field': f, 'decision': 'take_package',
                                  'base': base[f], 'incoming': incoming[f],
                                  'reason': '领取后线上未变更，采用回传内容'})
                log(db, order.id, 'merge.take_package', actor,
                    {'package': pkg.id, 'measure': m.title, 'field': f, 'field_label': FIELD_LABELS[f],
                     'base': base[f], 'value': incoming[f]},
                    package_id=pkg.id, measure_id=m.id)
            elif state[f] == incoming[f]:
                decisions.append({'measure_id': m.id, 'title': m.title, 'field': f, 'decision': 'same_change',
                                  'value': incoming[f], 'reason': '线上与回传改动一致，无需取舍'})
                log(db, order.id, 'merge.same_change', actor,
                    {'package': pkg.id, 'measure': m.title, 'field': f, 'field_label': FIELD_LABELS[f],
                     'value': incoming[f]},
                    package_id=pkg.id, measure_id=m.id)
            else:
                d = _raise_dispute(db, order, pkg, m, 'conflict', f,
                                   {'value': base[f]}, {'value': state[f]}, {'value': incoming[f]}, actor)
                decisions.append({'measure_id': m.id, 'title': m.title, 'field': f, 'decision': 'to_dispute',
                                  'kind': 'conflict', 'dispute_id': d.id,
                                  'base': base[f], 'online': state[f], 'incoming': incoming[f],
                                  'reason': '同项异改，保留线上内容并转待裁定'})
                log(db, order.id, 'merge.to_dispute', actor,
                    {'package': pkg.id, 'measure': m.title, 'kind': 'conflict', 'field': f,
                     'field_label': FIELD_LABELS[f], 'base': base[f], 'online': state[f], 'incoming': incoming[f]},
                    package_id=pkg.id, measure_id=m.id)
        if applied:
            m.note = new_state['note']
            m.evidence = new_state['evidence']
            if new_state['done'] and m.status != 'done':
                m.status = 'done'
                m.completed_at = time.time()
            elif not new_state['done'] and m.status == 'done':
                m.status = 'open'
                m.completed_at = None
            m.version += 1
            m.updated_at = time.time()
    receipt = {'package_id': pkg.id, 'order_id': order.id, 'round': pkg.round, 'returned_at': time.time(),
               'decisions': decisions,
               'summary': {'applied': sum(1 for d in decisions if d['decision'] == 'take_package'),
                           'same': sum(1 for d in decisions if d['decision'] == 'same_change'),
                           'disputes': sum(1 for d in decisions if d['decision'] == 'to_dispute')}}
    pkg.status = 'returned'
    pkg.content_hash = content_hash
    pkg.payload = payload
    pkg.result = receipt
    pkg.returned_at = receipt['returned_at']
    log(db, order.id, 'package.returned', actor,
        {'package': pkg.id, 'assignee': pkg.assignee, 'round': pkg.round, 'summary': receipt['summary']},
        package_id=pkg.id)
    return pkg, receipt, True


def _apply_field(m, field, value):
    if field == 'note':
        m.note = str(value or '')[:1000]
    elif field == 'evidence':
        m.evidence = norm_evidence(value)
    elif field == 'done':
        if value and m.status != 'done':
            m.status = 'done'
            m.completed_at = time.time()
        elif not value and m.status == 'done':
            m.status = 'open'
            m.completed_at = None


def resolve_dispute(db, dispute, data, actor):
    """裁定：与在线改动并发时（版本已前进）拒绝覆盖新值。"""
    order = get_order(db, dispute.order_id, lock=True)
    if dispute.status != 'pending':
        raise HTTPException(409, '该争议已裁定')
    m = db.get(RectificationMeasure, dispute.measure_id, with_for_update=True)
    if m is None:
        raise HTTPException(404, '措施不存在')
    if m.version != data.expected_version:
        raise HTTPException(409, '措施已有更新的在线改动（当前版本 %d），拒绝覆盖新值，请刷新后重新裁定' % m.version)
    if data.resolution == 'take_package':
        if dispute.kind == 'conflict':
            _apply_field(m, dispute.field, dispute.incoming_value.get('value'))
        else:
            incoming = dispute.incoming_value.get('changes', {})
            for f, v in incoming.items():
                _apply_field(m, f, v)
            m.status = 'done' if incoming.get('done') else 'open'
            if m.status == 'done' and not m.completed_at:
                m.completed_at = time.time()
            if m.status == 'open':
                m.completed_at = None
        m.version += 1
        m.updated_at = time.time()
    dispute.status = 'resolved'
    dispute.resolution = data.resolution
    dispute.resolved_by = actor
    dispute.resolved_at = time.time()
    log(db, order.id, 'dispute.resolved', actor,
        {'dispute': dispute.id, 'resolution': data.resolution, 'measure': m.title,
         'field': dispute.field, 'version': m.version},
        measure_id=m.id)
    return dispute


def _void_all_packages(db, order, reason, actor):
    voided = []
    for p in db.scalars(select(RectificationPackage).where(
            RectificationPackage.order_id == order.id, RectificationPackage.status == 'claimed')):
        p.status = 'void'
        p.void_reason = reason
        voided.append(p.id)
        log(db, order.id, 'package.voided', actor, {'package': p.id, 'assignee': p.assignee, 'reason': reason}, package_id=p.id)
    return voided


def _pending_disputes(db, order_id):
    return db.scalar(select(func.count()).select_from(RectificationDispute).where(
        RectificationDispute.order_id == order_id, RectificationDispute.status == 'pending'))


def accept_order(db, order, actor):
    """验收：争议未清不验收；验收后固定全部措施与证据。"""
    require_open(order)
    pending = _pending_disputes(db, order.id)
    if pending:
        raise HTTPException(409, '尚有 %d 项争议未裁定，争议未清不验收' % pending)
    measures = list(db.scalars(select(RectificationMeasure).where(RectificationMeasure.order_id == order.id)))
    if not measures:
        raise HTTPException(409, '整改单没有措施，不能验收')
    incomplete = [m for m in measures if m.status not in ('done', 'revoked')]
    if incomplete:
        raise HTTPException(409, '尚有 %d 项措施未完成，不能验收' % len(incomplete))
    now = time.time()
    order.status = 'accepted'
    order.accepted_at = now
    order.snapshot = {'round': order.round, 'accepted_at': now, 'accepted_by': actor,
                      'measures': [{'id': m.id, 'title': m.title, 'detail': m.detail, 'assignee': m.assignee,
                                    'status': m.status, 'note': m.note, 'evidence': list(m.evidence or []),
                                    'version': m.version} for m in measures]}
    voided = _void_all_packages(db, order, '整改单已验收固定', actor)
    log(db, order.id, 'order.accepted', actor,
        {'round': order.round, 'measures': len(measures), 'voided_packages': voided})
    return order


def send_back(db, order, note, actor):
    """退回整改：开启新一轮，已完成措施重新打开，旧包不能关闭新一轮。"""
    require_open(order)
    pending = _pending_disputes(db, order.id)
    if pending:
        raise HTTPException(409, '尚有 %d 项争议未裁定，请先完成裁定再退回' % pending)
    old_round = order.round
    order.round += 1
    reopened = 0
    for m in db.scalars(select(RectificationMeasure).where(RectificationMeasure.order_id == order.id)):
        if m.status == 'done':
            m.status = 'open'
            m.completed_at = None
            m.version += 1
            m.updated_at = time.time()
            reopened += 1
    voided = _void_all_packages(db, order, '已退回整改，开启第 %d 轮' % order.round, actor)
    log(db, order.id, 'order.returned', actor,
        {'from_round': old_round, 'to_round': order.round, 'reopened': reopened,
         'voided_packages': voided, 'note': note})
    return order


def detail_payload(db, order):
    measures = list(db.scalars(select(RectificationMeasure).where(
        RectificationMeasure.order_id == order.id).order_by(RectificationMeasure.id)))
    packages = list(db.scalars(select(RectificationPackage).where(
        RectificationPackage.order_id == order.id).order_by(RectificationPackage.id.desc())))
    disputes = list(db.scalars(select(RectificationDispute).where(
        RectificationDispute.order_id == order.id).order_by(RectificationDispute.id.desc())))
    events = list(db.scalars(select(RectificationEvent).where(
        RectificationEvent.order_id == order.id).order_by(RectificationEvent.id.desc()).limit(200)))
    return order, measures, packages, disputes, events
