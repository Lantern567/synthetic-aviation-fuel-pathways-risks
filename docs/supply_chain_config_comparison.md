# 供应链优化器配置对比报告

本报告列出了四个优化器之间所有取值不同的参数；“缺失”表示该配置文件没有该参数。对于复杂的列表或对象，仅输出长度等摘要以减少噪声。

| 项目 | 配置文件路径 | 扁平化参数数量 |
| --- | --- | --- |
| 煤+绿氢SAF | `products/supply_chain_optimization/coal_hydrogen_saf_optimization/data/CoalHydrogenSAFOptimizer_config.yaml` | 315 |
| DAC氢SAF | `shared/config/DACHydrogenSAFOptimizer_config.yaml` | 339 |
| 绿氢供应链 | `shared/data/GreenHydrogenSupplyChainOptimizer_config.yaml` | 311 |
| 天然气供应链 | `shared/data/NaturalGasSupplyChainOptimizer_config.yaml` | 283 |

## 基础参数（basic_parameters）

| 参数键 | 煤+绿氢SAF | DAC氢SAF | 绿氢供应链 | 天然气供应链 |
| --- | --- | --- | --- | --- |
| avg_lng_capacity_mcm_per_year | 缺失 | 缺失 | 缺失 | 1000 |
| use_co2_pipeline_distance | False | True | True | 缺失 |

## 产能约束（capacity_limits）

| 参数键 | 煤+绿氢SAF | DAC氢SAF | 绿氢供应链 | 天然气供应链 |
| --- | --- | --- | --- | --- |
| electrolyzer_max_capacity_kg_per_hour | 100000 | 100000 | 100000 | 2000 |
| electrolyzer_min_capacity_kg_per_hour | 100 | 100 | 100 | 缺失 |
| hydrogen_pipeline_max_daily_capacity_kg | 500000 | 缺失 | 缺失 | 50000 |
| hydrogen_truck_max_daily_capacity_kg | 缺失 | 缺失 | 缺失 | 10000 |
| mtj_capacity_estimates.default | 缺失 | 缺失 | 缺失 | 1500 |
| mtj_capacity_estimates.industrial | 缺失 | 缺失 | 缺失 | 2000 |
| mtj_capacity_estimates.petrochemical_base | 缺失 | 缺失 | 缺失 | 5000 |
| mtj_capacity_estimates.renewable_energy | 缺失 | 缺失 | 缺失 | 1000 |
| mtj_max_capacity_kg_per_hour | 缺失 | 缺失 | 缺失 | 100000 |
| ng_demand_estimates.default_daily_volume_m3 | 缺失 | 缺失 | 缺失 | 10000 |
| saf_capacity_estimates.default | 2000 | 2000 | 2000 | 缺失 |
| saf_capacity_estimates.industrial | 3000 | 3000 | 3000 | 缺失 |
| saf_capacity_estimates.petrochemical_base | 5000 | 5000 | 5000 | 缺失 |
| saf_reactor_max_capacity_kg_per_hour | 1000000 | 1000000 | 1000000 | 缺失 |
| saf_reactor_min_capacity_kg_per_hour | 100 | 0 | 0 | 缺失 |

## 碳排放参数（carbon_emission_parameters）

| 参数键 | 煤+绿氢SAF | DAC氢SAF | 绿氢供应链 | 天然气供应链 |
| --- | --- | --- | --- | --- |
| facility_construction.electrolyzer_embodied | 1500 | 1500 | 1500 | 1200 |
| facility_construction.electrolyzer_lifetime | 15 | 15 | 15 | 20 |
| facility_construction.saf_reactor_embodied | 2000 | 2000 | 2000 | 缺失 |
| facility_construction.saf_reactor_lifetime | 25 | 25 | 25 | 缺失 |
| production_process.co2_capture_efficiency | 0.85 | 缺失 | 缺失 | 缺失 |
| production_process.co2_capture_energy_kwh_per_ton | 120 | 缺失 | 缺失 | 缺失 |
| production_process.coal_co2_yield_kg_per_kg | 2.44 | 缺失 | 缺失 | 缺失 |
| production_process.coal_gasification_direct_emission | 0.15 | 缺失 | 缺失 | 缺失 |
| production_process.coal_gasification_energy_kwh_per_kg | 2.22 | 缺失 | 缺失 | 缺失 |
| production_process.coal_mining_emission | 0.04 | 缺失 | 缺失 | 缺失 |
| production_process.coal_transport_emission | 0.05 | 缺失 | 缺失 | 缺失 |
| production_process.dac_capture_emission | 缺失 | 7.0 | 缺失 | 缺失 |
| production_process.dac_capture_energy | 缺失 | 350 | 缺失 | 缺失 |
| production_process.gasification_electricity_intensity | 0.6 | 缺失 | 缺失 | 缺失 |
| production_process.h2_addition_rate | 缺失 | 缺失 | 缺失 | 40 |
| production_process.h2_electrolysis_emission | 0.05 | 0.05 | 0.05 | 缺失 |
| production_process.ng_process_emission | 缺失 | 缺失 | 缺失 | 0.8 |
| production_process.ng_to_methanol_rate | 缺失 | 缺失 | 缺失 | 1.2 |
| production_process.saf_process_energy | 3.0 | 3.0 | 3.0 | 缺失 |
| production_process.saf_synthesis_emission | 0.3 | 0.3 | 0.3 | 缺失 |
| raw_materials.dac_energy_intensity | 缺失 | 0.02 | 缺失 | 缺失 |
| raw_materials.dac_equipment_embodied | 缺失 | 0.05 | 缺失 | 缺失 |
| raw_materials.dac_total_intensity | 缺失 | 0.07 | 缺失 | 缺失 |
| raw_materials.ng_extraction_intensity | 缺失 | 缺失 | 缺失 | 0.25 |
| raw_materials.ng_pipeline_transport | 缺失 | 缺失 | 缺失 | 0.01 |
| renewable_energy.grid_electricity_intensity | 0.6 | 0.6 | 0.6 | 缺失 |
| renewable_energy.solar_power_intensity | 0.045 | 0.045 | 0.045 | 缺失 |
| renewable_energy.wind_power_intensity | 0.015 | 0.015 | 0.015 | 缺失 |
| storage_handling.h2_storage_energy | 2 | 2 | 2 | 0.5 |
| storage_handling.saf_storage_energy | 5 | 5 | 5 | 缺失 |
| transportation.co2_pipeline_intensity | 0.01 | 0.01 | 0.01 | 缺失 |
| transportation.co2_truck_intensity | 0.08 | 0.08 | 0.08 | 缺失 |
| transportation.h2_pipeline_intensity | 0.02 | 0.02 | 0.02 | 0.005 |
| transportation.ng_truck_intensity | 缺失 | 缺失 | 缺失 | 0.1 |
| transportation.saf_truck_intensity | 0.12 | 0.12 | 0.12 | 缺失 |

