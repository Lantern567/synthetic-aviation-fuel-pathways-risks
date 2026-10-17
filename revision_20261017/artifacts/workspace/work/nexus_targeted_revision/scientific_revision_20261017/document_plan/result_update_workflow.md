# 结果同步接口

输入为当前 `Nexus系统提交文件_重算更新20261017`，保留作者的段落框架、原有致谢与审稿标记方式。三个脚本均不保存 Word；`apply_updates` / `apply_replacements` 只修改调用者传入的内存文档，最终保存和版面检查由主代理统一处理。

## 已完成的真实检查

- 清稿及标记稿的 S5、S8、S9、S18、S19、S21–S29、S32 均已从当前 DOCX 定位，所有目标单元格均只有一个段落。
- 英文与中文两对正文各定位 29 个结果位置，包含结论中共址地点的单复数局部用语。标记稿按当前清稿的 accepted text 匹配，保留实际段落索引。
- 两份 SI 和两份补充图册均已定位结果正文及图注。
- 读取 `validation/ctl_resource_bounds.json` 并核对实际输入 SHA：基线必要上界为 0.7861470341634502，夏季为 0.9165895392434938。前者证明基线原 90% 要求不可行；后者没有该证明含义。两份 CTL 结果均保持部分供给诊断范围。
- 三个计划已绑定全部十八份真实新解及最终账户，八份文档的内存集成通过；四对清稿与标记稿的接受正文和表格一致，上标引文序列保留。
- S5/S9将捕集碳FT/MTJ的7.6 kWh/kg SynAF写为共同的aggregate route-level输入；电力约束、电费和碳账本采用同一输入。S8记录实际共同可再生电价0.35和市电价0.60 CNY/kWh。S8/S9天然气价采用真实目标账本核验的2.53 CNY/m³。

## 最终数据前提

1. `result_tables/output/collection_report.json` 包含 18 个已接受新解、12 个新基线、6 个固定生产资产对比。
2. `figures_cost/adapted_data` 为 18 个新解和原始 GTL 构建的完整契约；其中包括 S21 碳核算、S22/S23 固定设计敏感性与实际非可再生厂址产出占比。
3. `figures_spatial/network_data` 含完整 13 基线的网络指标及 15 行容量匹配。
4. `figures_temporal/inputs`、`temporal_data`、`outputs/temporal_verification.json` 含完整 13 基线及逐周独立的时序指标和 52 个静态剔周计算。
5. 所有源文件、独立验证、最终账本和输出契约的 SHA 保持匹配。

## 准备顺序

从本目录运行：

```powershell
python -X utf8 update_si_results.py inspect
python -X utf8 update_si_results.py prepare
python -X utf8 main_result_replacements.py prepare
python -X utf8 si_result_replacements.py prepare
```

输出：

- `si_result_table_bindings.json`：当前 Word 表结构与精确数据接口。
- `si_result_table_updates.json`：15 张表的具体单元格值及脚注依赖。
- `main_result_replacements.json`：英文及中文正文的局部替换，包含每段当前文本 SHA；非支配集合由真实 13 点独立重建并与图数据核对，三代表配置另行记录。
- `publication_values.json`：13 基线的成本、碳强度、供给、产量、容量、完整运行及空间指标；15 行阈值匹配；6 组 A/B；18 个间隙及最大值；验证计数、CTL 上界及完整源 SHA。供回复、其他附件和图注复用。
- `si_result_replacements.json`：SI 正文及补充图册的具体替换。

`inspect` 入口只刷新定位；`prepare` 每次读取当前 DOCX，不用旧快照覆盖已接受的正文修改。数据未齐时，准备入口会在数值输出前停止。

## 主代理继续负责的内容

- 最终数据与代码可用性段落、SI 第 7.7 节的真实 tag、commit 和完整归档入口。
- S20/S21 按新 GTL-BH 的真实采购量、选定净化容量及资本叶项重绘；其原图包含旧结果依赖。
- 四对 Word 的最终保存、图件插入、清稿与标记稿接受文本一致性，以及渲染后的版面检查。
- 致谢保持用户指定原文。
