# SAF供应链优化模型——技术CAPEX学习曲线文献调研汇总

> 适用模型：13个供应链优化模型（绿氢/副产氢 × 4种CO₂来源 × 2种SAF合成工艺）
> 调研日期：2026年4月

---

## 一、PEM电解槽（Electrolyzer）

### 1.1 学习率数据表

| 文献 | 年份 | 期刊/机构 | PEM学习率 | AEL学习率 | b值(PEM) | CAPEX基准 | 累计装机基准 | 数据范围 |
|------|------|---------|---------|---------|---------|--------|----------|--------|
| Ruhnau et al. | 2025 | Int. J. Hydrogen Energy | **32.1%** | 22.9% | -0.559 | 欧洲项目数据集 | — | 2005–2030 |
| Reksten et al. | 2022 | Int. J. Hydrogen Energy | **36.4%** | 25.1% | -0.644 | 600–1,500 €/kW | IEA全球数据库 | 2000–2030 |
| Bühler & Möst | 2024 | Int. J. Hydrogen Energy | **17.3%**（单因素） | 15.6% | -0.274 | 独立数据库 | 2003年起 | 2003–2020 |
| Bello & Reiner | 2024 | TF&SC / CWPE2476 | **17.5–46.8%**(LBD) | 同 | — | OECD国家级 | 2000年起 | 2000–2022 |
| IRENA | 2020 | 机构报告 | **16–21%** | 16–21% | -0.252~-0.340 | 650–1,000 USD/kW | ~20 GW（含氯碱） | 历史外推 |
| TNO | 2022 | 技术报告P10111 | **12–20%** | — | -0.184~-0.322 | 1,400–1,800 €/kW | 20 GW（含氯碱） | 预测分析 |

### 1.2 建模推荐参数（Wright's Law: C = C₀ × (X/X₀)^b）

| 情景 | 学习率LR | b值 | 基准CAPEX C₀ | 基准装机X₀ | 推荐引用 |
|------|---------|-----|------------|---------|--------|
| 保守 | 16% | -0.252 | 1,400 €/kW (2020) | 20 GW | IRENA 2020 |
| **基准** | **21%** | **-0.340** | **1,400 €/kW (2020)** | **20 GW** | **IRENA 2020 + Bühler 2024** |
| 激进 | 32% | -0.559 | 1,400 €/kW (2020) | 20 GW | Ruhnau 2025 |

### 1.3 成本轨迹

| 年份 | 全球累计（GW） | PEM CAPEX（USD/kW） |
|------|-------------|------------------|
| 2020 | ~20（含氯碱） | 800–1,500 |
| 2025 | ~60 | 500–900 |
| 2030 | ~230–560（NZE） | 320–850 |
| 2050 | ~2,000+ | 60–300 |

### 1.4 本地文献

| 文件 | 大小 | 状态 |
|------|------|------|
| `electrolyzer/TNO_2022_Electrolyzer_Learning_Curve.pdf` | 353 KB | ✅ 已下载 |
| `electrolyzer/Reksten_2022_Future_Cost_PEM_AEL_Electrolysers.pdf` | 1.1 MB | ✅ 已下载 |
| `electrolyzer/OneTwoFactor_2024_Electrolyzer_Experience_Curves.pdf` | 1.1 MB | ✅ 已下载 |
| `electrolyzer/IRENA_2020_NOTE.txt` | — | ⚠️ 手动下载说明（IRENA防爬）|

### 1.5 参考文献（APA格式）