## CO₂聚类参数（co2_clustering_parameters）

| 参数键 | 煤+绿氢SAF | DAC氢SAF | 绿氢供应链 | 天然气供应链 |
| --- | --- | --- | --- | --- |
| clustering_output_path | 缺失 | co2_clustering_results.json | co2_clustering_results.json | 缺失 |
| enable_clustering | 缺失 | True | True | 缺失 |
| enable_pipeline_optimization | 缺失 | True | True | 缺失 |
| eps_distance_km | 缺失 | 30.0 | 30.0 | 缺失 |
| export_clustering_results | 缺失 | True | True | 缺失 |
| max_clusters | 缺失 | 200 | 200 | 缺失 |
| min_samples | 缺失 | 3 | 3 | 缺失 |
| noise_plant_handling | 缺失 | direct_connection | direct_connection | 缺失 |
| pipeline_weight | 缺失 | 0.3 | 0.3 | 缺失 |
| processing_cost_base | 缺失 | 10.0 | 10.0 | 缺失 |
| shared_pipeline_discount_factor | 缺失 | 0.65 | 0.65 | 缺失 |

## CO₂供应参数（co2_parameters）

| 参数键 | 煤+绿氢SAF | DAC氢SAF | 绿氢供应链 | 天然气供应链 |
| --- | --- | --- | --- | --- |
| capture_costs.coal_power_yuan_per_ton | 150 | 缺失 | 150 | 缺失 |
| capture_costs.lng_power_yuan_per_ton | 180 | 缺失 | 180 | 缺失 |
| capture_costs.oil_refinery_yuan_per_ton | 120 | 缺失 | 120 | 缺失 |
| capture_sources.coal_power_capacity_factor | 0.7 | 缺失 | 0.7 | 缺失 |
| capture_sources.coal_power_capture_rate | 0.85 | 缺失 | 0.85 | 缺失 |
| capture_sources.coal_power_emission_factor | 0.95 | 缺失 | 0.95 | 缺失 |
| capture_sources.lng_power_capacity_factor | 0.75 | 缺失 | 0.75 | 缺失 |
| capture_sources.lng_power_capture_rate | 0.9 | 缺失 | 0.9 | 缺失 |
| capture_sources.lng_power_emission_factor | 0.42 | 缺失 | 0.42 | 缺失 |
| capture_sources.oil_refinery_capacity_factor | 0.85 | 缺失 | 0.85 | 缺失 |
| capture_sources.oil_refinery_capture_rate | 0.8 | 缺失 | 0.8 | 缺失 |
| capture_sources.oil_refinery_emission_factor | 0.6 | 缺失 | 0.6 | 缺失 |
| storage.max_storage_capacity_ton | 50000 | 缺失 | 50000 | 缺失 |
| storage.storage_cost_yuan_per_ton_per_day | 0.5 | 缺失 | 0.5 | 缺失 |
| storage.storage_density_ton_per_m3 | 0.8 | 缺失 | 0.8 | 缺失 |
| transport.liquefaction_cost_yuan_per_ton | 80 | 缺失 | 80 | 缺失 |
| transport.max_pipeline_capacity_ton_per_day | 5000 | 缺失 | 5000 | 缺失 |
| transport.max_truck_capacity_ton_per_day | 500 | 缺失 | 500 | 缺失 |
| transport.pipeline_transport_cost_function.data_points | list(len=7), item=list | 缺失 | list(len=7), item=list | 缺失 |
| transport.pipeline_transport_cost_function.description | CO₂管道运输成本曲线（包含建设成本摊销） / CO₂ pipeline transport cost curve (including construction cost amortization) / 模仿氢气管道成本结构，基于实... | 缺失 | CO₂管道运输成本曲线（包含建设成本摊销） / CO₂ pipeline transport cost curve (including construction cost amortization) / 模仿氢气管道成本结构，基于实... | 缺失 |
| transport.pipeline_transport_cost_function.function_type | piecewise_linear | 缺失 | piecewise_linear | 缺失 |
| transport.pipeline_transport_cost_function.notes | ⚠️ 重要说明 Important Notes: / - 成本函数已包含以下所有费用（与氢气管道成本处理方式一致）: /   * 管道建设投资摊销 (Pipeline construction amortization) /   * ... | 缺失 | ⚠️ 重要说明 Important Notes: / - 成本函数已包含以下所有费用（与氢气管道成本处理方式一致）: /   * 管道建设投资摊销 (Pipeline construction amortization) /   * ... | 缺失 |
| transport.pipeline_transport_cost_function.unit | yuan_per_ton_co2_per_100km | 缺失 | yuan_per_ton_co2_per_100km | 缺失 |
| transport.truck_cost_yuan_per_ton_per_100km | 50 | 缺失 | 50 | 缺失 |

## 煤炭参数（coal_parameters）

| 参数键 | 煤+绿氢SAF | DAC氢SAF | 绿氢供应链 | 天然气供应链 |
| --- | --- | --- | --- | --- |
| base_co2_yield_kg_per_kg_saf | 3.5 | 缺失 | 缺失 | 缺失 |
| carbon_content | 0.75 | 缺失 | 缺失 | 缺失 |
| co2_per_kg_coal | 2.44 | 缺失 | 缺失 | 缺失 |
| coal_consumption_kg_per_kg_saf | 1.8 | 缺失 | 缺失 | 缺失 |
| coal_price_yuan_per_ton | 525 | 缺失 | 缺失 | 缺失 |
| coal_type | bituminous | 缺失 | 缺失 | 缺失 |
| gasification_efficiency | 0.75 | 缺失 | 缺失 | 缺失 |
| gasification_energy_cost_yuan_per_mj | 0.5 | 缺失 | 缺失 | 缺失 |
| gasification_energy_kwh_per_kg | 2.22 | 缺失 | 缺失 | 缺失 |
| gasification_energy_mj_per_kg | 8.0 | 缺失 | 缺失 | 缺失 |

## 成本参数（cost_parameters）

