#!/usr/bin/env python3
"""查看详细分析结果"""

import json
import sys
from pathlib import Path

def view_analysis_summary(analysis_dir: Path):
    """查看分析结果摘要"""
    print("=== 钻井图像数据详细分析结果 ===")
    print(f"分析目录: {analysis_dir}")
    print()
    
    # 1. 井名分析
    well_file = analysis_dir / 'well_pattern_analysis.json'
    if well_file.exists():
        with open(well_file, 'r', encoding='utf-8') as f:
            well_data = json.load(f)
        
        print("📊 井名分析:")
        print(f"  总井数: {well_data['total_wells']}")
        print(f"  井名前缀数: {well_data['well_statistics']['prefix_count']}")
        print(f"  最常见前缀: {well_data['well_statistics']['most_common_prefix'][0]} ({well_data['well_statistics']['most_common_prefix'][1]}个)")
        print(f"  平均每前缀井数: {well_data['well_statistics']['avg_wells_per_prefix']:.1f}")
        
        print("  井名前缀分布:")
        for prefix, count in sorted(well_data['well_categories'].items(), key=lambda x: x[1], reverse=True):
            print(f"    {prefix}: {count}个")
        print()
    
    # 2. 深度分析
    depth_file = analysis_dir / 'depth_pattern_analysis.json'
    if depth_file.exists():
        with open(depth_file, 'r', encoding='utf-8') as f:
            depth_data = json.load(f)
        
        print("📊 深度模式分析:")
        print(f"  总深度模式数: {depth_data['total_patterns']}")
        
        pattern_types = depth_data['pattern_types']
        print(f"  单深度模式: {pattern_types['single_depth']['count']}个")
        print(f"  深度区间模式: {pattern_types['range_depth']['count']}个")
        print(f"  其他模式: {pattern_types['other_patterns']['count']}个")
        
        if 'depth_statistics' in depth_data:
            stats = depth_data['depth_statistics']
            print(f"  深度范围: {stats['min_depth']:.1f}m - {stats['max_depth']:.1f}m")
            print(f"  平均深度: {stats['avg_depth']:.1f}m")
            
            dist = stats['depth_distribution']
            print("  深度分布:")
            print(f"    浅层(0-1000m): {dist['shallow_0_1000']}个")
            print(f"    中层(1000-3000m): {dist['medium_1000_3000']}个")
            print(f"    深层(3000-5000m): {dist['deep_3000_5000']}个")
            print(f"    超深层(5000m+): {dist['very_deep_5000+']}个")
        print()
    
    # 3. 异常分析
    anomaly_file = analysis_dir / 'anomaly_analysis.json'
    if anomaly_file.exists():
        with open(anomaly_file, 'r', encoding='utf-8') as f:
            anomaly_data = json.load(f)
        
        print("🚨 异常分析:")
        print(f"  总异常数: {anomaly_data['total_anomalies']}")
        
        print("  异常类型分布:")
        for anomaly_type, count in sorted(anomaly_data['anomaly_types'].items(), key=lambda x: x[1], reverse=True):
            print(f"    {anomaly_type}: {count}个")
        
        if anomaly_data['anomalies']:
            print("  前5个严重异常:")
            for i, anomaly in enumerate(anomaly_data['anomalies'][:5]):
                print(f"    {i+1}. {anomaly['filename']}")
                print(f"       异常: {', '.join(anomaly['anomalies'])} (严重度: {anomaly['severity']})")
        print()
    
    # 4. 文件扩展名分析
    ext_file = analysis_dir / 'extension_analysis.json'
    if ext_file.exists():
        with open(ext_file, 'r', encoding='utf-8') as f:
            ext_data = json.load(f)
        
        print("📁 文件扩展名分析:")
        print(f"  总扩展名类型: {ext_data['total_extensions']}")
        print("  扩展名分布:")
        for ext, count in sorted(ext_data['extension_statistics'].items(), key=lambda x: x[1], reverse=True):
            print(f"    .{ext}: {count}个")
        print()
    
    # 5. 特殊标记分析
    token_file = analysis_dir / 'special_token_analysis.json'
    if token_file.exists():
        with open(token_file, 'r', encoding='utf-8') as f:
            token_data = json.load(f)
        
        print("🏷️  特殊标记分析:")
        print(f"  总特殊标记数: {token_data['total_tokens']}")
        
        for category, tokens in token_data['token_categories'].items():
            print(f"  {category}: {', '.join(tokens)}")
        print()
    
    # 6. 分类规则分析
    class_file = analysis_dir / 'classification_analysis.json'
    if class_file.exists():
        with open(class_file, 'r', encoding='utf-8') as f:
            class_data = json.load(f)
        
        print("🔍 分类规则分析:")
        print(f"  总规则数: {class_data['total_rules']}")
        
        print("  按优先级分组:")
        for priority in sorted(class_data['rules_by_priority'].keys(), reverse=True):
            rules = class_data['rules_by_priority'][priority]
            print(f"    优先级{priority}: {', '.join(rules)}")
        
        print("  按置信度分组:")
        for confidence_range, rules in class_data['rules_by_confidence'].items():
            print(f"    {confidence_range}: {', '.join(rules)}")
        print()

