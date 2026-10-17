# Figure 3及S30–S35

原模板来自revision_20261007/figures_space_time/source的五份时间分析脚本，副本保存在本目录source。主图保留原Figure 3的画布、面板结构和矢量拼版；分布图、堆积条、散点与气泡矩阵保持原字体及配色。S31/S32复用原补图的尺寸、面板结构及Arial样式。

```powershell
python build_inputs.py --results ../results --accounts-root ../postprocess/accounts --out inputs
python render_temporal.py --inputs inputs --out outputs
python export_aliases.py --out outputs
```

绘图要求12条本轮真实baseline及GTL真实历史记录齐全，accounts须通过并绑定同一summary字节；每份实际产量及能力独立读入，不从旧图或旧均值补数据。--case和--historical-only只供限定范围的真实数据检查，--metrics-only可检查其指标。限定范围检查写入checks，正式全表仅在完整13基准时输出。

归档迁移后，使用`--renewable-input`指定真实`renewable_periods.csv`，`--gtl-source-dir`指定原GTL完整解及同时间逐期CSV所在目录，`--gtl-adapted-dir`指定GTL规范化完整解、碳账本及manifest所在目录。重新执行build会为新位置生成可核验的绝对路径和SHA；图件读取本次生成的inputs/manifest.json。

## 数据与指标

- 时段为224个3h记录。每条产量及能力CSV、规范化记录和accounts均核对真实源hash。
- SynAF利用率为实际期间产量/(3h×装机kg/h能力)；GH氢气按电解能力，BH按本轮选定净化能力。GTL无独立氢气产量时保留不适用值。
- 原始物理利用率首先检查界限，超出数值容差立即报错。所有绘图指标与独立期间算法对照。
- 各代表周内分别统计低负荷事件与可再生功率变化，跨周边界不形成事件或ramp。
- S30的24h居中平滑在每个代表周内部独立计算；分布统计使用原始3h记录。恒定利用率以真实数值处的直线及均值/中位数标记表示。
- Mean-utilization capacity premium = (1/mean utilization−1)×100%；additional worst-week capacity premium = (1/worst-week utilization−1/mean utilization)×100%。两者是容量需求代理，图中文字采用对应名称。
- 可再生波动指标沿用所选活跃H₂来源点的可用发电记录。BH的kg H₂/h供应记录不作为MW发电。无可再生电源的配置按其实际供电范围保存0及来源说明。
- S35的标准化参考总体重新计算全部13条基准。三个固定参考配置为GTL-BH、GTL、CCU-GH-FT；选择不宣称它们形成新的Pareto前沿。

## 输出

| 图件 | 输出文件干名 |
|---|---|
| Figure 3 | Figure_3 |
| S30 | Figure_S30（与h2_saf_2col_3row_by_category逐字节一致） |
| S31 | Figure_S31 |
| S32 | Figure_S32 |
| S33 | Figure_S33（与pareto_temporal_distribution_latest逐字节一致） |
| S34 | Figure_S34（与pareto_penalty_comparison_latest逐字节一致） |
| S35 | Figure_S35（与pareto_penalty_driver_heatmap_latest逐字节一致） |

每图输出PNG及PDF；其余矢量格式按原模板保留。Figure 3使用真实PDF面板边界记录，保留矢量内容。真实出图后逐张检查文字、标注、面板边界及图例，完成图面检查后再进入Word。

正式共享指标为temporal_data/all_pathway_temporal_metrics.csv，保留原模板列，并增加MeanSynAFUtilization、MeanUtilizationCapacityPremiumPct、AdditionalWorstWeekCapacityPremiumPct、CapacityPremiumClass、DemandFulfillmentRatio及SourceKind。原内部列名SAFMean/ChronicPenaltyPct/RobustnessPenaltyPct用于模板兼容，公开标签为SynAF及两项capacity premium。

temporal_verification.json记录实际源hash、脚本hash、独立逐期指标对照、真实图文件hash与来源范围。Figure_3_manifest.json记录各PDF面板的实际裁剪和选定配置的实际供给率。
official_figure_aliases.json记录S30、S33–S35的正式PNG/PDF别名、原图文件名及逐字节SHA一致性。

## 已完成的真实检查

全部13条基准已完成适配和独立指标检查：均值、四周均值、retention、两项capacity premium、低负荷事件及周内ramp一致。Figure 3及S30–S35已使用完整真实期间记录绘制，并逐张检查文字、标注、边界和图例。最终交付绑定以最后冻结账户重新构建的input_manifest及temporal_verification为准。

依赖：numpy、pandas、matplotlib、scipy、adjustText、PyMuPDF、Pillow；当前adjustText版本为1.4.0。