| 参数键 | 煤+绿氢SAF | DAC氢SAF | 绿氢供应链 | 天然气供应链 |
| --- | --- | --- | --- | --- |
| electrolysis.electrolysis_efficiency | 0.7 | 0.7 | 0.7 | 0.8 |
| electrolysis.electrolysis_power_consumption | 55 | 50 | 50 | 45 |
| electrolysis.formula_based_transport.trip_fixed_cost | 缺失 | 缺失 | 缺失 | 2000 |
| electrolysis.formula_based_transport.utilization_rate | 缺失 | 缺失 | 缺失 | 0.8 |
| electrolysis.formula_based_transport.variable_cost_per_km | 缺失 | 缺失 | 缺失 | 15.0 |
| electrolysis.formula_based_transport.vehicle_payload_kg | 缺失 | 缺失 | 缺失 | 25000 |
| hydrogen.electrolysis_cost_yuan_per_kg | 25.0 | 25.0 | 25.0 | 缺失 |
| hydrogen.formula_based_transport.trip_fixed_cost | 3000 | 3000 | 3000 | 缺失 |
| hydrogen.formula_based_transport.utilization_rate | 0.75 | 0.75 | 0.75 | 缺失 |
| hydrogen.formula_based_transport.variable_cost_per_km | 20.0 | 20.0 | 20.0 | 缺失 |
| hydrogen.formula_based_transport.vehicle_payload_kg | 500 | 500 | 500 | 缺失 |
| raw_materials.hydrogen_market_price_yuan_per_kg | 25.0 | 25.0 | 25.0 | 30 |
| raw_materials.natural_gas_price_yuan_per_m3 | 缺失 | 缺失 | 缺失 | 4.2 |
| raw_materials.renewable_electricity_cost_yuan_per_mwh | 350 | 350 | 350 | 500 |
| renewable_energy.grid_electricity_price_yuan_per_kwh | 0.7 | 0.7 | 0.7 | 缺失 |
| renewable_energy.solar_power_price_yuan_per_kwh | 0.4 | 0.4 | 0.4 | 缺失 |
| renewable_energy.wind_power_price_yuan_per_kwh | 0.35 | 0.35 | 0.35 | 缺失 |
| shortage_penalty_yuan_per_kg | 5000000 | 2500 | 2500 | 2500 |

## DAC参数（dac_parameters）

| 参数键 | 煤+绿氢SAF | DAC氢SAF | 绿氢供应链 | 天然气供应链 |
| --- | --- | --- | --- | --- |
| atmospheric_co2_ppm | 缺失 | 415 | 缺失 | 缺失 |
| capex_per_module_yuan | 缺失 | 10000000 | 缺失 | 缺失 |
| capture_cost_2030_yuan_per_ton | 缺失 | 2500 | 缺失 | 缺失 |
| capture_cost_yuan_per_ton | 缺失 | 4500 | 缺失 | 缺失 |
| capture_efficiency | 缺失 | 0.95 | 缺失 | 缺失 |
| co2_per_kg_methanol | 缺失 | 2.8 | 缺失 | 缺失 |
| co2_per_kg_saf | 缺失 | 3.5 | 缺失 | 缺失 |
| co2_purity | 缺失 | 0.995 | 缺失 | 缺失 |
| cost_breakdown.capex_amortization | 缺失 | 0.4 | 缺失 | 缺失 |
| cost_breakdown.energy | 缺失 | 0.35 | 缺失 | 缺失 |
| cost_breakdown.opex_maintenance | 缺失 | 0.15 | 缺失 | 缺失 |
| cost_breakdown.other | 缺失 | 0.1 | 缺失 | 缺失 |
| cost_reduction_rate | 缺失 | 0.1 | 缺失 | 缺失 |
| dac_energy_share | 缺失 | 0.86 | 缺失 | 缺失 |
| deployment_strategy | 缺失 | independent_deployment | 缺失 | 缺失 |
| energy_breakdown.auxiliary | 缺失 | 20 | 缺失 | 缺失 |
| energy_breakdown.compression | 缺失 | 30 | 缺失 | 缺失 |
| energy_breakdown.fan_blower | 缺失 | 50 | 缺失 | 缺失 |
| energy_breakdown.heating_regeneration | 缺失 | 250 | 缺失 | 缺失 |
| energy_kwh_per_ton_co2 | 缺失 | 350 | 缺失 | 缺失 |
| energy_type | 缺失 | renewable_electricity | 缺失 | 缺失 |
| facility_parameters.can_colocate_with_saf | 缺失 | True | 缺失 | 缺失 |
| facility_parameters.facility_construction_cost_yuan | 缺失 | 50000000 | 缺失 | 缺失 |
| facility_parameters.max_capacity_kg_per_hour | 缺失 | 100000 | 缺失 | 缺失 |
| facility_parameters.suitable_locations | 缺失 | ["solar_plant", "wind_farm", "airport"] | 缺失 | 缺失 |
| land_area_hectare_per_kton_year | 缺失 | 0.1 | 缺失 | 缺失 |
| module_availability | 缺失 | 0.9 | 缺失 | 缺失 |
| module_capacity_ton_year | 缺失 | 2000 | 缺失 | 缺失 |
| module_lifetime_years | 缺失 | 20 | 缺失 | 缺失 |
| opex_ratio | 缺失 | 0.05 | 缺失 | 缺失 |
| supply_assumptions.location_flexibility | 缺失 | high | 缺失 | 缺失 |
| supply_assumptions.scaling | 缺失 | modular | 缺失 | 缺失 |
| supply_assumptions.supply_model | 缺失 | independent_facility | 缺失 | 缺失 |
| supply_assumptions.supply_unlimited | 缺失 | True | 缺失 | 缺失 |
| technology | 缺失 | solid_sorbent | 缺失 | 缺失 |
| technology_cn | 缺失 | 固体吸附剂DAC | 缺失 | 缺失 |
| transport_distance_km | 缺失 | variable | 缺失 | 缺失 |
| water_consumption_liter_per_ton_co2 | 缺失 | 5 | 缺失 | 缺失 |

## 数据路径（data_paths）