- Ruhnau, O., et al. (2025). Learning in green hydrogen production: Insights from a novel European dataset. *International Journal of Hydrogen Energy*. https://doi.org/10.1016/j.ijhydene.2025.06.002
- Reksten, A. H., Thomassen, M. S., Møller-Holst, S., & Sundseth, K. (2022). Projecting the future cost of PEM and alkaline water electrolysers; a CAPEX model including electrolyser plant size and technology development. *International Journal of Hydrogen Energy*, 47(90), 38106–38113. https://doi.org/10.1016/j.ijhydene.2022.08.306
- Bühler, F., & Möst, D. (2024). One- and two-factor learning curves for electrolyzers. *International Journal of Hydrogen Energy*. https://doi.org/10.1016/j.ijhydene.2024.09.243
- Bello, B., & Reiner, D. (2024). *International knowledge spillovers and learning effects for electrolysers* (CWPE2476). Cambridge Working Paper in Economics. https://doi.org/10.1016/j.techfore.2025.124314
- IRENA. (2020). *Green hydrogen cost reduction: Scaling up electrolysers to meet the 1.5°C climate goal*. International Renewable Energy Agency. ISBN 978-92-9260-295-6.
- de Tezanos Pinto, M., Groenenberg, R., & Detz, R. (2022). *Projections of electrolyzer investment cost reduction through learning curve analysis* (TNO 2022 P10111). Netherlands Organisation for Applied Scientific Research.

---

## 二、DAC直接空气捕获

### 2.1 学习率数据表

| 文献 | 年份 | 期刊/机构 | DAC类型 | 学习率LR | CAPEX基准 | 2050预测 | 数据质量 |
|------|------|---------|--------|---------|--------|--------|--------|
| Sievert et al. | 2024 | Joule (Cell Press) | 液态溶剂 | **11%** | $670/tCO₂ | $226–544/tCO₂ | ★★★★★ |
| Sievert et al. | 2024 | Joule (Cell Press) | 固态吸附 | **12%** | $1,282/tCO₂ | $281–579/tCO₂ | ★★★★★ |
| Sievert et al. | 2024 | Joule (Cell Press) | CaO矿化 | **14%** | — | $230–835/tCO₂ | ★★★★★ |
| Young et al. | 2022 | SSRN | 综合 | **15%** | ~$700/tCO₂ | ~$90/tCO₂ | ★★★★ |
| Fasihi et al. | 2019 | Journal of Cleaner Production | 固态 | **10%** | ~$242/tCO₂ | ~$59/tCO₂ | ★★★★ |
| BCG / Belfer Center | 2022/2023 | 机构报告 | 综合 | **10–15%** | $600–1,300/tCO₂ | $90–440/tCO₂ | ★★★ |

### 2.2 建模推荐参数

| 情景 | 学习率LR | b值 | 基准成本C₀ | 基准规模X₀ | 推荐引用 |
|------|---------|-----|---------|---------|--------|
| 保守 | 8% | -0.120 | $1,000/tCO₂ (2023) | 0.01 Mt/年 | Sievert 2024 |
| **基准** | **12%** | **-0.184** | **$800/tCO₂ (2023)** | **0.01 Mt/年** | **Sievert 2024 Joule** |
| 激进 | 15% | -0.234 | $700/tCO₂ (2023) | 0.01 Mt/年 | Young 2022 |

### 2.3 成本轨迹（Sievert 2024, 固态吸附DAC）

| 全球规模（Mt/年） | 对应年份（估） | 成本（$/tCO₂, 中值） |
|---------------|------------|-----------------|
| 0.01（基准） | 2023 | ~1,200 |
| 1 | 2030 | ~400–700 |
| 100 | 2040 | ~300–400 |
| 1,000（1Gt） | 2050 | ~374（$281–579） |

### 2.4 本地文献

| 文件 | 大小 | 状态 |
|------|------|------|
| `dac/IEAGHG_2021_TR05_Global_DAC_Cost_Assessment.pdf` | 3.6 MB | ✅ 已下载（97页）|
| `dac/Frontiers_2024_Expert_DAC_Cost_Trajectories.pdf` | 1.5 MB | ✅ 已下载（25页）|
| `dac/Frontiers_2025_DAC_Industrialization_Potential.pdf` | 259 KB | ✅ 已下载（9页）|
| Sievert 2024 Joule | — | ⚠️ DOI: 10.1016/j.joule.2024.01.018（CC BY 4.0，付费墙限制自动下载）|

### 2.5 参考文献（APA格式）

