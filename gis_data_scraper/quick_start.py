#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
快速启动脚本 - 中国能源基础设施GIS数据爬取器
Quick Start Script for China Energy Infrastructure GIS Data Scraper

作者: AI Assistant
日期: 2025-08-03
"""

from advanced_china_energy_gis_scraper import AdvancedChinaEnergyGISScraper
import time

def quick_scrape_all():
    """快速爬取所有数据集"""
    print("🚀 启动高级GIS数据爬取器...")
    
    # 创建爬取器
    scraper = AdvancedChinaEnergyGISScraper()
    
    # 显示配置信息
    print(f"\n📊 配置了 {len(scraper.feature_servers)} 个数据集:")
    categories = {
        '电力基础设施': ['nuclear_power_plants', 'coal_power_plants', 'gas_power_plants'],
        '可再生能源': ['solar_power_plants', 'wind_power_plants'],
        '石油天然气': ['lng_terminals', 'oil_ports', 'oil_refineries', 'oil_storage', 'gas_storage'],
        '管道基础设施': ['natural_gas_pipelines', 'crude_pipelines', 'refined_product_pipelines', 'hydrogen_pipelines'],
        '新兴能源技术': ['hydrogen_facilities', 'ccs_projects', 'ev_battery_factories'],
        '矿产和地理': ['mining_properties', 'china_boundaries', 'urban_areas']
    }
    
    for category, datasets in categories.items():
        print(f"\n  {category}:")
        for dataset in datasets:
            if dataset in scraper.feature_servers:
                print(f"    • {scraper.feature_servers[dataset]['description']}")
    
    print(f"\n📁 输出目录: {scraper.output_dir}")
    print("\n⏳ 开始爬取所有数据集...")
    
    # 执行爬取
    start_time = time.time()
    results = scraper.scrape_all_datasets()
    elapsed = time.time() - start_time
    
    # 统计结果
    successful = sum(1 for success in results.values() if success)
    total = len(results)
    
    print(f"\n🎉 爬取完成！")
    print(f"   耗时: {elapsed:.1f} 秒")
    print(f"   成功: {successful}/{total} 个数据集")
    print(f"   成功率: {successful/total*100:.1f}%")
    
    # 生成报告
    print("\n📝 生成总结报告...")
    scraper.generate_summary_report()
    
    return results

def quick_test_connections():
    """快速测试所有服务连接"""
    print("🔍 测试服务连接...")
    
    scraper = AdvancedChinaEnergyGISScraper()
    
    print(f"\n测试 {len(scraper.feature_servers)} 个服务:")
    
    working = 0
    total = len(scraper.feature_servers)
    
    for name, config in scraper.feature_servers.items():
        print(f"  测试 {name}...", end="")
        if scraper.test_service_connection(config['url']):
            print(" ✅")
            working += 1
        else:
            print(" ❌")
    
    print(f"\n📊 连接测试结果:")
    print(f"   正常: {working}/{total} 个服务")
    print(f"   成功率: {working/total*100:.1f}%")
    
    return working == total

if __name__ == "__main__":
    print("=" * 50)
    print("🌟 中国能源基础设施GIS数据爬取器")
    print("   China Energy Infrastructure GIS Scraper")
    print("=" * 50)
    
    print("\n请选择操作:")
    print("1. 🚀 立即爬取所有数据集")
    print("2. 🔍 测试服务连接")
    print("3. 📋 查看数据集列表")
    
    choice = input("\n请输入选择 (1-3): ").strip()
    
    if choice == '1':
        quick_scrape_all()
    elif choice == '2':
        if quick_test_connections():
            print("\n✅ 所有服务连接正常，可以开始爬取！")
        else:
            print("\n⚠️  部分服务连接异常，请检查网络或稍后重试")
    elif choice == '3':
        scraper = AdvancedChinaEnergyGISScraper()
        print(f"\n📋 配置的数据集 ({len(scraper.feature_servers)} 个):")
        for i, (name, config) in enumerate(scraper.feature_servers.items(), 1):
            print(f"  {i:2d}. {config['description']}")
            print(f"      数据集名: {name}")
            print(f"      几何类型: {config['geometry_type']}")
            print()
    else:
        print("❌ 无效选择")
    
    print("\n👋 程序结束")