| 参数键 | 煤+绿氢SAF | DAC氢SAF | 绿氢供应链 | 天然气供应链 |
| --- | --- | --- | --- | --- |
| co2_data.co2_capture_sources | products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/data/co2_capture_sources.csv | products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/data/co2_capture_sources.csv | products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/data/co2_capture_sources.csv | 缺失 |
| gis_data.coal_power_plants | products/gis_energy_mapping/gis_data_scraper/scraped_gis_data/coal_power_plants.csv | products/gis_energy_mapping/gis_data_scraper/scraped_gis_data/coal_power_plants.csv | products/gis_energy_mapping/gis_data_scraper/scraped_gis_data/coal_power_plants.csv | 缺失 |
| gis_data.gas_power_plants | products/gis_energy_mapping/gis_data_scraper/scraped_gis_data/gas_power_plants.csv | products/gis_energy_mapping/gis_data_scraper/scraped_gis_data/gas_power_plants.csv | products/gis_energy_mapping/gis_data_scraper/scraped_gis_data/gas_power_plants.csv | 缺失 |
| gis_data.lng_terminals_original | 缺失 | 缺失 | 缺失 | products/gis_energy_mapping/gis_data_scraper/scraped_gis_data/lng_terminals.csv |
| gis_data.lng_terminals_preprocessed | 缺失 | 缺失 | 缺失 | products/gis_energy_mapping/gis_data_scraper/scraped_gis_data/lng_terminals_with_capacity.xlsx |
| gis_data.ng_pipelines_integrated | 缺失 | 缺失 | 缺失 | products/supply_chain_optimization/natural_gas_supply_chain_optimization/data/integrated_gas_pipeline_price_data_with... |
| gis_data.ng_pipelines_original | 缺失 | 缺失 | 缺失 | products/gis_energy_mapping/scraped_gis_data/natural_gas_pipelines.csv |
| gis_data.ng_pipelines_preprocessed | 缺失 | 缺失 | 缺失 | products/gis_energy_mapping/gis_data_scraper/scraped_gis_data/natural_gas_pipelines_with_capacity.xlsx |
| gis_data.oil_refineries | products/gis_energy_mapping/gis_data_scraper/scraped_gis_data/oil_refineries.csv | products/gis_energy_mapping/gis_data_scraper/scraped_gis_data/oil_refineries.csv | products/gis_energy_mapping/gis_data_scraper/scraped_gis_data/oil_refineries.csv | 缺失 |
| output_paths.file_templates.co2_transport_plan | co2_transport_plan_{timestamp}.csv | co2_transport_plan_{timestamp}.csv | co2_transport_plan_{timestamp}.csv | 缺失 |
| output_paths.file_templates.lng_terminals | 缺失 | 缺失 | 缺失 | lng_terminals_{timestamp}.csv |
| output_paths.file_templates.mtj_transport_plan | 缺失 | 缺失 | 缺失 | mtj_transport_plan_{timestamp}.csv |
| output_paths.file_templates.ng_pipelines | 缺失 | 缺失 | 缺失 | ng_pipelines_{timestamp}.csv |
| output_paths.file_templates.ng_transport_plan | 缺失 | 缺失 | 缺失 | ng_transport_plan_{timestamp}.csv |
| output_paths.file_templates.saf_transport_plan | saf_transport_plan_{timestamp}.csv | saf_transport_plan_{timestamp}.csv | saf_transport_plan_{timestamp}.csv | 缺失 |
| output_paths.results_base_dir | products/supply_chain_optimization/coal_hydrogen_saf_optimization/results | products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results | products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results | products/supply_chain_optimization/natural_gas_supply_chain_optimization/results |

## 依赖设置（dependencies）

| 参数键 | 煤+绿氢SAF | DAC氢SAF | 绿氢供应链 | 天然气供应链 |
| --- | --- | --- | --- | --- |
| data_inputs.co2_capture_sources | products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/data/co2_capture_sources.csv | products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/data/co2_capture_sources.csv | products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/data/co2_capture_sources.csv | 缺失 |
| data_inputs.lng_terminals_original | 缺失 | 缺失 | 缺失 | products/gis_energy_mapping/gis_data_scraper/scraped_gis_data/lng_terminals.csv |
| data_inputs.lng_terminals_preprocessed | 缺失 | 缺失 | 缺失 | products/gis_energy_mapping/gis_data_scraper/scraped_gis_data/lng_terminals_with_capacity.xlsx |
| data_inputs.ng_pipelines_integrated | 缺失 | 缺失 | 缺失 | products/supply_chain_optimization/natural_gas_supply_chain_optimization/data/integrated_gas_pipeline_price_data_with... |
| data_inputs.ng_pipelines_original | 缺失 | 缺失 | 缺失 | products/gis_energy_mapping/scraped_gis_data/natural_gas_pipelines.csv |
| data_inputs.ng_pipelines_preprocessed | 缺失 | 缺失 | 缺失 | products/gis_energy_mapping/gis_data_scraper/scraped_gis_data/natural_gas_pipelines_with_capacity.xlsx |
| data_inputs.osm_pbf_default | products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/data/china-latest.osm.pbf | products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/data/china-latest.osm.pbf | products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/data/china-latest.osm.pbf | products/supply_chain_optimization/natural_gas_supply_chain_optimization/data/china-latest.osm.pbf |
| internal_modules | list(len=6), item=dict | list(len=6), item=dict | list(len=6), item=dict | list(len=7), item=dict |
| main_entry.class | GreenHydrogenSupplyChainOptimizer | GreenHydrogenSupplyChainOptimizer | GreenHydrogenSupplyChainOptimizer | NaturalGasSupplyChainOptimizer |
| main_entry.source_file | products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/src/core/green_hydrogen_optimization_mode... | products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/src/core/green_hydrogen_optimization_mode... | products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/src/core/green_hydrogen_optimization_mode... | products/supply_chain_optimization/natural_gas_supply_chain_optimization/src/natural_gas_optimization_model.py |
| output_artifacts.dir | products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results | products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results | products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results | products/supply_chain_optimization/natural_gas_supply_chain_optimization/results |
| quick_validation_checklist | 1. pip install -r requirements.txt (确保gurobipy已就绪) / 2. 检查 airports_excel 是否存在 / 3. 检查 wind/solar 目录存在且含CSV / 4. 检查 c... | 1. pip install -r requirements.txt (确保gurobipy已就绪) / 2. 检查 airports_excel 是否存在 / 3. 检查 wind/solar 目录存在且含CSV / 4. 检查 c... | 1. pip install -r requirements.txt (确保gurobipy已就绪) / 2. 检查 airports_excel 是否存在 / 3. 检查 wind/solar 目录存在且含CSV / 4. 检查 c... | 1. pip install -r requirements.txt (确保gurobipy已就绪) / 2. 检查 airports_excel 是否存在 / 3. 检查 wind/solar 目录存在且含CSV / 4. 检查 n... |