- Sievert, K., Schmidt, T. S., & Steffen, B. (2024). Considering technology characteristics to project future costs of direct air capture. *Joule*, *8*(4), 979–999. https://doi.org/10.1016/j.joule.2024.02.005
- Young, R., Yu, L., & Li, J. (2022). *Cost assessment of direct air capture: Based on learning curve and net present value* (SSRN 4108848). https://ssrn.com/abstract=4108848
- Fasihi, M., Efimova, O., & Breyer, C. (2019). Techno-economic assessment of CO₂ direct air capture plants. *Journal of Cleaner Production*, 224, 957–980. https://doi.org/10.1016/j.jclepro.2019.03.086
- IEAGHG. (2021). *Global assessment of direct air capture costs* (TR05). IEA Greenhouse Gas R&D Programme.

---

## 三、燃煤电厂后燃烧CCS

### 3.1 学习率数据表

| 文献 | 年份 | 学习对象 | 学习率LR | 方法 | 中国数据 |
|------|------|--------|---------|------|--------|
| Rubin et al. | 2015 | 捕获岛（post-combustion PCC子系统）| **5.7–12%** | 组件法，以FGD为类比 | 无 |
| iScience（PMC:9730147） | 2022 | 中国煤电CCUS（LBD+LBR双因素） | **LBD: 10–15%；LBR: 8%** | 双因素模型 | ✅ 专项 |
| IEA | 2020 | Boundary Dam → Petra Nova → Shand成本轨迹 | 隐含约**35%**（Shand vs BD） | 项目比较 | 无 |

### 3.2 建模推荐参数

| 情景 | 学习率LR | b值 | 基准成本C₀ | 基准规模X₀ | 推荐引用 |
|------|---------|-----|---------|---------|--------|
| 保守 | 5% | -0.074 | $65/tCO₂（Petra Nova, 2017） | 0.5 Mt/年（全球） | Rubin 2015 |
| **基准** | **10%** | **-0.152** | **$50/tCO₂（NOAK估算）** | **5 Mt/年（全球）** | **Rubin 2015 + iScience 2022** |
| 激进 | 15% | -0.234 | $50/tCO₂ | 5 Mt/年 | iScience 2022（中国LBD） |

### 3.3 成本轨迹（中国煤电CCUS，iScience 2022）

| 年份 | 中国成本（CNY/tCO₂） | 全球成本（USD/tCO₂） |
|------|-----------------|-----------------|
| 2021（基准） | ~330 | ~$51 |
| 2030 | 219 | ~$34 |
| 2040 | 165→63 | ~$26→$10 |

### 3.4 本地文献

| 文件 | 大小 | 状态 |
|------|------|------|
| `coal_ccs/Rubin_2015_Energy_Policy_Learning_Rates_CCS.pdf` | 1.4 MB | ✅ 已下载（21页）|
| `coal_ccs/Rubin_2015_IJGGC_Cost_of_CCS.pdf` | 1.1 MB | ✅ 已下载（23页）|
| `coal_ccs/China_2022_CRP_Coal_CCUS_Optimal_Deployment.pdf` | 3.2 MB | ✅ 已下载（19页）|
| `coal_ccs/SmithSchool_2023_Comparing_High_Low_CCS_Pathways.pdf` | 2.9 MB | ✅ 已下载（63页）|

### 3.5 参考文献（APA格式）

- Rubin, E. S., Azevedo, I. M. L., Jaramillo, P., & Yeh, S. (2015). A review of learning rates for electricity supply technologies. *Energy Policy*, 86, 198–218. https://doi.org/10.1016/j.enpol.2015.06.011
- Zhao, X., et al. (2022). Optimal deployment for carbon capture, utilization and storage in carbon-neutral scenario for China's coal-fired power. *Cell Reports Physical Science*, *3*(12), 101152. https://doi.org/10.1016/j.xcrp.2022.101152
- IEA. (2020). *CCUS in clean energy transitions*. International Energy Agency. https://www.iea.org/reports/ccus-in-clean-energy-transitions

---

## 四、天然气电厂/SMR CCS

### 4.1 学习率数据表

