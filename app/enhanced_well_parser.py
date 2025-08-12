"""增强的井名解析器 - 集成学习到的井名规则"""

import re
import json
from pathlib import Path
from typing import Optional, Tuple, Dict, Any
from collections import Counter

class EnhancedWellParser:
    """增强的井名解析器"""
    
    def __init__(self, well_mapping_path: Optional[Path] = None):
        self.well_mapping = {}
        self.prefix_rules = {}
        self.suffix_rules = {}
        self.known_wells = set()
        
        # 加载学习到的井名映射规则
        if well_mapping_path and well_mapping_path.exists():
            self.load_well_mapping(well_mapping_path)
    
    def load_well_mapping(self, mapping_path: Path):
        """加载井名映射规则"""
        try:
            with open(mapping_path, 'r', encoding='utf-8') as f:
                mapping_data = json.load(f)
            
            self.well_mapping = mapping_data.get('direct_mappings', {})
            self.prefix_rules = mapping_data.get('prefix_rules', {})
            self.suffix_rules = mapping_data.get('suffix_rules', {})
            
            # 构建已知井名集合
            self.known_wells = set(self.well_mapping.values())
            
            print(f"加载井名映射规则: {len(self.well_mapping)} 个直接映射")
            print(f"前缀规则: {len(self.prefix_rules)} 个")
            print(f"后缀规则: {len(self.suffix_rules)} 个")
            
        except Exception as e:
            print(f"加载井名映射规则失败: {e}")
    
    def parse_well_name(self, filename: str) -> Tuple[Optional[str], float, Dict[str, Any]]:
        """解析井名，返回 (井名, 置信度, 解析详情)"""
        if not filename:
            return None, 0.0, {'method': 'none', 'reason': 'empty_filename'}
        
        # 1. 首先尝试直接匹配带"井"字的井名
        well_matches = re.findall(r'([A-Za-z0-9\-]+井)', filename)
        if well_matches:
            return well_matches[0], 1.0, {
                'method': 'direct_match',
                'pattern': 'well_char_pattern',
                'matches': well_matches
            }
        
        # 2. 尝试直接映射（不带"井"字的已知井名）
        potential_wells = self._extract_potential_wells(filename)
        
        for well in potential_wells:
            if well in self.well_mapping:
                mapped_well = self.well_mapping[well]
                return mapped_well, 0.9, {
                    'method': 'direct_mapping',
                    'original': well,
                    'mapped': mapped_well
                }
        
        # 3. 使用学习到的规则进行预测
        best_match = None
        best_confidence = 0.0
        best_details = {}
        
        for well in potential_wells:
            confidence, details = self._calculate_well_confidence(well)
            if confidence > best_confidence:
                best_match = well
                best_confidence = confidence
                best_details = details
        
        if best_match and best_confidence > 0.5:
            # 添加"井"字
            predicted_well = best_match + "井"
            return predicted_well, best_confidence, {
                'method': 'rule_based_prediction',
                'original': best_match,
                'predicted': predicted_well,
                'confidence': best_confidence,
                'details': best_details
            }
        
        return None, 0.0, {
            'method': 'no_match',
            'reason': 'confidence_too_low',
            'potential_wells': potential_wells
        }
    
    def _extract_potential_wells(self, filename: str) -> list:
        """提取潜在的井名"""
        potential_wells = []
        
        # 移除文件扩展名
        name = re.sub(r'\.[a-zA-Z]+$', '', filename)
        
        # 查找符合井名模式的字符串
        patterns = [
            r'[A-Z]{2,4}\d+(?:-\d+)*(?:-[A-Za-z0-9]+)*',  # 标准模式
            r'[A-Z]{2,4}\d+[A-Za-z0-9]*',  # 简化模式
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, name)
            potential_wells.extend(matches)
        
        return list(set(potential_wells))  # 去重
    
    def _calculate_well_confidence(self, potential_well: str) -> Tuple[float, Dict[str, Any]]:
        """计算井名置信度"""
        confidence = 0.0
        details = {
            'prefix_score': 0.0,
            'suffix_score': 0.0,
            'length_score': 0.0,
            'structure_score': 0.0
        }
        
        # 1. 前缀匹配
        prefix_match = re.match(r'^([A-Z]{2,4})', potential_well)
        if prefix_match:
            prefix = prefix_match.group(1)
            if prefix in self.prefix_rules:
                prefix_confidence = self.prefix_rules[prefix]['confidence']
                confidence += 0.3 * prefix_confidence
                details['prefix_score'] = 0.3 * prefix_confidence
                details['prefix'] = prefix
        
        # 2. 后缀匹配
        suffix_match = re.search(r'([A-Za-z]+)$', potential_well)
        if suffix_match:
            suffix = suffix_match.group(1)
            if suffix in self.suffix_rules:
                suffix_confidence = self.suffix_rules[suffix]['confidence']
                confidence += 0.2 * suffix_confidence
                details['suffix_score'] = 0.2 * suffix_confidence
                details['suffix'] = suffix
        
        # 3. 长度匹配（基于常见井名长度）
        well_length = len(potential_well)
        if 8 <= well_length <= 15:  # 常见井名长度范围
            length_score = 1.0 - abs(well_length - 12) / 7  # 12是理想长度
            confidence += 0.1 * length_score
            details['length_score'] = 0.1 * length_score
            details['length'] = well_length
        
        # 4. 结构模式匹配
        structure = self._extract_structure_pattern(potential_well)
        if self._is_valid_structure(structure):
            confidence += 0.1
            details['structure_score'] = 0.1
            details['structure'] = structure
        
        return min(confidence, 1.0), details
    
    def _extract_structure_pattern(self, well_name: str) -> str:
        """提取井名结构模式"""
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
    
    def _is_valid_structure(self, structure: str) -> bool:
        """检查结构模式是否有效"""
        # 有效的井名结构模式
        valid_patterns = [
            'LLLNN-N-NLLL',  # BZ26-6-B6H
            'LLLNN-N-NLL',   # BZ26-6-B6
            'LLLNN-NLLL',    # BZ26-B6H
            'LLLNN-NLL',     # BZ26-B6
            'LLLNNLLL',      # BZ26B6H
            'LLLNNLL',       # BZ26B6
        ]
        
        return structure in valid_patterns
    
    def batch_parse_well_names(self, filenames: list) -> Dict[str, Any]:
        """批量解析井名"""
        results = {
            'total_files': len(filenames),
            'successful_parses': 0,
            'failed_parses': 0,
            'parsing_methods': Counter(),
            'confidence_distribution': Counter(),
            'examples': []
        }
        
        for filename in filenames:
            well_name, confidence, details = self.parse_well_name(filename)
            
            if well_name:
                results['successful_parses'] += 1
                results['parsing_methods'][details['method']] += 1
                
                # 记录置信度分布
                confidence_range = f"{int(confidence * 10) * 10}-{(int(confidence * 10) + 1) * 10}%"
                results['confidence_distribution'][confidence_range] += 1
                
                # 记录示例
                if len(results['examples']) < 20:
                    results['examples'].append({
                        'filename': filename,
                        'well_name': well_name,
                        'confidence': confidence,
                        'method': details['method']
                    })
            else:
                results['failed_parses'] += 1
        
        return results
    
    def get_well_statistics(self) -> Dict[str, Any]:
        """获取井名统计信息"""
        stats = {
            'total_known_wells': len(self.known_wells),
            'total_mappings': len(self.well_mapping),
            'prefix_rules_count': len(self.prefix_rules),
            'suffix_rules_count': len(self.suffix_rules),
            'prefix_distribution': Counter(),
            'suffix_distribution': Counter()
        }
        
        # 统计前缀分布
        for well in self.known_wells:
            well_base = well.replace('井', '')
            prefix_match = re.match(r'^([A-Z]{2,4})', well_base)
            if prefix_match:
                stats['prefix_distribution'][prefix_match.group(1)] += 1
        
        # 统计后缀分布
        for well in self.known_wells:
            well_base = well.replace('井', '')
            suffix_match = re.search(r'([A-Za-z]+)$', well_base)
            if suffix_match:
                stats['suffix_distribution'][suffix_match.group(1)] += 1
        
        return stats