## 经济参数（economic_parameters）

| 参数键 | 煤+绿氢SAF | DAC氢SAF | 绿氢供应链 | 天然气供应链 |
| --- | --- | --- | --- | --- |
| capacity_factors.mtj_plant_capacity_factor | 缺失 | 缺失 | 缺失 | 0.85 |
| capacity_factors.saf_reactor_capacity_factor | 0.85 | 0.85 | 0.85 | 缺失 |
| levelized_cost_threshold_yuan_per_kg | 50 | 1000 | 1000 | 7 |
| mtj_plant_lifetime | 缺失 | 缺失 | 缺失 | 20 |
| saf_reactor_lifetime | 25 | 25 | 25 | 缺失 |

## 设备原始成本（equipment_raw_costs）

| 参数键 | 煤+绿氢SAF | DAC氢SAF | 绿氢供应链 | 天然气供应链 |
| --- | --- | --- | --- | --- |
| electrolyzer.opex_raw | 200000 | 200000 | 200000 | 800 |
| saf_reactor.capex_raw | 6000000 | 6000000 | 6000000 | 缺失 |
| saf_reactor.opex_raw | 150000 | 150000 | 150000 | 缺失 |
| storage.capex_raw | 200000 | 2000 | 2000 | 1500 |
| storage.opex_raw | 5000 | 30 | 30 | 20 |

## 设施LCOE参数（facility_lcoe_parameters）

| 参数键 | 煤+绿氢SAF | DAC氢SAF | 绿氢供应链 | 天然气供应链 |
| --- | --- | --- | --- | --- |
| catalyst_cost_yuan_per_kg_saf | 0.1 | 0.1 | 0.1 | 缺失 |
| energy_cost_yuan_per_kwh | 0.5 | 0.5 | 0.5 | 缺失 |
| fixed_capex | 60000000 | 60000000 | 60000000 | 20000000 |
| fixed_opex_annual | 18000000 | 18000000 | 18000000 | 10000000 |
| variable_capex_per_capacity | 35000 | 35000 | 35000 | 20000 |
| variable_opex_per_kg | 0.8 | 0.8 | 0.8 | 0.3 |

## 绿氢供应（green_hydrogen_supply）

| 参数键 | 煤+绿氢SAF | DAC氢SAF | 绿氢供应链 | 天然气供应链 |
| --- | --- | --- | --- | --- |
| electrolyzer_efficiency | 0.7 | 0.7 | 0.7 | 缺失 |
| production_cost_yuan_per_kg | 25 | 25 | 25 | 缺失 |
| production_energy_kwh_per_kg | 55 | 50 | 50 | 缺失 |
| storage.compression_cost_yuan_per_kg | 2.0 | 2.0 | 2.0 | 缺失 |
| storage.liquefaction_cost_yuan_per_kg | 5.0 | 5.0 | 5.0 | 缺失 |
| storage.storage_cost_yuan_per_kg_per_day | 1.0 | 1.0 | 1.0 | 缺失 |
| transport.pipeline_capex_yuan_per_km | 5000000 | 5000000 | 5000000 | 缺失 |
| transport.pipeline_cost_yuan_per_kg_per_100km | 0.5 | 0.5 | 0.5 | 缺失 |
| transport.truck_cost_yuan_per_kg_per_100km | 2.0 | 2.0 | 2.0 | 缺失 |

## 元数据（metadata）

| 参数键 | 煤+绿氢SAF | DAC氢SAF | 绿氢供应链 | 天然气供应链 |
| --- | --- | --- | --- | --- |
| base_version | 缺失 | 2.0.0 | 缺失 | 缺失 |
| co2_source | 缺失 | direct_air_capture | 缺失 | 缺失 |
| created_date | 2025-10-27 | 2025-10-13 | 2025-10-13 | 2025-01-09 |
| description | CoalHydrogenSAFOptimizer综合参数配置文件 / Coal Hydrogen SAF Supply Chain Optimizer Comprehensive Configuration File /  | DAC直接空气捕获+绿氢制SAF供应链优化 | GreenHydrogenSupplyChainOptimizer综合参数配置文件 / Green Hydrogen Supply Chain Optimizer Comprehensive Configuration File /  | NaturalGasSupplyChainOptimizer综合参数配置文件 / 天然气供应链 Optimizer Comprehensive Configuration File /  |
| last_updated | 2025-10-27 | 2025-10-13 | 2025-10-13 | 2025-09-08 |
| notes | 配置文件说明: / - 此配置文件包含了CoalHydrogenSAFOptimizer类的所有参数配置 / - 修改此文件可以调整优化器的行为，无需修改源代码 / - 参数分为15个主要类别，涵盖了经济、技术、成本、数据路径等各个方... | 配置文件说明: / - 此配置文件包含了GreenHydrogenSupplyChainOptimizer类的所有参数配置 / - 修改此文件可以调整优化器的行为，无需修改源代码 / - 参数分为15个主要类别，涵盖了经济、技术、成本... | 配置文件说明: / - 此配置文件包含了GreenHydrogenSupplyChainOptimizer类的所有参数配置 / - 修改此文件可以调整优化器的行为，无需修改源代码 / - 参数分为15个主要类别，涵盖了经济、技术、成本... | 配置文件说明: / - 此配置文件包含了NaturalGasSupplyChainOptimizer类的所有参数配置 / - 修改此文件可以调整优化器的行为，无需修改源代码 / - 参数分为18个主要类别，涵盖了经济、技术、成本、数据... |
| version | 3.0.0 | 4.0.0 | 2.0.0 | 1.1.0 |

## 目标函数系数（objective_coefficients）

| 参数键 | 煤+绿氢SAF | DAC氢SAF | 绿氢供应链 | 天然气供应链 |
| --- | --- | --- | --- | --- |
| hydrogen_transport_vehicle.max_vehicles_per_day | 缺失 | 缺失 | 缺失 | 48 |
| hydrogen_transport_vehicle.vehicle_capacity_kg | 缺失 | 缺失 | 缺失 | 500 |
| storage.hydrogen_equipment_unit_cost_yuan_per_kg | 缺失 | 缺失 | 缺失 | 20 |

## 运行参数（operational_parameters）

