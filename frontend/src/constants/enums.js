export const Role={admin:'业务负责人',analyst:'分析员',viewer:'观察员'};
export const JobStatus={queued:'排队中',running:'计算中',completed:'已完成',failed:'执行失败'};
export const RectStatus={open:'整改中',accepted:'已验收'};
export const MeasureStatus={open:'待整改',done:'已完成',revoked:'已撤销'};
export const PackageStatus={claimed:'待回传',returned:'已回传',void:'已失效'};
export const DisputeStatus={pending:'待裁定',resolved:'已裁定'};
export const DisputeKind={conflict:'同项异改',revoked:'已撤销措施'};
export const Resolution={keep_online:'保留线上',take_package:'采用回传'};
export const FieldLabel={done:'完成标记',note:'整改说明',evidence:'证据清单'};
export const RectEvent={
 'order.created':'建立整改单','measure.added':'新增措施','measure.edited':'在线修改措施','measure.reassigned':'重新指派','measure.revoked':'撤销措施',
 'package.claimed':'领取填写包','package.returned':'回传合并','package.voided':'填写包失效',
 'merge.take_package':'取舍 · 采用回传','merge.same_change':'取舍 · 双方一致','merge.to_dispute':'取舍 · 转待裁定',
 'dispute.raised':'产生争议','dispute.resolved':'裁定结案','order.accepted':'验收固定','order.returned':'退回整改'};