| 文献 | 年份 | 学习对象 | 学习率LR | 方法 |
|------|------|--------|---------|------|
| Rubin et al. | 2007 | NGCC+CCS整体系统 | **2.2%** | 组件法（燃机成熟） |
| van den Broek et al. | 2009 | NGCC+CCS系统 | **5%**（范围2–7%） | 组件法扩展 |
| Frontiers in Energy Research | 2022 | PCC子系统（后燃烧捕获岛） | **11–25%** | FOAK→NOAK分析 |

### 4.2 建模推荐参数

| 情景 | 学习率LR | b值 | 基准成本C₀ | 推荐引用 |
|------|---------|-----|---------|--------|
| 保守 | 2% | -0.029 | $75/tCO₂ (2022) | Rubin 2007 |
| **基准** | **5%** | **-0.074** | **$70/tCO₂** | **van den Broek 2009** |
| 激进 | 11% | -0.168 | $100/tCO₂（FOAK） | Frontiers 2022 |

### 4.3 本地文献

| 文件 | 大小 | 状态 |
|------|------|------|
| `gas_ccs/Frontiers_2022_NGCC_CCS_FOAK_NOAK.pdf` | 2.3 MB | ✅ 已下载（15页）|
| `gas_ccs/IEA_2020_CCUS_Clean_Energy_Transitions.pdf` | 14 MB | ✅ 已下载（174页）|
| `gas_ccs/ETC_2022_CCUS_Technical_Annex.pdf` | 2.9 MB | ✅ 已下载（28页）|

### 4.4 参考文献（APA格式）

- Rubin, E. S., Yeh, S., Antes, M., Berkenpas, M., & Davison, J. (2007). Use of experience curves to estimate the future cost of power plants with CO₂ capture. *International Journal of Greenhouse Gas Control*, 1(2), 188–197. https://doi.org/10.1016/S1750-5836(07)00016-3
- van den Broek, M., Faaij, A., & Turkenburg, W. (2009). Planning for an electricity sector with carbon capture and storage: Case of the Netherlands. *International Journal of Greenhouse Gas Control*, 3(2), 217–236. https://doi.org/10.1016/j.ijggc.2008.09.005
- Li, C., et al. (2022). Cost projection of combined cycle power plants equipped with post-combustion carbon capture considering learning rates and economies of scale. *Frontiers in Energy Research*. https://doi.org/10.3389/fenrg.2022.987166

---

## 五、石油炼厂工业CCS

### 5.1 学习率数据表

| 文献 | 年份 | 学习对象 | 学习率LR | 说明 |
|------|------|--------|---------|------|
| Rubin et al. | 2015 | 工业CCS整体 | **O&M: 4.35%；整体: 3–8%** | 成熟化工过程 |
| Leeson et al. | 2017 | 工业CCS综述（含炼厂） | **3.5–12%** | 按CO₂浓度区分 |
| IEA | 2020 | 炼厂高浓度CO₂流（H₂制氢） | 隐含**低** | Quest项目降本20–25%（单项目） |

### 5.2 建模推荐参数

| 情景 | 学习率LR | b值 | 基准成本C₀ | 推荐引用 |
|------|---------|-----|---------|--------|
| 保守 | 3% | -0.044 | $50/tCO₂（高浓度H₂流） | Rubin 2015 |
| **基准** | **6%** | **-0.088** | **$80/tCO₂（混合过程）** | **Leeson 2017** |
| 激进 | 12% | -0.184 | $100/tCO₂（低浓度烟气） | Leeson 2017 |

### 5.3 本地文献

| 文件 | 大小 | 状态 |
|------|------|------|
| `refinery_ccs/Frontiers_2024_CCS_CCU_Prospective_Review.pdf` | 3.1 MB | ✅ 已下载（26页）|
| `refinery_ccs/IEAGHG_2021_TR05_CCS_Cost_Evaluation_Guidelines.pdf` | 4.9 MB | ✅ 已下载（156页）|

### 5.4 参考文献（APA格式）