| 参数键 | 煤+绿氢SAF | DAC氢SAF | 绿氢供应链 | 天然气供应链 |
| --- | --- | --- | --- | --- |
| default_transport_distances.co2_transport_distance_km | 80 | 80 | 80 | 缺失 |
| default_transport_distances.h2_transport_distance_km | 100 | 100 | 100 | 缺失 |
| default_transport_distances.hydrogen_transport_distance_km | 缺失 | 缺失 | 缺失 | 50 |
| default_transport_distances.ng_transport_distance_km | 缺失 | 缺失 | 缺失 | 80 |

## 优化控制（optimization）

| 参数键 | 煤+绿氢SAF | DAC氢SAF | 绿氢供应链 | 天然气供应链 |
| --- | --- | --- | --- | --- |
| super_graph_cache_to_disk | 缺失 | 缺失 | False | 缺失 |
| super_graph_k_connections | 缺失 | 缺失 | 10 | 缺失 |
| use_super_graph_precompute | 缺失 | 缺失 | True | 缺失 |

## 求解器参数（solver_parameters）

| 参数键 | 煤+绿氢SAF | DAC氢SAF | 绿氢供应链 | 天然气供应链 |
| --- | --- | --- | --- | --- |
| MIPGap | 0.01 | 0.05 | 0.01 | 0.1 |
| Threads | 0 | 128 | 128 | 128 |

## 供应能力（supply_capacity）

| 参数键 | 煤+绿氢SAF | DAC氢SAF | 绿氢供应链 | 天然气供应链 |
| --- | --- | --- | --- | --- |
| lng_terminal_capacity.default_capacity_mcm_per_year | 缺失 | 缺失 | 缺失 | 300 |
| natural_gas_supply.airport_max_flow_m3_per_hour | 缺失 | 缺失 | 缺失 | 5000 |
| natural_gas_supply.default_daily_volume_m3 | 缺失 | 缺失 | 缺失 | 10000 |
| natural_gas_supply.default_max_flow_m3_per_hour | 缺失 | 缺失 | 缺失 | 10000 |
| natural_gas_supply.default_reduced_flow_m3_per_hour | 缺失 | 缺失 | 缺失 | 4000 |

## 技术路线（technologies）

| 参数键 | 煤+绿氢SAF | DAC氢SAF | 绿氢供应链 | 天然气供应链 |
| --- | --- | --- | --- | --- |
| airport_integrated_conversion.efficiency | 缺失 | 缺失 | 缺失 | 0.85 |
| airport_integrated_conversion.h2_consumption_ratio | 缺失 | 缺失 | 缺失 | 0.12 |
| airport_integrated_conversion.hydrogen_transport_required | 缺失 | 缺失 | 缺失 | True |
| airport_integrated_conversion.methanol_intermediate_ratio | 缺失 | 缺失 | 缺失 | 1.2 |
| airport_integrated_conversion.name | 缺失 | 缺失 | 缺失 | E-CRM+TRM MTJ航煤生产（机场集成） |
| airport_integrated_conversion.ng_consumption_ratio | 缺失 | 缺失 | 缺失 | 0.8 |
| airport_integrated_conversion.suitable_locations | 缺失 | 缺失 | 缺失 | ["airport"] |
| airport_integrated_conversion.technology_type | 缺失 | 缺失 | 缺失 | E-CRM+TRM |
| airport_integrated_conversion.transport_mode | 缺失 | 缺失 | 缺失 | airport_integrated |
| complexity_factors.airport_integrated_conversion | 缺失 | 缺失 | 缺失 | 1.0 |
| complexity_factors.green_h2_co2_to_saf | 1.2 | 1.2 | 1.2 | 缺失 |
| complexity_factors.lng_terminal_conversion | 缺失 | 缺失 | 缺失 | 1.0 |
| complexity_factors.lng_to_hplant_conversion | 缺失 | 缺失 | 缺失 | 1.0 |
| complexity_factors.pipeline_direct_conversion | 缺失 | 缺失 | 缺失 | 1.0 |
| green_h2_co2_to_saf.catalyst_cost_yuan_per_kg_saf | 0.12 | 0.12 | 0.12 | 缺失 |
| green_h2_co2_to_saf.catalyst_type | Iron-based | Iron-based | Iron-based | 缺失 |
| green_h2_co2_to_saf.co2_consumption_ratio | 3.0 | 3.0 | 3.0 | 缺失 |
| green_h2_co2_to_saf.co2_emission_factor | -2.5 | -2.5 | -2.5 | 缺失 |
| green_h2_co2_to_saf.efficiency | 0.6 | 0.6 | 0.6 | 缺失 |
| green_h2_co2_to_saf.energy_consumption_kwh_per_kg_saf | 6.0 | 6.0 | 6.0 | 缺失 |
| green_h2_co2_to_saf.h2_consumption_ratio | 0.15 | 0.15 | 0.15 | 缺失 |
| green_h2_co2_to_saf.heat_integration_efficiency | 0.7 | 0.7 | 0.7 | 缺失 |
| green_h2_co2_to_saf.hydrogen_transport_required | True | True | True | 缺失 |
| green_h2_co2_to_saf.methanol_intermediate_ratio | 缺失 | 1.5625 | 3.125 | 缺失 |
| green_h2_co2_to_saf.methanol_to_saf_ratio | 缺失 | 0.64 | 0.64 | 缺失 |
| green_h2_co2_to_saf.name | 绿氢+CO₂费托合成制SAF | 绿氢+CO₂费托合成制SAF | 绿氢+CO₂费托合成制SAF | 缺失 |
| green_h2_co2_to_saf.process_mode | one_step | 缺失 | 缺失 | 缺失 |
| green_h2_co2_to_saf.reactor_pressure_mpa | 3.0 | 3.0 | 3.0 | 缺失 |
| green_h2_co2_to_saf.reactor_temperature_celsius | 250 | 250 | 250 | 缺失 |
| green_h2_co2_to_saf.suitable_locations | ["solar_plant", "wind_farm", "airport", "lng_terminal"] | ["solar_plant", "wind_farm", "airport"] | ["solar_plant", "wind_farm", "airport", "co2_capture"] | 缺失 |
| green_h2_co2_to_saf.technology_type | GreenH2_CO2_FT | GreenH2_CO2_FT | GreenH2_CO2_FT | 缺失 |
| green_h2_co2_to_saf.transport_mode | renewable_h2_pipeline | renewable_h2_pipeline | renewable_h2_pipeline | 缺失 |
| lng_terminal_conversion.efficiency | 缺失 | 缺失 | 缺失 | 0.85 |
| lng_terminal_conversion.h2_consumption_ratio | 缺失 | 缺失 | 缺失 | 0.12 |
| lng_terminal_conversion.hydrogen_transport_required | 缺失 | 缺失 | 缺失 | True |
| lng_terminal_conversion.methanol_intermediate_ratio | 缺失 | 缺失 | 缺失 | 1.2 |
| lng_terminal_conversion.name | 缺失 | 缺失 | 缺失 | E-CRM+TRM MTJ航煤生产（LNG接收站） |
| lng_terminal_conversion.ng_consumption_ratio | 缺失 | 缺失 | 缺失 | 0.8 |
| lng_terminal_conversion.suitable_locations | 缺失 | 缺失 | 缺失 | ["lng_terminal"] |
| lng_terminal_conversion.technology_type | 缺失 | 缺失 | 缺失 | E-CRM+TRM |
| lng_terminal_conversion.transport_mode | 缺失 | 缺失 | 缺失 | lng_port_supply |
| lng_to_hplant_conversion.efficiency | 缺失 | 缺失 | 缺失 | 0.85 |
| lng_to_hplant_conversion.h2_consumption_ratio | 缺失 | 缺失 | 缺失 | 0.12 |
| lng_to_hplant_conversion.hydrogen_transport_required | 缺失 | 缺失 | 缺失 | False |
| lng_to_hplant_conversion.methanol_intermediate_ratio | 缺失 | 缺失 | 缺失 | 1.2 |
| lng_to_hplant_conversion.name | 缺失 | 缺失 | 缺失 | E-CRM+TRM MTJ航煤生产（LNG转运+可再生能源站） |
| lng_to_hplant_conversion.ng_consumption_ratio | 缺失 | 缺失 | 缺失 | 0.8 |
| lng_to_hplant_conversion.suitable_locations | 缺失 | 缺失 | 缺失 | ["solar_plant", "wind_farm"] |
| lng_to_hplant_conversion.technology_type | 缺失 | 缺失 | 缺失 | E-CRM+TRM |
| lng_to_hplant_conversion.transport_mode | 缺失 | 缺失 | 缺失 | lng_transfer |
| pipeline_direct_conversion.efficiency | 缺失 | 缺失 | 缺失 | 0.85 |
| pipeline_direct_conversion.h2_consumption_ratio | 缺失 | 缺失 | 缺失 | 0.12 |
| pipeline_direct_conversion.hydrogen_transport_required | 缺失 | 缺失 | 缺失 | False |
| pipeline_direct_conversion.methanol_intermediate_ratio | 缺失 | 缺失 | 缺失 | 1.2 |
| pipeline_direct_conversion.name | 缺失 | 缺失 | 缺失 | E-CRM+TRM MTJ航煤生产（在可再生能源站） |
| pipeline_direct_conversion.ng_consumption_ratio | 缺失 | 缺失 | 缺失 | 0.8 |
| pipeline_direct_conversion.suitable_locations | 缺失 | 缺失 | 缺失 | ["solar_plant", "wind_farm"] |
| pipeline_direct_conversion.technology_type | 缺失 | 缺失 | 缺失 | E-CRM+TRM |
| pipeline_direct_conversion.transport_mode | 缺失 | 缺失 | 缺失 | pipeline_direct |

