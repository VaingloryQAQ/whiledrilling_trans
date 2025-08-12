"""规则学习工具 - 从CSV数据中自动学习和优化规则"""

import re
import json
import yaml
from pathlib import Path
from typing import Dict, List, Set, Tuple, Any, Optional
from collections import Counter, defaultdict
import csv

from csv_analyzer import CsvAnalyzer
from ml_classifier import MLClassifier, HybridClassifier

class RuleLearner:
    """规则学习器 - 从数据中自动学习分类规则"""
    
    def __init__(self, csv_dir: Path, output_dir: Path):
        self.csv_dir = csv_dir
        self.output_dir = output_dir
        self.analyzer = CsvAnalyzer()
        self.learned_patterns = {}
        self.rule_suggestions = []
        
    def learn_from_csv_data(self) -> Dict[str, Any]:
        """从CSV数据中学习规则"""
        print("开始从CSV数据学习规则...")
        
        # 1. 分析CSV文件
        analysis_result = self.analyzer.generate_enhanced_rules(self.csv_dir)
        
        # 2. 学习文件名模式
        patterns = self._learn_filename_patterns()
        
        # 3. 学习分类规则
        classification_rules = self._learn_classification_rules()
        
        # 4. 学习样品类型规则
        sample_type_rules = self._learn_sample_type_rules()
        
        # 5. 生成规则建议
        suggestions = self._generate_rule_suggestions(analysis_result, patterns, classification_rules)
        
        # 6. 保存学习结果
        self._save_learning_results(analysis_result, patterns, classification_rules, sample_type_rules, suggestions)
        
        return {
            'analysis': analysis_result,
            'patterns': patterns,
            'classification_rules': classification_rules,
            'sample_type_rules': sample_type_rules,
            'suggestions': suggestions
        }
    
    def _learn_filename_patterns(self) -> Dict[str, Any]:
        """学习文件名模式"""
        patterns = {
            'well_patterns': set(),
            'depth_patterns': set(),
            'category_patterns': set(),
            'sample_type_patterns': set(),
            'special_tokens': set(),
            'file_extensions': set()
        }
        
        for csv_file in self.csv_dir.glob('*.csv'):
            with open(csv_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    filename = row.get('graphic_doc_name', '')
                    if filename and self.analyzer.is_image_file(filename):
                        self._extract_patterns_from_filename(filename, patterns)
        
        # 转换为列表并排序
        return {k: sorted(list(v)) for k, v in patterns.items()}
    
    def _extract_patterns_from_filename(self, filename: str, patterns: Dict[str, Set]):
        """从单个文件名提取模式"""
        # 井名模式
        well_matches = re.findall(r'([A-Za-z0-9\-]+井)', filename)
        patterns['well_patterns'].update(well_matches)
        
        # 深度模式
        depth_matches = re.findall(r'(\d+\.?\d*m)', filename)
        patterns['depth_patterns'].update(depth_matches)
        
        # 类别模式
        categories = ['薄片鉴定', '三维谱图', '荧光扫描', '轻烃谱图', '色谱谱图', '热解谱图']
        for cat in categories:
            if cat in filename:
                patterns['category_patterns'].add(cat)
                break
        
        # 样品类型模式
        sample_types = ['岩屑', '岩心', '壁心', '泥浆', '标样']
        for st in sample_types:
            if st in filename:
                patterns['sample_type_patterns'].add(st)
                break
        
        # 特殊标记
        special_tokens = ['精选', '单偏光', '正交光', '指纹图', '立体图', '标样1', '标样2', '标样3']
        for token in special_tokens:
            if token in filename:
                patterns['special_tokens'].add(token)
        
        # 文件扩展名
        ext_match = re.search(r'\.([a-zA-Z]+)$', filename)
        if ext_match:
            patterns['file_extensions'].add(ext_match.group(1))
    
    def _learn_classification_rules(self) -> Dict[str, Any]:
        """学习分类规则"""
        rules = {
            'categories': [],
            'priority_suggestions': {},
            'exclusion_patterns': [],
            'inclusion_patterns': []
        }
        
        # 分析每个CSV文件对应的类别
        csv_to_category = {
            'W0501010005002': '薄片鉴定',
            'W0501020005001': '三维谱图',
            'W0501030007001': '荧光扫描',
            'W0501030010006': '谱图分析'
        }
        
        for csv_file in self.csv_dir.glob('*.csv'):
            api_source = csv_file.stem
            category = csv_to_category.get(api_source, '未知')
            
            # 分析该类别下的文件名特征
            filenames = []
            with open(csv_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    filename = row.get('graphic_doc_name', '')
                    if filename and self.analyzer.is_image_file(filename):
                        filenames.append(filename)
            
            # 学习该类别的规则
            category_rules = self._learn_category_rules(filenames, category, api_source)
            rules['categories'].extend(category_rules)
        
        return rules
    
    def _learn_category_rules(self, filenames: List[str], category: str, api_source: str) -> List[Dict]:
        """学习单个类别的规则"""
        rules = []
        
        # 统计关键词频率
        keyword_freq = Counter()
        for filename in filenames:
            # 提取关键词
            keywords = self._extract_keywords(filename)
            keyword_freq.update(keywords)
        
        # 根据类别生成规则
        if category == '薄片鉴定':
            # 分析光类型分布
            light_types = {'单偏光': 0, '正交光': 0}
            for filename in filenames:
                if '单偏光' in filename:
                    light_types['单偏光'] += 1
                elif '正交光' in filename:
                    light_types['正交光'] += 1
            
            # 生成子类别规则
            if light_types['单偏光'] > 0:
                rules.append({
                    'name': '单偏光',
                    'mode': 'file',
                    'priority': 75,
                    'require_all': ['薄片鉴定', '单偏光'],
                    'api_source': api_source,
                    'confidence': light_types['单偏光'] / len(filenames)
                })
            
            if light_types['正交光'] > 0:
                rules.append({
                    'name': '正交光',
                    'mode': 'file',
                    'priority': 75,
                    'require_all': ['薄片鉴定', '正交光'],
                    'api_source': api_source,
                    'confidence': light_types['正交光'] / len(filenames)
                })
        
        elif category == '三维谱图':
            # 三维谱图是大类，需要进一步细分
            # 分析图类型分布
            chart_types = {'指纹图': 0, '立体图': 0, '等值图': 0, '三维图': 0}
            for filename in filenames:
                if '指纹图' in filename or '等值图' in filename:
                    chart_types['指纹图'] += 1
                elif '立体图' in filename or '三维图' in filename:
                    chart_types['立体图'] += 1
            
            # 添加三维指纹子分类
            if chart_types['指纹图'] > 0:
                rules.append({
                    'name': '三维指纹',
                    'mode': 'file',
                    'priority': 70,
                    'require_all': ['三维谱图'],
                    'image_tokens_any': ['指纹图', '等值图'],
                    'api_source': api_source,
                    'confidence': chart_types['指纹图'] / len(filenames)
                })
            
            # 添加三维立体子分类
            if chart_types['立体图'] > 0:
                rules.append({
                    'name': '三维立体',
                    'mode': 'file',
                    'priority': 70,
                    'require_all': ['三维谱图'],
                    'image_tokens_any': ['立体图', '三维图'],
                    'api_source': api_source,
                    'confidence': chart_types['立体图'] / len(filenames)
                })
        
        elif category == '荧光扫描':
            # 分析特殊标记
            special_count = sum(1 for f in filenames if '精选' in f)
            rules.append({
                'name': '荧光扫描',
                'mode': 'file',
                'priority': 80,
                'require_all': ['荧光扫描'],
                'special_tokens': ['精选'] if special_count > 0 else [],
                'api_source': api_source,
                'confidence': 1.0
            })
        
        elif category == '谱图分析':
            # 分析谱图类型分布
            spectrum_types = {'轻烃谱图': 0, '色谱谱图': 0, '热解谱图': 0}
            for filename in filenames:
                for st in spectrum_types:
                    if st in filename and '标样' not in filename:
                        spectrum_types[st] += 1
            
            spectrum_keys = list(spectrum_types.keys())
            for st, count in spectrum_types.items():
                if count > 0:
                    rules.append({
                        'name': st,
                        'mode': 'file',
                        'priority': 65 - spectrum_keys.index(st) * 5,
                        'require_all': [st],
                        'reject_any': ['标样'],
                        'api_source': api_source,
                        'confidence': count / len(filenames)
                    })
        
        return rules
    
    def _extract_keywords(self, filename: str) -> List[str]:
        """提取文件名中的关键词"""
        # 移除文件扩展名
        name = re.sub(r'\.[a-zA-Z]+$', '', filename)
        
        # 分词
        keywords = re.findall(r'[a-zA-Z\u4e00-\u9fa5]+', name)
        
        # 过滤短词
        keywords = [k for k in keywords if len(k) > 1]
        
        return keywords
    
    def _learn_sample_type_rules(self) -> Dict[str, Any]:
        """学习样品类型规则"""
        sample_type_stats = defaultdict(lambda: {'count': 0, 'keywords': Counter()})
        
        for csv_file in self.csv_dir.glob('*.csv'):
            with open(csv_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    filename = row.get('graphic_doc_name', '')
                    if filename and self.analyzer.is_image_file(filename):
                        # 识别样品类型
                        sample_type = self._identify_sample_type(filename)
                        if sample_type:
                            sample_type_stats[sample_type]['count'] += 1
                            keywords = self._extract_keywords(filename)
                            sample_type_stats[sample_type]['keywords'].update(keywords)
        
        # 生成样品类型规则
        rules = []
        for sample_type, stats in sample_type_stats.items():
            # 获取最相关的关键词
            top_keywords = [k for k, v in stats['keywords'].most_common(5) if v > 1]
            
            rules.append({
                'label': sample_type,
                'tokens': top_keywords,
                'count': stats['count'],
                'confidence': stats['count'] / sum(s['count'] for s in sample_type_stats.values())
            })
        
        return {'sample_types': rules}
    
    def _identify_sample_type(self, filename: str) -> Optional[str]:
        """识别样品类型"""
        sample_types = ['岩屑', '岩心', '壁心', '泥浆', '标样']
        for st in sample_types:
            if st in filename:
                return st
        return None
    
    def _generate_rule_suggestions(self, analysis_result: Dict, patterns: Dict, classification_rules: Dict) -> List[Dict]:
        """生成规则建议"""
        suggestions = []
        
        # 1. 基于模式分析的建议
        if len(patterns['well_patterns']) > 10:
            suggestions.append({
                'type': 'well_pattern',
                'message': f'发现 {len(patterns["well_patterns"])} 种井名模式，建议优化井名识别规则',
                'priority': 'medium'
            })
        
        # 2. 基于深度模式的分析
        depth_patterns = patterns['depth_patterns']
        if any('-' in dp for dp in depth_patterns):
            suggestions.append({
                'type': 'depth_pattern',
                'message': '发现深度区间模式，建议增强深度解析规则',
                'priority': 'high'
            })
        
        # 3. 基于特殊标记的建议
        special_tokens = patterns['special_tokens']
        if '精选' in special_tokens:
            suggestions.append({
                'type': 'special_token',
                'message': '发现"精选"标记，建议为荧光扫描添加精选样品处理',
                'priority': 'medium'
            })
        
        if any('标样' in token for token in special_tokens):
            suggestions.append({
                'type': 'exclusion_pattern',
                'message': '发现标准样品，建议添加排除规则',
                'priority': 'high'
            })
        
        # 4. 基于分类规则的建议
        for rule in classification_rules['categories']:
            if rule.get('confidence', 0) < 0.8:
                suggestions.append({
                    'type': 'rule_confidence',
                    'message': f'规则 "{rule["name"]}" 置信度较低 ({rule["confidence"]:.2f})，建议优化',
                    'priority': 'medium'
                })
        
        return suggestions
    
    def _save_learning_results(self, analysis_result: Dict, patterns: Dict, classification_rules: Dict, 
                              sample_type_rules: Dict, suggestions: List[Dict]):
        """保存学习结果"""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # 保存分析结果
        with open(self.output_dir / 'analysis_result.json', 'w', encoding='utf-8') as f:
            json.dump(analysis_result, f, ensure_ascii=False, indent=2)
        
        # 保存模式分析
        with open(self.output_dir / 'patterns.json', 'w', encoding='utf-8') as f:
            json.dump(patterns, f, ensure_ascii=False, indent=2)
        
        # 保存分类规则
        with open(self.output_dir / 'classification_rules.json', 'w', encoding='utf-8') as f:
            json.dump(classification_rules, f, ensure_ascii=False, indent=2)
        
        # 保存样品类型规则
        with open(self.output_dir / 'sample_type_rules.json', 'w', encoding='utf-8') as f:
            json.dump(sample_type_rules, f, ensure_ascii=False, indent=2)
        
        # 保存建议
        with open(self.output_dir / 'suggestions.json', 'w', encoding='utf-8') as f:
            json.dump(suggestions, f, ensure_ascii=False, indent=2)
        
        # 生成增强的YAML规则文件
        enhanced_rules = self._generate_enhanced_yaml_rules(classification_rules, sample_type_rules)
        with open(self.output_dir / 'enhanced_rules.yaml', 'w', encoding='utf-8') as f:
            yaml.dump(enhanced_rules, f, allow_unicode=True, default_flow_style=False)
        
        # 生成详细分析报告
        self._generate_detailed_analysis_report(analysis_result, patterns, classification_rules, sample_type_rules)
        
        print(f"学习结果已保存到: {self.output_dir}")
    
    def _generate_detailed_analysis_report(self, analysis_result: Dict, patterns: Dict, 
                                         classification_rules: Dict, sample_type_rules: Dict):
        """生成详细分析报告"""
        
        # 1. 井名模式详细分析
        self._generate_well_pattern_analysis(patterns['well_patterns'])
        
        # 2. 深度模式详细分析
        self._generate_depth_pattern_analysis(patterns['depth_patterns'])
        
        # 3. 文件扩展名分析
        self._generate_extension_analysis(patterns['file_extensions'])
        
        # 4. 特殊标记分析
        self._generate_special_token_analysis(patterns['special_tokens'])
        
        # 5. 异常文件名分析
        self._generate_anomaly_analysis()
        
        # 6. 分类规则详细分析
        self._generate_classification_analysis(classification_rules)
        
        # 7. 样品类型详细分析
        self._generate_sample_type_analysis(sample_type_rules)
    
    def _generate_well_pattern_analysis(self, well_patterns: List[str]):
        """生成井名模式详细分析"""
        well_analysis = {
            'total_wells': len(well_patterns),
            'well_patterns': well_patterns,
            'well_categories': {},
            'well_statistics': {}
        }
        
        # 按井名前缀分类
        prefix_stats = {}
        for well in well_patterns:
            # 提取前缀（如BZ、KL、SZ等）
            prefix = re.match(r'^([A-Z]{2,4})', well)
            if prefix:
                prefix = prefix.group(1)
                prefix_stats[prefix] = prefix_stats.get(prefix, 0) + 1
        
        well_analysis['well_categories'] = prefix_stats
        
        # 统计信息
        well_analysis['well_statistics'] = {
            'most_common_prefix': max(prefix_stats.items(), key=lambda x: x[1]) if prefix_stats else None,
            'prefix_count': len(prefix_stats),
            'avg_wells_per_prefix': sum(prefix_stats.values()) / len(prefix_stats) if prefix_stats else 0
        }
        
        # 保存井名分析
        with open(self.output_dir / 'well_pattern_analysis.json', 'w', encoding='utf-8') as f:
            json.dump(well_analysis, f, ensure_ascii=False, indent=2)
        
        # 生成井名列表文件
        with open(self.output_dir / 'well_names.txt', 'w', encoding='utf-8') as f:
            for well in sorted(well_patterns):
                f.write(f"{well}\n")
    
    def _generate_depth_pattern_analysis(self, depth_patterns: List[str]):
        """生成深度模式详细分析"""
        depth_analysis = {
            'total_patterns': len(depth_patterns),
            'depth_patterns': depth_patterns,
            'pattern_types': {},
            'depth_statistics': {}
        }
        
        # 分析深度模式类型
        single_depths = []
        range_depths = []
        other_patterns = []
        
        for pattern in depth_patterns:
            if re.match(r'^\d+\.?\d*m$', pattern):
                single_depths.append(pattern)
            elif re.match(r'^\d+\.?\d*-\d+\.?\d*m$', pattern):
                range_depths.append(pattern)
            else:
                other_patterns.append(pattern)
        
        depth_analysis['pattern_types'] = {
            'single_depth': {
                'count': len(single_depths),
                'examples': single_depths[:10]  # 前10个例子
            },
            'range_depth': {
                'count': len(range_depths),
                'examples': range_depths[:10]
            },
            'other_patterns': {
                'count': len(other_patterns),
                'examples': other_patterns[:10]
            }
        }
        
        # 深度统计
        if single_depths:
            depths = [float(re.search(r'(\d+\.?\d*)', d).group(1)) for d in single_depths]
            depth_analysis['depth_statistics'] = {
                'min_depth': min(depths),
                'max_depth': max(depths),
                'avg_depth': sum(depths) / len(depths),
                'depth_distribution': {
                    'shallow_0_1000': len([d for d in depths if d < 1000]),
                    'medium_1000_3000': len([d for d in depths if 1000 <= d < 3000]),
                    'deep_3000_5000': len([d for d in depths if 3000 <= d < 5000]),
                    'very_deep_5000+': len([d for d in depths if d >= 5000])
                }
            }
        
        # 保存深度分析
        with open(self.output_dir / 'depth_pattern_analysis.json', 'w', encoding='utf-8') as f:
            json.dump(depth_analysis, f, ensure_ascii=False, indent=2)
        
        # 生成深度模式列表文件
        with open(self.output_dir / 'depth_patterns.txt', 'w', encoding='utf-8') as f:
            for pattern in sorted(depth_patterns):
                f.write(f"{pattern}\n")
    
    def _generate_extension_analysis(self, extensions: List[str]):
        """生成文件扩展名分析"""
        ext_stats = {}
        for ext in extensions:
            ext_stats[ext] = ext_stats.get(ext, 0) + 1
        
        ext_analysis = {
            'total_extensions': len(ext_stats),
            'extension_statistics': ext_stats,
            'most_common': max(ext_stats.items(), key=lambda x: x[1]) if ext_stats else None
        }
        
        # 保存扩展名分析
        with open(self.output_dir / 'extension_analysis.json', 'w', encoding='utf-8') as f:
            json.dump(ext_analysis, f, ensure_ascii=False, indent=2)
    
    def _generate_special_token_analysis(self, special_tokens: List[str]):
        """生成特殊标记分析"""
        token_analysis = {
            'total_tokens': len(special_tokens),
            'special_tokens': special_tokens,
            'token_categories': {
                'light_types': [t for t in special_tokens if t in ['单偏光', '正交光']],
                'chart_types': [t for t in special_tokens if t in ['指纹图', '立体图', '等值图', '三维图']],
                'sample_marks': [t for t in special_tokens if t in ['精选', '标样1', '标样2', '标样3']]
            }
        }
        
        # 保存特殊标记分析
        with open(self.output_dir / 'special_token_analysis.json', 'w', encoding='utf-8') as f:
            json.dump(token_analysis, f, ensure_ascii=False, indent=2)
    
    def _generate_anomaly_analysis(self):
        """生成异常文件名分析"""
        anomalies = []
        
        for csv_file in self.csv_dir.glob('*.csv'):
            with open(csv_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    filename = row.get('graphic_doc_name', '')
                    if filename and self.analyzer.is_image_file(filename):
                        # 检查各种异常
                        anomaly_info = self._check_filename_anomalies(filename)
                        if anomaly_info['anomalies']:
                            anomalies.append({
                                'filename': filename,
                                'source_file': csv_file.name,
                                'anomalies': anomaly_info['anomalies'],
                                'severity': anomaly_info['severity']
                            })
        
        # 按严重程度排序
        anomalies.sort(key=lambda x: x['severity'], reverse=True)
        
        anomaly_analysis = {
            'total_anomalies': len(anomalies),
            'anomaly_types': {},
            'anomalies': anomalies[:100]  # 只保存前100个异常
        }
        
        # 统计异常类型
        for anomaly in anomalies:
            for anomaly_type in anomaly['anomalies']:
                anomaly_analysis['anomaly_types'][anomaly_type] = \
                    anomaly_analysis['anomaly_types'].get(anomaly_type, 0) + 1
        
        # 保存异常分析
        with open(self.output_dir / 'anomaly_analysis.json', 'w', encoding='utf-8') as f:
            json.dump(anomaly_analysis, f, ensure_ascii=False, indent=2)
        
        # 生成异常文件名列表
        with open(self.output_dir / 'anomaly_filenames.txt', 'w', encoding='utf-8') as f:
            for anomaly in anomalies:
                f.write(f"{anomaly['filename']} | {', '.join(anomaly['anomalies'])}\n")
    
    def _check_filename_anomalies(self, filename: str) -> Dict:
        """检查文件名异常"""
        anomalies = []
        severity = 0
        
        # 检查缺少井名
        if not re.search(r'[A-Za-z0-9\-]+井', filename):
            anomalies.append('缺少井名')
            severity += 3
        
        # 检查缺少深度（支持全角字符和缺少单位的情况）
        depth_patterns = [
            r'\d+\.?\d*m',  # 标准格式：数字+m
            r'\d+\.?\d*ｍ',  # 全角格式：数字+ｍ
            r'\d+\.?\d*\.jpg',  # 缺少单位但以.jpg结尾
            r'\d+\.?\d*\.png',  # 缺少单位但以.png结尾
            r'\d+\.?\d*\.pdf',  # 缺少单位但以.pdf结尾
        ]
        has_depth = any(re.search(pattern, filename) for pattern in depth_patterns)
        if not has_depth:
            anomalies.append('缺少深度')
            severity += 2
        
        # 检查缺少样品类型（扩展样品类型列表）
        sample_types = [
            '岩屑', '岩心', '壁心', '泥浆', '标样', 
            '钻井液', '井壁取心', '井液', '循环泥浆',
            '取心', '岩芯', '壁取心', '壁芯'
        ]
        if not any(st in filename for st in sample_types):
            anomalies.append('缺少样品类型')
            severity += 2
        
        # 检查缺少类别
        categories = ['薄片鉴定', '三维谱图', '荧光扫描', '轻烃谱图', '色谱谱图', '热解谱图']
        if not any(cat in filename for cat in categories):
            anomalies.append('缺少类别')
            severity += 2
        
        # 检查特殊字符（排除正常的标点符号）
        # 允许的字符：字母、数字、中文、连字符、下划线、点、井字
        if re.search(r'[^\w\u4e00-\u9fa5\-\._井（）()]', filename):
            anomalies.append('包含特殊字符')
            severity += 1
        
        # 检查文件名长度
        if len(filename) > 100:
            anomalies.append('文件名过长')
            severity += 1
        
        return {
            'anomalies': anomalies,
            'severity': severity
        }
    
    def _generate_classification_analysis(self, classification_rules: Dict):
        """生成分类规则详细分析"""
        analysis = {
            'total_rules': len(classification_rules['categories']),
            'rules_by_priority': {},
            'rules_by_confidence': {},
            'detailed_rules': []
        }
        
        for rule in classification_rules['categories']:
            # 按优先级分组
            priority = rule['priority']
            if priority not in analysis['rules_by_priority']:
                analysis['rules_by_priority'][priority] = []
            analysis['rules_by_priority'][priority].append(rule['name'])
            
            # 按置信度分组
            confidence = rule.get('confidence', 0)
            confidence_range = f"{int(confidence * 10) * 10}-{(int(confidence * 10) + 1) * 10}%"
            if confidence_range not in analysis['rules_by_confidence']:
                analysis['rules_by_confidence'][confidence_range] = []
            analysis['rules_by_confidence'][confidence_range].append(rule['name'])
            
            # 详细规则信息
            analysis['detailed_rules'].append({
                'name': rule['name'],
                'priority': rule['priority'],
                'confidence': rule.get('confidence', 0),
                'mode': rule['mode'],
                'require_all': rule.get('require_all', []),
                'image_tokens_any': rule.get('image_tokens_any', []),
                'reject_any': rule.get('reject_any', []),
                'api_source': rule.get('api_source', '')
            })
        
        # 保存分类分析
        with open(self.output_dir / 'classification_analysis.json', 'w', encoding='utf-8') as f:
            json.dump(analysis, f, ensure_ascii=False, indent=2)
    
    def _generate_sample_type_analysis(self, sample_type_rules: Dict):
        """生成样品类型详细分析"""
        analysis = {
            'total_sample_types': len(sample_type_rules['sample_types']),
            'sample_type_details': sample_type_rules['sample_types'],
            'token_frequency': {}
        }
        
        # 统计token频率
        for rule in sample_type_rules['sample_types']:
            for token in rule['tokens']:
                analysis['token_frequency'][token] = analysis['token_frequency'].get(token, 0) + 1
        
        # 保存样品类型分析
        with open(self.output_dir / 'sample_type_analysis.json', 'w', encoding='utf-8') as f:
            json.dump(analysis, f, ensure_ascii=False, indent=2)
    
    def _generate_enhanced_yaml_rules(self, classification_rules: Dict, sample_type_rules: Dict) -> Dict:
        """生成增强的YAML规则"""
        enhanced_rules = {
            'categories': [],
            'sample_types': [],
            'metadata': {
                'generated_by': 'RuleLearner',
                'version': '2.0',
                'description': '基于CSV数据学习的增强规则'
            }
        }
        
        # 添加分类规则
        for rule in classification_rules['categories']:
            yaml_rule = {
                'name': rule['name'],
                'mode': rule['mode'],
                'priority': rule['priority'],
                'require_all': rule['require_all']
            }
            
            if 'reject_any' in rule:
                yaml_rule['reject_any'] = rule['reject_any']
            
            if 'special_tokens' in rule:
                yaml_rule['special_tokens'] = rule['special_tokens']
            
            if 'image_tokens_any' in rule:
                yaml_rule['image_tokens_any'] = rule['image_tokens_any']
            
            enhanced_rules['categories'].append(yaml_rule)
        
        # 添加样品类型规则
        for rule in sample_type_rules['sample_types']:
            enhanced_rules['sample_types'].append({
                'label': rule['label'],
                'tokens': rule['tokens']
            })
        
        return enhanced_rules
    
    def evaluate_learned_rules(self, test_csv_dir: Optional[Path] = None) -> Dict[str, Any]:
        """评估学习到的规则"""
        if test_csv_dir is None:
            test_csv_dir = self.csv_dir
        
        # 使用混合分类器评估
        hybrid_classifier = HybridClassifier()
        
        # 准备测试数据
        test_files = []
        for csv_file in test_csv_dir.glob('*.csv'):
            with open(csv_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    filename = row.get('graphic_doc_name', '')
                    if filename:
                        test_files.append(filename)
        
        # 评估性能
        performance = hybrid_classifier.evaluate_hybrid_performance(test_files)
        
        return {
            'test_files_count': len(test_files),
            'performance': performance,
            'accuracy': performance['rule_based']['success_rate'] if performance['rule_based']['count'] > 0 else 0.0
        }
