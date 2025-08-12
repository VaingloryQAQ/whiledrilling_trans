"""规则学习命令行工具"""

import argparse
import sys
from pathlib import Path
import json

from .rule_learner import RuleLearner
from .ml_classifier import MLClassifier, HybridClassifier

def main():
    parser = argparse.ArgumentParser(description='从CSV数据学习分类规则')
    parser.add_argument('--csv-dir', type=Path, default=Path('data/api_csv'),
                       help='CSV文件目录 (默认: data/api_csv)')
    parser.add_argument('--output-dir', type=Path, default=Path('data/learned_rules'),
                       help='输出目录 (默认: data/learned_rules)')
    parser.add_argument('--train-ml', action='store_true',
                       help='训练机器学习模型')
    parser.add_argument('--ml-model-path', type=Path, default=Path('data/models/ml_classifier.pkl'),
                       help='ML模型保存路径 (默认: data/models/ml_classifier.pkl)')
    parser.add_argument('--evaluate', action='store_true',
                       help='评估学习到的规则')
    parser.add_argument('--apply-enhanced-rules', action='store_true',
                       help='应用增强规则到现有系统')
    
    args = parser.parse_args()
    
    # 检查CSV目录是否存在
    if not args.csv_dir.exists():
        print(f"错误: CSV目录不存在: {args.csv_dir}")
        sys.exit(1)
    
    # 创建输出目录
    args.output_dir.mkdir(parents=True, exist_ok=True)
    
    print("=== 钻井图像分类规则学习工具 ===")
    print(f"CSV目录: {args.csv_dir}")
    print(f"输出目录: {args.output_dir}")
    print()
    
    # 1. 学习规则
    print("1. 开始学习规则...")
    learner = RuleLearner(args.csv_dir, args.output_dir)
    learning_result = learner.learn_from_csv_data()
    
    print(f"✓ 规则学习完成")
    print(f"  - 分析了 {len(learning_result['analysis']['analysis_stats'])} 个CSV文件")
    print(f"  - 生成了 {len(learning_result['classification_rules']['categories'])} 个分类规则")
    print(f"  - 发现了 {len(learning_result['patterns']['special_tokens'])} 个特殊标记")
    print()
    
    # 2. 训练ML模型（可选）
    if args.train_ml:
        print("2. 训练机器学习模型...")
        ml_model_path = args.ml_model_path
        ml_model_path.parent.mkdir(parents=True, exist_ok=True)
        
        ml_classifier = MLClassifier(ml_model_path)
        training_result = ml_classifier.train(args.csv_dir)
        
        print(f"✓ ML模型训练完成")
        print(f"  - 准确率: {training_result['accuracy']:.3f}")
        print(f"  - 训练样本: {training_result['training_samples']}")
        print(f"  - 测试样本: {training_result['test_samples']}")
        print(f"  - 特征数量: {training_result['feature_count']}")
        print()
        
        # 保存训练结果
        with open(args.output_dir / 'ml_training_result.json', 'w', encoding='utf-8') as f:
            json.dump(training_result, f, ensure_ascii=False, indent=2)
    
    # 3. 评估规则（可选）
    if args.evaluate:
        print("3. 评估学习到的规则...")
        evaluation_result = learner.evaluate_learned_rules()
        
        print(f"✓ 规则评估完成")
        print(f"  - 测试文件数: {evaluation_result['test_files_count']}")
        print(f"  - 规则引擎成功率: {evaluation_result['performance']['rule_based']['success_rate']:.3f}")
        if 'ml_based' in evaluation_result['performance']:
            print(f"  - ML模型成功率: {evaluation_result['performance']['ml_based']['success_rate']:.3f}")
        print()
        
        # 保存评估结果
        with open(args.output_dir / 'evaluation_result.json', 'w', encoding='utf-8') as f:
            json.dump(evaluation_result, f, ensure_ascii=False, indent=2)
    
    # 4. 应用增强规则（可选）
    if args.apply_enhanced_rules:
        print("4. 应用增强规则...")
        enhanced_rules_path = args.output_dir / 'enhanced_rules.yaml'
        
        if enhanced_rules_path.exists():
            # 备份现有规则
            current_rules_path = Path('config/rules.yaml')
            if current_rules_path.exists():
                backup_path = Path('config/rules.yaml.backup')
                import shutil
                shutil.copy2(current_rules_path, backup_path)
                print(f"  - 已备份现有规则到: {backup_path}")
            
            # 应用新规则
            import shutil
            shutil.copy2(enhanced_rules_path, current_rules_path)
            print(f"  - 已应用增强规则到: {current_rules_path}")
        else:
            print(f"  - 错误: 增强规则文件不存在: {enhanced_rules_path}")
        print()
    
    # 5. 生成报告
    print("5. 生成学习报告...")
    generate_learning_report(learning_result, args.output_dir)
    print(f"✓ 报告已生成: {args.output_dir / 'learning_report.md'}")
    
    print("\n=== 规则学习完成 ===")
    print(f"所有结果已保存到: {args.output_dir}")
    
    # 显示关键建议
    if learning_result['suggestions']:
        print("\n关键建议:")
        for suggestion in learning_result['suggestions']:
            if suggestion['priority'] == 'high':
                print(f"  🔴 {suggestion['message']}")
            elif suggestion['priority'] == 'medium':
                print(f"  🟡 {suggestion['message']}")
            else:
                print(f"  🟢 {suggestion['message']}")


def generate_learning_report(learning_result: dict, output_dir: Path):
    """生成学习报告"""
    report_content = """# 钻井图像分类规则学习报告

## 概述

本报告基于CSV数据分析结果，自动学习了钻井图像分类规则。

## 数据统计

### CSV文件分析
"""
    
    # 添加CSV分析统计
    for api_source, stats in learning_result['analysis']['analysis_stats'].items():
        report_content += f"""
#### {api_source}
- 总文件数: {stats['total_files']}
- 唯一井名数: {stats['unique_wells']}
- 样品类型分布: {stats['sample_type_distribution']}
- 类别分布: {stats['category_distribution']}
"""
    
    # 添加模式分析
    patterns = learning_result['patterns']
    report_content += f"""
## 模式分析

### 井名模式
发现 {len(patterns['well_patterns'])} 种井名模式

### 深度模式
发现 {len(patterns['depth_patterns'])} 种深度模式

### 特殊标记
发现 {len(patterns['special_tokens'])} 种特殊标记: {', '.join(patterns['special_tokens'])}

## 学习到的规则

### 分类规则
"""
    
    for rule in learning_result['classification_rules']['categories']:
        report_content += f"""
#### {rule['name']}
- 模式: {rule['mode']}
- 优先级: {rule['priority']}
- 必需条件: {rule['require_all']}
- 置信度: {rule.get('confidence', 0):.3f}
"""
    
    # 添加建议
    if learning_result['suggestions']:
        report_content += """
## 规则建议

"""
        for suggestion in learning_result['suggestions']:
            priority_icon = {
                'high': '🔴',
                'medium': '🟡',
                'low': '🟢'
            }.get(suggestion['priority'], '⚪')
            
            report_content += f"- {priority_icon} **{suggestion['type']}**: {suggestion['message']}\n"
    
    # 保存报告
    with open(output_dir / 'learning_report.md', 'w', encoding='utf-8') as f:
        f.write(report_content)


if __name__ == '__main__':
    main()