## 运输约束（transport_constraints）

| 参数键 | 煤+绿氢SAF | DAC氢SAF | 绿氢供应链 | 天然气供应链 |
| --- | --- | --- | --- | --- |
| co2_truck_transport.max_trucks_per_day | 25 | 25 | 25 | 缺失 |
| co2_truck_transport.truck_capacity_ton | 20 | 20 | 20 | 缺失 |
| h2_truck_transport.max_trucks_per_day | 15 | 15 | 15 | 缺失 |
| h2_truck_transport.truck_capacity_kg | 500 | 500 | 500 | 缺失 |
| ng_truck_transport.max_trucks_per_day | 缺失 | 缺失 | 缺失 | 20 |
| ng_truck_transport.truck_capacity_m3 | 缺失 | 缺失 | 缺失 | 1200 |

## 运输方式（transport_modes）

| 参数键 | 煤+绿氢SAF | DAC氢SAF | 绿氢供应链 | 天然气供应链 |
| --- | --- | --- | --- | --- |
| airport_integrated.cost_yuan_per_kg | 5.0 | 5.0 | 5.0 | 缺失 |
| airport_integrated.cost_yuan_per_mcm_km | 缺失 | 缺失 | 缺失 | 5.0 |
| airport_integrated.description | 在机场就近建设绿氢+CO₂制SAF设施 | 在机场就近建设绿氢+CO₂制SAF设施 | 在机场就近建设绿氢+CO₂制SAF设施 | 在机场就近建设生产设施，多种来源供气 |
| airport_integrated.distance_limit_km | 100 | 100 | 100 | 500 |
| airport_integrated.suitable_sources | ["renewable_plant", "co2_capture_site"] | ["renewable_plant", "co2_capture_site"] | ["renewable_plant", "co2_capture_site"] | ["ng_pipeline"] |
| co2_pipeline_transport.capacity_factor | 0.95 | 0.95 | 0.95 | 缺失 |
| co2_pipeline_transport.description | 从CO₂捕获源管道输送至SAF设施 | 从CO₂捕获源管道输送至SAF设施 | 从CO₂捕获源管道输送至SAF设施 | 缺失 |
| co2_pipeline_transport.distance_limit_km | 500 | 500 | 500 | 缺失 |
| co2_pipeline_transport.name | CO₂管道运输 | CO₂管道运输 | CO₂管道运输 | 缺失 |
| co2_pipeline_transport.suitable_sources | ["co2_capture_site"] | ["co2_capture_site"] | ["co2_capture_site"] | 缺失 |
| co2_truck_transport.capacity_factor | 0.85 | 0.85 | 0.85 | 缺失 |
| co2_truck_transport.cost_yuan_per_ton_km | 0.8 | 0.8 | 0.8 | 缺失 |
| co2_truck_transport.description | CO₂罐车运输 | CO₂罐车运输 | CO₂罐车运输 | 缺失 |
| co2_truck_transport.distance_limit_km | 300 | 300 | 300 | 缺失 |
| co2_truck_transport.name | CO₂罐车运输 | CO₂罐车运输 | CO₂罐车运输 | 缺失 |
| co2_truck_transport.suitable_sources | ["co2_capture_site"] | ["co2_capture_site"] | ["co2_capture_site"] | 缺失 |
| h2_truck_transport.capacity_factor | 0.8 | 0.8 | 0.8 | 缺失 |
| h2_truck_transport.cost_yuan_per_kg_km | 2.0 | 2.0 | 2.0 | 缺失 |
| h2_truck_transport.description | 氢气罐车运输 | 氢气罐车运输 | 氢气罐车运输 | 缺失 |
| h2_truck_transport.distance_limit_km | 200 | 200 | 200 | 缺失 |
| h2_truck_transport.name | 氢气罐车运输 | 氢气罐车运输 | 氢气罐车运输 | 缺失 |
| h2_truck_transport.suitable_sources | ["renewable_plant", "electrolyzer_station"] | ["renewable_plant", "electrolyzer_station"] | ["renewable_plant", "electrolyzer_station"] | 缺失 |
| lng_port_supply.capacity_factor | 缺失 | 缺失 | 缺失 | 0.92 |
| lng_port_supply.description | 缺失 | 缺失 | 缺失 | 从LNG接收站直接供应天然气 |
| lng_port_supply.distance_limit_km | 缺失 | 缺失 | 缺失 | 800 |
| lng_port_supply.name | 缺失 | 缺失 | 缺失 | LNG接收站供应 |
| lng_port_supply.suitable_sources | 缺失 | 缺失 | 缺失 | ["lng_terminal"] |
| lng_transfer.capacity_factor | 缺失 | 缺失 | 缺失 | 0.85 |
| lng_transfer.description | 缺失 | 缺失 | 缺失 | LNG接收站到生产基地的多式联运 |
| lng_transfer.distance_limit_km | 缺失 | 缺失 | 缺失 | 1200 |
| lng_transfer.name | 缺失 | 缺失 | 缺失 | LNG转运 |
| lng_transfer.suitable_sources | 缺失 | 缺失 | 缺失 | ["lng_terminal"] |
| pipeline_direct.capacity_factor | 缺失 | 缺失 | 缺失 | 0.95 |
| pipeline_direct.description | 缺失 | 缺失 | 缺失 | 天然气从管道经罐车运输到可再生能源站，就地制氢制备MTJ航煤，氢气运输成本为0 |
| pipeline_direct.distance_limit_km | 缺失 | 缺失 | 缺失 | 1500 |
| pipeline_direct.hydrogen_transport_cost | 缺失 | 缺失 | 缺失 | 0 |
| pipeline_direct.name | 缺失 | 缺失 | 缺失 | 管段直供 |
| pipeline_direct.suitable_sources | 缺失 | 缺失 | 缺失 | ["ng_pipeline"] |
| renewable_h2_pipeline.capacity_factor | 0.92 | 0.92 | 0.92 | 缺失 |
| renewable_h2_pipeline.description | 可再生能源发电厂电解制氢，管道输送至SAF设施 | 可再生能源发电厂电解制氢，管道输送至SAF设施 | 可再生能源发电厂电解制氢，管道输送至SAF设施 | 缺失 |
| renewable_h2_pipeline.distance_limit_km | 500 | 500 | 500 | 缺失 |
| renewable_h2_pipeline.name | 可再生能源氢气管道 | 可再生能源氢气管道 | 可再生能源氢气管道 | 缺失 |
| renewable_h2_pipeline.suitable_sources | ["renewable_plant"] | ["renewable_plant"] | ["renewable_plant"] | 缺失 |

