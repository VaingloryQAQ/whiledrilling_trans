"""智能井名学习器 - 从已识别的井名中学习模式并应用到其他井名"""

import re
import json
from pathlib import Path
from typing import Dict, List, Set, Tuple, Any, Optional
from collections import Counter, defaultdict
import csv

class WellNameLearner:
    """智能井名学习器"""
    
    def __init__(self):
        self.known_wells = set()  # 已知的井名（带"井"字）
        self.well_patterns = {}   # 井名模式
        self.prefix_patterns = {} # 前缀模式
        self.suffix_patterns = {} # 后缀模式
        self.well_mapping = {}    # 井名映射（不带"井"字 -> 带"井"字）
        
    def learn_from_csv_data(self, csv_dir: Path) -> Dict[str, Any]:
        """从CSV数据中学习井名模式"""
        print("开始学习井名模式...")
        
        # 1. 收集所有带"井"字的井名
        self._collect_known_wells(csv_dir)
        
        # 2. 分析井名模式
        self._analyze_well_patterns()
        
        # 3. 学习前缀和后缀模式
        self._learn_prefix_suffix_patterns()
        
        # 4. 生成井名映射规则
        self._generate_well_mapping_rules()
        
        # 5. 验证学习结果
        validation_results = self._validate_learning_results(csv_dir)
        
        return {
            'known_wells': list(self.known_wells),
            'well_patterns': self.well_patterns,
            'prefix_patterns': self.prefix_patterns,
            'suffix_patterns': self.suffix_patterns,
            'well_mapping': self.well_mapping,
            'validation': validation_results
        }
    
    def _collect_known_wells(self, csv_dir: Path):
        """收集所有带"井"字的井名"""
        for csv_file in csv_dir.glob('*.csv'):
            with open(csv_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    filename = row.get('graphic_doc_name', '')
                    if filename:
                        # 提取带"井"字的井名
                        well_matches = re.findall(r'([A-Za-z0-9\-]+井)', filename)
                        for well in well_matches:
                            self.known_wells.add(well)
        
        print(f"收集到 {len(self.known_wells)} 个已知井名")
    
    def _analyze_well_patterns(self):
        """分析井名模式"""
        patterns = {
            'prefix_patterns': Counter(),  # 前缀模式（如BZ、KL、SZ等）
            'number_patterns': Counter(),  # 数字模式
            'suffix_patterns': Counter(),  # 后缀模式（如H、Sa、d等）
            'separator_patterns': Counter(), # 分隔符模式（如-、_等）
            'length_distribution': Counter(), # 长度分布
            'structure_patterns': Counter()   # 结构模式
        }
        
        for well in self.known_wells:
            # 移除"井"字进行分析
            well_base = well.replace('井', '')
            
            # 分析前缀
            prefix_match = re.match(r'^([A-Z]{2,4})', well_base)
            if prefix_match:
                patterns['prefix_patterns'][prefix_match.group(1)] += 1
            
            # 分析数字模式
            numbers = re.findall(r'\d+', well_base)
            if numbers:
                number_pattern = '-'.join(numbers)
                patterns['number_patterns'][number_pattern] += 1
            
            # 分析后缀
            suffix_match = re.search(r'([A-Za-z]+)$', well_base)
            if suffix_match:
                patterns['suffix_patterns'][suffix_match.group(1)] += 1
            
            # 分析分隔符
            separators = re.findall(r'[^A-Za-z0-9]', well_base)
            if separators:
                separator_pattern = ''.join(separators)
                patterns['separator_patterns'][separator_pattern] += 1
            
            # 分析长度
            patterns['length_distribution'][len(well_base)] += 1
            
            # 分析结构模式
            structure = self._extract_structure_pattern(well_base)
            patterns['structure_patterns'][structure] += 1
        
        self.well_patterns = {k: dict(v) for k, v in patterns.items()}
    
    def _extract_structure_pattern(self, well_name: str) -> str:
        """提取井名结构模式"""
        # 将井名转换为结构模式
        # 例如：BZ26-6-B6H -> LLLNN-N-NLLL
        pattern = ''
        for char in well_name:
            if char.isalpha():
                if char.isupper():
                    pattern += 'L'  # 大写字母
                else:
                    pattern += 'l'  # 小写字母
            elif char.isdigit():
                pattern += 'N'  # 数字
            else:
                pattern += char  # 保持分隔符
        
        return pattern
    
    def _learn_prefix_suffix_patterns(self):
        """学习前缀和后缀模式"""
        prefix_stats = defaultdict(lambda: {'count': 0, 'examples': [], 'suffixes': Counter()})
        suffix_stats = defaultdict(lambda: {'count': 0, 'examples': [], 'prefixes': Counter()})
        
        for well in self.known_wells:
            well_base = well.replace('井', '')
            
            # 分析前缀
            prefix_match = re.match(r'^([A-Z]{2,4})', well_base)
            if prefix_match:
                prefix = prefix_match.group(1)
                prefix_stats[prefix]['count'] += 1
                prefix_stats[prefix]['examples'].append(well)
                
                # 分析该前缀下的后缀
                suffix_match = re.search(r'([A-Za-z]+)$', well_base)
                if suffix_match:
                    suffix = suffix_match.group(1)
                    prefix_stats[prefix]['suffixes'][suffix] += 1
            
            # 分析后缀
            suffix_match = re.search(r'([A-Za-z]+)$', well_base)
            if suffix_match:
                suffix = suffix_match.group(1)
                suffix_stats[suffix]['count'] += 1
                suffix_stats[suffix]['examples'].append(well)
                
                # 分析该后缀下的前缀
                prefix_match = re.match(r'^([A-Z]{2,4})', well_base)
                if prefix_match:
                    prefix = prefix_match.group(1)
                    suffix_stats[suffix]['prefixes'][prefix] += 1
        
        # 转换为可序列化的格式
        self.prefix_patterns = {}
        for prefix, stats in prefix_stats.items():
            self.prefix_patterns[prefix] = {
                'count': stats['count'],
                'examples': stats['examples'][:5],  # 只保留前5个例子
                'suffixes': dict(stats['suffixes'])
            }
        
        self.suffix_patterns = {}
        for suffix, stats in suffix_stats.items():
            self.suffix_patterns[suffix] = {
                'count': stats['count'],
                'examples': stats['examples'][:5],  # 只保留前5个例子
                'prefixes': dict(stats['prefixes'])
            }
    
    def _generate_well_mapping_rules(self):
        """生成井名映射规则"""
        # 基于学习到的模式，生成从不带"井"字到带"井"字的映射规则
        
        # 1. 直接映射：如果发现相同的井名（一个带"井"字，一个不带）
        direct_mappings = {}
        
        # 2. 模式映射：基于前缀和后缀模式进行映射
        pattern_mappings = {}
        
        # 3. 生成映射规则
        for well in self.known_wells:
            well_base = well.replace('井', '')
            
            # 直接映射
            direct_mappings[well_base] = well
            
            # 模式映射
            prefix_match = re.match(r'^([A-Z]{2,4})', well_base)
            if prefix_match:
                prefix = prefix_match.group(1)
                suffix_match = re.search(r'([A-Za-z]+)$', well_base)
                if suffix_match:
                    suffix = suffix_match.group(1)
                    pattern_key = f"{prefix}*{suffix}"
                    if pattern_key not in pattern_mappings:
                        pattern_mappings[pattern_key] = []
                    pattern_mappings[pattern_key].append(well)
        
        self.well_mapping = {
            'direct_mappings': direct_mappings,
            'pattern_mappings': pattern_mappings,
            'prefix_rules': self._generate_prefix_rules(),
            'suffix_rules': self._generate_suffix_rules()
        }
    
    def _generate_prefix_rules(self) -> Dict[str, Any]:
        """生成前缀规则"""
        rules = {}
        for prefix, stats in self.prefix_patterns.items():
            if stats['count'] >= 3:  # 至少出现3次才生成规则
                # 将suffixes转换为Counter对象以使用most_common
                suffixes_counter = Counter(stats['suffixes'])
                rules[prefix] = {
                    'confidence': min(stats['count'] / 10, 1.0),  # 置信度
                    'common_suffixes': [s for s, c in suffixes_counter.most_common(3)],
                    'examples': stats['examples']
                }
        return rules
    
    def _generate_suffix_rules(self) -> Dict[str, Any]:
        """生成后缀规则"""
        rules = {}
        for suffix, stats in self.suffix_patterns.items():
            if stats['count'] >= 3:  # 至少出现3次才生成规则
                # 将prefixes转换为Counter对象以使用most_common
                prefixes_counter = Counter(stats['prefixes'])
                rules[suffix] = {
                    'confidence': min(stats['count'] / 10, 1.0),  # 置信度
                    'common_prefixes': [p for p, c in prefixes_counter.most_common(3)],
                    'examples': stats['examples']
                }
        return rules
    
    def predict_well_name(self, filename: str) -> Tuple[Optional[str], float]:
        """预测井名"""
        if not filename:
            return None, 0.0
        
        # 1. 首先尝试直接匹配带"井"字的井名
        well_matches = re.findall(r'([A-Za-z0-9\-]+井)', filename)
        if well_matches:
            return well_matches[0], 1.0
        
        # 2. 尝试匹配不带"井"字的井名模式
        potential_wells = self._extract_potential_wells(filename)
        
        best_match = None
        best_confidence = 0.0
        
        for potential_well in potential_wells:
            confidence = self._calculate_well_confidence(potential_well)
            if confidence > best_confidence:
                best_match = potential_well
                best_confidence = confidence
        
        if best_match and best_confidence > 0.5:
            # 添加"井"字
            return best_match + "井", best_confidence
        
        return None, 0.0
    
    def _extract_potential_wells(self, filename: str) -> List[str]:
        """提取潜在的井名"""
        potential_wells = []
        
        # 移除文件扩展名
        name = re.sub(r'\.[a-zA-Z]+$', '', filename)
        
        # 查找符合井名模式的字符串
        # 模式：字母+数字+可能的字母后缀，用连字符分隔
        patterns = [
            r'[A-Z]{2,4}\d+(?:-\d+)*(?:-[A-Za-z0-9]+)*',  # 标准模式
            r'[A-Z]{2,4}\d+[A-Za-z0-9]*',  # 简化模式
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, name)
            potential_wells.extend(matches)
        
        return list(set(potential_wells))  # 去重
    
    def _calculate_well_confidence(self, potential_well: str) -> float:
        """计算井名置信度"""
        confidence = 0.0
        
        # 1. 直接映射匹配
        if potential_well in self.well_mapping['direct_mappings']:
            confidence += 0.8
        
        # 2. 前缀匹配
        prefix_match = re.match(r'^([A-Z]{2,4})', potential_well)
        if prefix_match:
            prefix = prefix_match.group(1)
            if prefix in self.well_mapping['prefix_rules']:
                confidence += 0.3
        
        # 3. 后缀匹配
        suffix_match = re.search(r'([A-Za-z]+)$', potential_well)
        if suffix_match:
            suffix = suffix_match.group(1)
            if suffix in self.well_mapping['suffix_rules']:
                confidence += 0.2
        
        # 4. 长度匹配
        well_length = len(potential_well)
        length_dist = self.well_patterns['length_distribution']
        if well_length in length_dist:
            max_count = max(length_dist.values())
            confidence += 0.1 * (length_dist[well_length] / max_count)
        
        # 5. 结构模式匹配
        structure = self._extract_structure_pattern(potential_well)
        structure_dist = self.well_patterns['structure_patterns']
        if structure in structure_dist:
            max_count = max(structure_dist.values())
            confidence += 0.1 * (structure_dist[structure] / max_count)
        
        return min(confidence, 1.0)
    
    def _validate_learning_results(self, csv_dir: Path) -> Dict[str, Any]:
        """验证学习结果"""
        validation_results = {
            'total_files': 0,
            'wells_with_well_char': 0,
            'wells_without_well_char': 0,
            'predicted_wells': 0,
            'prediction_accuracy': 0.0,
            'examples': []
        }
        
        all_filenames = []
        for csv_file in csv_dir.glob('*.csv'):
            with open(csv_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    filename = row.get('graphic_doc_name', '')
                    if filename:
                        all_filenames.append(filename)
        
        validation_results['total_files'] = len(all_filenames)
        
        # 随机选择一些文件进行验证
        import random
        sample_size = min(1000, len(all_filenames))
        sample_files = random.sample(all_filenames, sample_size)
        
        for filename in sample_files:
            # 检查是否包含"井"字
            has_well_char = bool(re.search(r'井', filename))
            if has_well_char:
                validation_results['wells_with_well_char'] += 1
            else:
                validation_results['wells_without_well_char'] += 1
                
                # 尝试预测井名
                predicted_well, confidence = self.predict_well_name(filename)
                if predicted_well:
                    validation_results['predicted_wells'] += 1
                    validation_results['examples'].append({
                        'filename': filename,
                        'predicted_well': predicted_well,
                        'confidence': confidence
                    })
        
        if validation_results['wells_without_well_char'] > 0:
            validation_results['prediction_accuracy'] = (
                validation_results['predicted_wells'] / 
                validation_results['wells_without_well_char']
            )
        
        return validation_results
    
    def save_learning_results(self, output_dir: Path, results: Dict[str, Any]):
        """保存学习结果"""
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 保存学习结果
        with open(output_dir / 'well_learning_results.json', 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        # 保存井名映射规则
        with open(output_dir / 'well_mapping_rules.json', 'w', encoding='utf-8') as f:
            json.dump(self.well_mapping, f, ensure_ascii=False, indent=2)
        
        # 生成井名列表
        with open(output_dir / 'known_wells.txt', 'w', encoding='utf-8') as f:
            for well in sorted(self.known_wells):
                f.write(f"{well}\n")
        
        # 生成预测规则报告
        self._generate_prediction_report(output_dir, results)
        
        print(f"井名学习结果已保存到: {output_dir}")
    
    def _generate_prediction_report(self, output_dir: Path, results: Dict[str, Any]):
        """生成预测规则报告"""
        report = f"""# 井名学习报告

## 学习统计

- 已知井名数量: {len(self.known_wells)}
- 前缀模式数量: {len(self.prefix_patterns)}
- 后缀模式数量: {len(self.suffix_patterns)}
- 直接映射数量: {len(self.well_mapping['direct_mappings'])}

## 验证结果

- 总文件数: {results['validation']['total_files']}
- 带"井"字文件数: {results['validation']['wells_with_well_char']}
- 不带"井"字文件数: {results['validation']['wells_without_well_char']}
- 成功预测井名数: {results['validation']['predicted_wells']}
- 预测准确率: {results['validation']['prediction_accuracy']:.2%}

## 常见前缀模式

"""
        
        for prefix, stats in sorted(self.prefix_patterns.items(), 
                                   key=lambda x: x[1]['count'], reverse=True)[:10]:
            report += f"- {prefix}: {stats['count']} 次\n"
        
        report += "\n## 常见后缀模式\n\n"
        
        for suffix, stats in sorted(self.suffix_patterns.items(), 
                                   key=lambda x: x[1]['count'], reverse=True)[:10]:
            report += f"- {suffix}: {stats['count']} 次\n"
        
        report += "\n## 预测示例\n\n"
        
        for example in results['validation']['examples'][:20]:
            report += f"- {example['filename']} -> {example['predicted_well']} (置信度: {example['confidence']:.2f})\n"
        
        with open(output_dir / 'well_learning_report.md', 'w', encoding='utf-8') as f:
            f.write(report)