- Leeson, D., Mac Dowell, N., Shah, N., Petit, C., & Fennell, P. S. (2017). A Techno-economic analysis and systematic review of carbon capture and storage (CCS) applied to the iron and steel, cement, oil refining and pulp and paper industries, as well as other high purity sources. *International Journal of Greenhouse Gas Control*, 61, 71–84. https://doi.org/10.1016/j.ijggc.2017.03.020

---

## 六、FT合成（一步法PtL）+ e-Methanol + MTJ（两步法）

### 6.1 学习率数据表

| 技术 | 文献 | 年份 | 学习率LR | 说明 |
|------|------|------|---------|------|
| FT合成（PtL整体系统） | ICCT | 2022 | 等效CAGR **~8%/年** | 以成本年降幅表达 |
| FT合成（PtL整体系统） | Way et al. | 2022 | — | 子组件加权：电解槽LR×占比主导 |
| CTL/GTL参考（成熟FT） | 文献综合 | — | **无独立学习率** | 成熟技术，CAPEX受工程超支影响 |
| e-Methanol合成 | IRENA/LBST | 2021/2023 | **~15%**（类比估算） | 无独立文献，驱动因素为H₂价格 |
| MTJ甲醇制航煤 | RSB | 2024 | FOAK→NOAK **10–25%** | 累计规模效应 |

### 6.2 建模推荐参数

| 技术 | 情景 | 学习率LR | b值 | 基准成本 | 基准规模X₀ | 推荐引用 |
|------|------|---------|-----|--------|---------|--------|
| PtL-FT整体 | 基准 | **18%**（电解槽主导） | -0.263 | $4/L SAF | 全球绿氢产量 | Way 2022 + ICCT 2022 |
| e-Methanol | 基准 | **15%** | -0.234 | €1,000/t MeOH | — | LBST 2023（类比） |
| MTJ | 基准 | **15%** | -0.234 | $8/kg SAF（FOAK） | — | RSB 2024（类比） |

**注**：FT合成、e-Methanol、MTJ均缺乏独立实证学习率数据，推荐做敏感性分析（LR范围10–25%）。

### 6.3 成本轨迹

| 技术 | 2023 | 2030 | 2040 | 2050 |
|------|------|------|------|------|
| FT-PtL SAF | $4–6/L | $2–3/L | $1.5–2/L | $1–1.5/L |
| e-Methanol | €750–4,510/t | ~€500/t | ~€300/t | ~€100–200/t |
| MTJ SAF（e-MeOH路线） | $7–13/kg | $3–6/kg | $2–3/kg | $1–2/kg |

### 6.4 CTL/GTL历史CAPEX参考点（用于FT学习曲线基准）

| 项目 | 地点 | 规模 | 实际CAPEX | 年份 |
|------|------|------|---------|------|
| Sasol Secunda | 南非 | 165,000 bpd | 历史成本（1955–1980s） | 历史 |
| Shenhua CTL | 中国宁夏 | 4 Mt/a | ~$7.9亿 | 2016 |
| Shell Pearl GTL | 卡塔尔 | 140,000 bpd | $18–19亿（超支3.5×） | 2011 |
| Oryx GTL | 卡塔尔 | — | $60亿 | ~2006 |

**结论**：大型FT项目普遍出现严重成本超支，不符合经典学习曲线模式；小型模块化FT（Velocys类）量产后可降本~24%/百台。

### 6.5 本地文献

| 文件 | 大小 | 状态 |
|------|------|------|
| `ft_synthesis/ICCT_2022_Current_Future_Cost_Ekerosene.pdf` | 675 KB | ✅ 已下载（15页）|
| `ft_synthesis/LBST_2023_ESAF_Techno_Economics.pdf` | 1.4 MB | ✅ 已下载（45页）|
| `ft_synthesis/Rodrigues_2023_SAF_PtL_Techno_Economic_LCA.pdf` | 3.2 MB | ✅ 已下载 |
| `ft_synthesis/RSB_2024_TEA_SAF_Pathways.pdf` | 3.0 MB | ✅ 已下载（31页）|
| `ft_synthesis/SkyPower_2024_eSAF_Europe_Insights.pdf` | 8.8 MB | ✅ 已下载 |
| `ft_synthesis/Way_2022_Joule_Empirically_Grounded_Tech_Forecasts.pdf` | 17 MB | ✅ 已下载（21页）|
| `ft_synthesis/Agora_2024_Defossilising_Aviation_eSAF.pdf` | 2.3 MB | ✅ 已下载 |

