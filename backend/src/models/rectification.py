from sqlalchemy import String, Double, ForeignKey, JSON, Integer
from sqlalchemy.orm import Mapped, mapped_column
from src.config.database import Base
class RectificationOrder(Base):
    __tablename__ = 'rectification_orders'
    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey('jobs.id'))
    title: Mapped[str] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(String(20), default='open')  # open 整改中 / accepted 已验收
    round: Mapped[int] = mapped_column(Integer, default=1)
    snapshot: Mapped[dict] = mapped_column(JSON, default=dict)  # 验收时冻结的全部措施与证据
    created_by: Mapped[str] = mapped_column(String(150))
    created_at: Mapped[float] = mapped_column(Double)
    accepted_at: Mapped[float | None] = mapped_column(Double, nullable=True)
class RectificationMeasure(Base):
    __tablename__ = 'rectification_measures'
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey('rectification_orders.id'))
    title: Mapped[str] = mapped_column(String(160))
    detail: Mapped[str] = mapped_column(String(500), default='')
    assignee: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(20), default='open')  # open 待整改 / done 已完成 / revoked 已撤销
    note: Mapped[str] = mapped_column(String(1000), default='')
    evidence: Mapped[list] = mapped_column(JSON, default=list)
    version: Mapped[int] = mapped_column(Integer, default=1)  # 乐观锁：在线改动与裁定并发校验
    updated_at: Mapped[float] = mapped_column(Double)
    completed_at: Mapped[float | None] = mapped_column(Double, nullable=True)
class RectificationPackage(Base):
    __tablename__ = 'rectification_packages'
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey('rectification_orders.id'))
    round: Mapped[int] = mapped_column(Integer)
    assignee: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(20), default='claimed')  # claimed 待回传 / returned 已回传 / void 已失效
    void_reason: Mapped[str] = mapped_column(String(200), default='')
    base_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)  # 领取时内容，回传合并的对照基线
    content_hash: Mapped[str] = mapped_column(String(64), default='')
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    result: Mapped[dict] = mapped_column(JSON, default=dict)  # 合并回执：逐项取舍与争议
    claimed_by: Mapped[str] = mapped_column(String(150))
    claimed_at: Mapped[float] = mapped_column(Double)
    returned_at: Mapped[float | None] = mapped_column(Double, nullable=True)
class RectificationDispute(Base):
    __tablename__ = 'rectification_disputes'
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey('rectification_orders.id'))
    measure_id: Mapped[int] = mapped_column(ForeignKey('rectification_measures.id'))
    package_id: Mapped[int | None] = mapped_column(ForeignKey('rectification_packages.id'), nullable=True)
    kind: Mapped[str] = mapped_column(String(20))  # conflict 同项异改 / revoked 已撤销措施被回传修改
    field: Mapped[str] = mapped_column(String(20), default='')  # conflict 时为字段名；revoked 时为空（整项）
    base_value: Mapped[dict] = mapped_column(JSON, default=dict)
    online_value: Mapped[dict] = mapped_column(JSON, default=dict)
    incoming_value: Mapped[dict] = mapped_column(JSON, default=dict)
    measure_version: Mapped[int] = mapped_column(Integer)  # 争议产生时的措施版本
    status: Mapped[str] = mapped_column(String(20), default='pending')  # pending 待裁定 / resolved 已裁定
    resolution: Mapped[str] = mapped_column(String(20), default='')  # keep_online 保留线上 / take_package 采用回传
    resolved_by: Mapped[str] = mapped_column(String(150), default='')
    resolved_at: Mapped[float | None] = mapped_column(Double, nullable=True)
    created_at: Mapped[float] = mapped_column(Double)
class RectificationEvent(Base):
    __tablename__ = 'rectification_events'
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey('rectification_orders.id'))
    package_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    measure_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    action: Mapped[str] = mapped_column(String(40))
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    actor: Mapped[str] = mapped_column(String(150))
    at: Mapped[float] = mapped_column(Double)