def view_specific_analysis(analysis_dir: Path, analysis_type: str):
    """查看特定类型的详细分析"""
    print(f"=== {analysis_type} 详细分析 ===")
    
    if analysis_type == 'wells':
        # 查看井名列表
        well_file = analysis_dir / 'well_names.txt'
        if well_file.exists():
            with open(well_file, 'r', encoding='utf-8') as f:
                wells = f.readlines()
            
            print(f"总井数: {len(wells)}")
            print("前20个井名:")
            for i, well in enumerate(wells[:20]):
                print(f"  {i+1:2d}. {well.strip()}")
            
            if len(wells) > 20:
                print(f"  ... 还有 {len(wells) - 20} 个井名")
    
    elif analysis_type == 'depths':
        # 查看深度模式
        depth_file = analysis_dir / 'depth_patterns.txt'
        if depth_file.exists():
            with open(depth_file, 'r', encoding='utf-8') as f:
                depths = f.readlines()
            
            print(f"总深度模式数: {len(depths)}")
            print("前20个深度模式:")
            for i, depth in enumerate(depths[:20]):
                print(f"  {i+1:2d}. {depth.strip()}")
            
            if len(depths) > 20:
                print(f"  ... 还有 {len(depths) - 20} 个深度模式")
    
    elif analysis_type == 'anomalies':
        # 查看异常文件名
        anomaly_file = analysis_dir / 'anomaly_filenames.txt'
        if anomaly_file.exists():
            with open(anomaly_file, 'r', encoding='utf-8') as f:
                anomalies = f.readlines()
            
            print(f"总异常数: {len(anomalies)}")
            print("前20个异常文件名:")
            for i, anomaly in enumerate(anomalies[:20]):
                print(f"  {i+1:2d}. {anomaly.strip()}")
            
            if len(anomalies) > 20:
                print(f"  ... 还有 {len(anomalies) - 20} 个异常")

def main():
    if len(sys.argv) < 2:
        print("用法: python view_analysis_results.py <分析目录> [分析类型]")
        print("分析类型: summary, wells, depths, anomalies")
        sys.exit(1)
    
    analysis_dir = Path(sys.argv[1])
    if not analysis_dir.exists():
        print(f"错误: 分析目录不存在: {analysis_dir}")
        sys.exit(1)
    
    if len(sys.argv) > 2:
        analysis_type = sys.argv[2]
        if analysis_type == 'summary':
            view_analysis_summary(analysis_dir)
        else:
            view_specific_analysis(analysis_dir, analysis_type)
    else:
        view_analysis_summary(analysis_dir)

if __name__ == '__main__':
    main()