## 统一成本（unified_costs）

| 参数键 | 煤+绿氢SAF | DAC氢SAF | 绿氢供应链 | 天然气供应链 |
| --- | --- | --- | --- | --- |
| co2_storage.equipment_cost_yuan_per_kg | 缺失 | 5 | 缺失 | 缺失 |
| co2_storage.handling_cost_yuan_per_kg | 缺失 | 0.05 | 缺失 | 缺失 |
| co2_storage.initial_inventory_yuan_per_kg | 缺失 | 0 | 缺失 | 缺失 |
| co2_storage.operation_cost_yuan_per_kg_hour | 缺失 | 0.000208 | 缺失 | 缺失 |
| co2_transport.pipeline.transport_cost_function.data_points | 缺失 | list(len=5), item=list | 缺失 | 缺失 |
| co2_transport.pipeline.transport_cost_function.description | 缺失 | 基于CO₂管道输送成本曲线 | 缺失 | 缺失 |
| co2_transport.pipeline.transport_cost_function.function_type | 缺失 | piecewise_linear | 缺失 | 缺失 |
| co2_transport.pipeline.transport_cost_function.notes | 缺失 | 成本函数已包含以下所有费用： / - 管道建设投资摊销 (Pipeline construction amortization) / - 压缩机站投资和运营 (Compressor station CAPEX & OPEX) / - ... | 缺失 | 缺失 |
| co2_transport.pipeline.transport_cost_function.unit | 缺失 | yuan_per_kg_co2_per_100km | 缺失 | 缺失 |
| co2_transport.pipeline.transport_cost_yuan_per_kg_km | 缺失 | 0.0001 | 缺失 | 缺失 |
| production.h2_production_cost_yuan_per_kg | 25.0 | 25.0 | 25.0 | 缺失 |
| production.hydrogen_internal_cost_yuan_per_kg | 缺失 | 缺失 | 缺失 | 0 |
| production.natural_gas_processing_cost_yuan_per_m3 | 缺失 | 缺失 | 缺失 | 0.1 |
| production.saf_synthesis_cost_yuan_per_kg | 8.0 | 8.0 | 8.0 | 缺失 |
| raw_materials.co2_capture_base_cost_yuan_per_ton | 280 | 280 | 280 | 缺失 |
| raw_materials.hydrogen_market_price_yuan_per_kg | 缺失 | 缺失 | 缺失 | 30 |
| raw_materials.natural_gas_base_price_yuan_per_m3 | 缺失 | 缺失 | 缺失 | 4.2 |
| raw_materials.renewable_electricity_base_price_yuan_per_kwh | 0.35 | 0.35 | 0.35 | 缺失 |
| storage.facility_investment_yuan_per_kg | 2000 | 2000 | 2000 | 1500 |
| storage.facility_operation_yuan_per_kg_year | 25 | 25 | 25 | 20 |
| storage.hydrogen_equipment_cost_yuan_per_kg | 缺失 | 缺失 | 缺失 | 20 |
| storage.mtj_equipment_cost_yuan_per_kg | 缺失 | 缺失 | 缺失 | 10 |
| storage.saf_equipment_cost_yuan_per_kg | 12 | 12 | 12 | 缺失 |