### 6.6 参考文献（APA格式）

- Way, R., Ives, M. C., Mealy, P., & Farmer, J. D. (2022). Empirically grounded technology forecasts and the energy transition. *Joule*, *6*(9), 2057–2082. https://doi.org/10.1016/j.joule.2022.08.009
- Zhou, Y., Searle, P., & Pavlenko, N. (2022). *Current and future cost of e-kerosene in the United States and Europe*. International Council on Clean Transportation. https://theicct.org/wp-content/uploads/2022/02/fuels-us-europe-current-future-cost-ekerosene-us-europe-mar22.pdf
- Rodrigues, A., et al. (2023). SAF production through power-to-liquid: A combined techno-economic and life cycle assessment. *Energy Conversion and Management*, 292, 117427. https://doi.org/10.1016/j.enconman.2023.117427
- RSB. (2024). *Report on techno-economic assessments of SAF pathways*. Roundtable on Sustainable Biomaterials. https://rsb.org/wp-content/uploads/2024/10/report-on-techno-economic-assessments-of-saf-pathways_final.pdf
- Agora Verkehrswende. (2024). *Defossilising aviation with e-SAF*. International PtX Hub. https://www.agora-verkehrswende.de/fileadmin/Projekte/2024/E-Fuels-im-Luftverkehr_EN/111_Defossilising_Aviation_with_e-SAF.pdf

---

## 七、综合建模参数速查表

| 技术 | 适用模型# | 保守LR | **基准LR** | 激进LR | 基准b值 | 当前成本 | 最佳引用 |
|------|---------|--------|-----------|--------|--------|--------|--------|
| PEM电解槽 | 1,2,3,6,7,12,13 | 16% | **21%** | 32% | -0.340 | 1,400 €/kW | IRENA 2020 |
| DAC | 2,3,9,10 | 8% | **12%** | 15% | -0.184 | $800/tCO₂ | Sievert 2024 *Joule* |
| 煤电CCS | 6,7,12,13 | 5% | **10%** | 15% | -0.152 | $50/tCO₂ | Rubin 2015 + iScience 2022 |
| 天然气CCS/SMR | 4,5,6,7,11,12,13 | 2% | **5%** | 11% | -0.074 | $70/tCO₂ | van den Broek 2009 |
| 炼厂工业CCS | 6,7,12,13 | 3% | **6%** | 12% | -0.088 | $80/tCO₂ | Leeson 2017 |
| FT合成（PtL） | 1,3,5,7,8,10,13 | 10% | **18%** | 25% | -0.263 | $4/L SAF | Way 2022 + ICCT 2022 |
| e-Methanol | 2,4,6,9,11,12 | 10% | **15%** | 20% | -0.234 | €1,000/t | LBST 2023（类比） |
| MTJ | 2,4,6,9,11,12 | 10% | **15%** | 25% | -0.234 | $8/kg SAF | RSB 2024（类比） |

---

## 八、文献目录结构

```
learning_curves/references/
├── electrolyzer/          # PEM电解槽（3个PDF + 1个引用说明）
├── dac/                   # DAC直接空气捕获（3个PDF）
├── coal_ccs/              # 燃煤电厂CCS（4个PDF）
├── gas_ccs/               # 天然气电厂CCS（3个PDF）
├── refinery_ccs/          # 炼厂工业CCS（2个PDF）
└── ft_synthesis/          # FT/e-Methanol/MTJ（7个PDF + 1个引用说明）
```

**总计**：22个PDF，共约80 MB

---

*注：部分文献（Ruhnau 2025、Sievert 2024 Joule）因出版商反爬机制无法自动下载，已记录关键数据，请通过机构VPN或浏览器手动下载。*
