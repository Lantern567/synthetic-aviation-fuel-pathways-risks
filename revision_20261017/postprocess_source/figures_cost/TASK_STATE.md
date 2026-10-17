输入版本：20261017 新科学修订目录中的 18 份真实求解与核验结果，加原发布包保留的 GTL 基线。原 20261015 源码、结果和图件只读。

已完成：
- build_inputs.py 严格核验 summary、accounts、物理、运输和库存报告的 SHA，构造 13 条基线路径与 6 条换周记录。
- 学习轨迹沿用当前发布包 learning_assumptions.json；固定设计敏感性从实际制氢、合成用电和 DAC 捕集质量重算。
- render_figures.py 只读导入原图模板，准备 Figure 1、S20–S25、S28–S29、S36–S48；沿用版式、字体和尺寸。
- Figure 1 的横坐标使用供应链碳强度实际值；成本标签统一为 LCO-SynAF。
- 语法检查和所需库导入通过。adjustText 安装在本目录 python_dependencies 中。

执行接口：
1. python build_inputs.py --check-inputs
2. python build_inputs.py
3. python render_figures.py

S20/S21已基于真实新GTL-BH及保留GTL基线通过成本闭合，试绘位于qa/fossil_sensitivity；GTL-BH资本扫描140k–400k对应6.201138910847923–6.3496113851375116 CNY/kg，钢铁/炼油保持1:0.8比例。

正式输入已绑定18份真实结果及最终a85cfcccc0147521fa3635875d68c13a98787c9509d5c9289431085e4c145e7c账户处理器；13条基线、6组固定资产换周及原GTL记录齐全。Figure 1、独立Figure 1b、S20–S25、S28–S29、S36–S48共23份PNG/PDF已生成并逐张检查；figure_verification.json核验所有输出哈希、300dpi、PDF单页、学习基线及标签，render_manifest.json的visual_qa_completed为true。

归档绘图通过archive_sources.json指定保存的模板、参数与处理器位置，支持独立恢复和重绘。CCU/DAC FT和MTJ均以共同route-level输入假设7.6 kWh/kg最终燃料核算；S29显示直接供应链CI，图1/S25使用全部13个真实点重新计算非支配包络。
