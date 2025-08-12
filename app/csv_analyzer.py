"""CSV数据分析器 - 用于从API CSV文件中学习文件名模式和规则"""

import re
import csv
from pathlib import Path
from typing import Dict, List, Set, Tuple, Any
from collections import Counter, defaultdict
import json

class CsvAnalyzer:
    """CSV文件名模式分析器"""
    
    def __init__(self):
        self.patterns = {}
        self.sample_types = set()
        self.categories = set()
        self.well_names = set()
        self.depth_patterns = set()
        self.special_tokens = set()
        # 定义图片文件扩展名
        self.image_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif', '.gif', '.webp'}
        
    def is_image_file(self, filename: str) -> bool:
        """检查文件是否为图片类型"""
        if not filename:
            return False
        
        # 获取文件扩展名
        file_ext = Path(filename).suffix.lower()
        return file_ext in self.image_extensions
    
    def analyze_csv(self, csv_path: Path, api_source: str) -> Dict[str, Any]:
        """分析单个CSV文件"""
        print(f"分析CSV文件: {csv_path.name}")
        
        filenames = []
        image_filenames = []
        non_image_filenames = []
        
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                filename = row.get('graphic_doc_name', '')
                if filename:
                    filenames.append(filename)
                    if self.is_image_file(filename):
                        image_filenames.append(filename)
                    else:
                        non_image_filenames.append(filename)
        
        print(f"总文件数: {len(filenames)}, 图片文件数: {len(image_filenames)}, 非图片文件数: {len(non_image_filenames)}")
        
        # 只分析图片文件名模式
        patterns = self._extract_patterns(image_filenames)
        
        # 统计信息
        stats = {
            'total_files': len(filenames),
            'image_files': len(image_filenames),
            'non_image_files': len(non_image_filenames),
            'unique_wells': len(self.well_names),
            'unique_sample_types': len(self.sample_types),
            'unique_categories': len(self.categories),
            'patterns': patterns,
            'sample_type_distribution': self._get_sample_type_distribution(image_filenames),
            'category_distribution': self._get_category_distribution(image_filenames),
            'depth_analysis': self._analyze_depth_patterns(image_filenames),
            'special_tokens': list(self.special_tokens),
            'file_extension_distribution': self._get_file_extension_distribution(image_filenames)
        }
        
        return stats
    
    def _extract_patterns(self, filenames: List[str]) -> Dict[str, Any]:
        """提取文件名模式"""
        patterns = {
            'well_patterns': [],
            'sample_type_patterns': [],
            'category_patterns': [],
            'depth_patterns': [],
            'file_extension_patterns': []
        }
        
        for filename in filenames:
            # 只处理图片文件
            if not self.is_image_file(filename):
                continue
                
            # 解析井名
            well_match = re.search(r'([A-Za-z0-9\-]+井)', filename)
            if well_match:
                well = well_match.group(1)
                self.well_names.add(well)
            
            # 解析样品类型
            sample_types = ['岩屑', '岩心', '壁心', '泥浆', '标样']
            for st in sample_types:
                if st in filename:
                    self.sample_types.add(st)
                    break
            
            # 解析类别
            categories = ['薄片鉴定', '三维谱图', '荧光扫描', '轻烃谱图', '色谱谱图', '热解谱图']
            for cat in categories:
                if cat in filename:
                    self.categories.add(cat)
                    break
            
            # 解析深度
            depth_match = re.search(r'(\d+\.?\d*m)', filename)
            if depth_match:
                depth = depth_match.group(1)
                self.depth_patterns.add(depth)
            
            # 解析特殊标记
            special_tokens = ['精选', '标样1', '标样2', '标样3', '单偏光', '正交光', '指纹图', '立体图']
            for token in special_tokens:
                if token in filename:
                    self.special_tokens.add(token)
            
            # 解析文件扩展名
            ext_match = re.search(r'\.([a-zA-Z]+)$', filename)
            if ext_match:
                ext = ext_match.group(1)
                patterns['file_extension_patterns'].append(ext)
        
        return patterns
    
    def _get_sample_type_distribution(self, filenames: List[str]) -> Dict[str, int]:
        """获取样品类型分布"""
        distribution = Counter()
        sample_types = ['岩屑', '岩心', '壁心', '泥浆', '标样']
        
        for filename in filenames:
            # 只处理图片文件
            if not self.is_image_file(filename):
                continue
                
            for st in sample_types:
                if st in filename:
                    distribution[st] += 1
                    break
        
        return dict(distribution)
    
    def _get_category_distribution(self, filenames: List[str]) -> Dict[str, int]:
        """获取类别分布"""
        distribution = Counter()
        categories = ['薄片鉴定', '三维谱图', '荧光扫描', '轻烃谱图', '色谱谱图', '热解谱图']
        
        for filename in filenames:
            # 只处理图片文件
            if not self.is_image_file(filename):
                continue
                
            for cat in categories:
                if cat in filename:
                    distribution[cat] += 1
                    break
        
        return dict(distribution)
    
    def _get_file_extension_distribution(self, filenames: List[str]) -> Dict[str, int]:
        """获取文件扩展名分布"""
        distribution = Counter()
        
        for filename in filenames:
            # 只处理图片文件
            if not self.is_image_file(filename):
                continue
                
            ext_match = re.search(r'\.([a-zA-Z]+)$', filename)
            if ext_match:
                ext = ext_match.group(1).lower()
                distribution[ext] += 1
        
        return dict(distribution)
    
    def _analyze_depth_patterns(self, filenames: List[str]) -> Dict[str, Any]:
        """分析深度模式"""
        single_depths = []
        range_depths = []
        
        for filename in filenames:
            # 只处理图片文件
            if not self.is_image_file(filename):
                continue
                
            # 单深度模式
            single_match = re.search(r'(\d+\.?\d*)m(?!\d)', filename)
            if single_match:
                single_depths.append(float(single_match.group(1)))
            
            # 深度区间模式
            range_match = re.search(r'(\d+\.?\d*)-(\d+\.?\d*)m', filename)
            if range_match:
                start = float(range_match.group(1))
                end = float(range_match.group(2))
                range_depths.append((start, end))
        
        return {
            'single_depth_count': len(single_depths),
            'range_depth_count': len(range_depths),
            'single_depth_stats': {
                'min': min(single_depths) if single_depths else None,
                'max': max(single_depths) if single_depths else None,
                'avg': sum(single_depths) / len(single_depths) if single_depths else None
            },
            'range_depth_stats': {
                'min_start': min([r[0] for r in range_depths]) if range_depths else None,
                'max_end': max([r[1] for r in range_depths]) if range_depths else None,
                'avg_range': sum([r[1] - r[0] for r in range_depths]) / len(range_depths) if range_depths else None
            }
        }
    
    def generate_enhanced_rules(self, csv_dir: Path) -> Dict[str, Any]:
        """基于CSV数据生成增强规则"""
        all_stats = {}
        
        # 分析所有CSV文件
        for csv_file in csv_dir.glob('*.csv'):
            api_source = csv_file.stem
            stats = self.analyze_csv(csv_file, api_source)
            all_stats[api_source] = stats
        
        # 生成增强规则
        enhanced_rules = self._generate_rules_from_stats(all_stats)
        
        return {
            'analysis_stats': all_stats,
            'enhanced_rules': enhanced_rules
        }
    
    def _generate_rules_from_stats(self, stats: Dict[str, Any]) -> Dict[str, Any]:
        """从统计数据生成增强规则"""
        enhanced_rules = {
            'categories': [],
            'sample_types': [],
            'patterns': {},
            'filters': {}
        }
        
        # 基于CSV数据生成新的分类规则
        for api_source, stat in stats.items():
            if api_source == 'W0501010005002':  # 薄片鉴定
                enhanced_rules['categories'].extend([
                    {
                        'name': '单偏光',
                        'mode': 'file',
                        'priority': 75,
                        'require_all': ['薄片鉴定', '单偏光'],
                        'api_source': api_source
                    },
                    {
                        'name': '正交光',
                        'mode': 'file',
                        'priority': 75,
                        'require_all': ['薄片鉴定', '正交光'],
                        'api_source': api_source
                    }
                ])
            
            elif api_source == 'W0501020005001':  # 三维谱图
                enhanced_rules['categories'].extend([
                    {
                        'name': '三维指纹',
                        'mode': 'file',
                        'priority': 70,
                        'require_all': ['三维谱图', '指纹图'],
                        'api_source': api_source
                    },
                    {
                        'name': '三维立体',
                        'mode': 'file',
                        'priority': 70,
                        'require_all': ['三维谱图', '立体图'],
                        'api_source': api_source
                    }
                ])
            
            elif api_source == 'W0501030007001':  # 荧光扫描
                enhanced_rules['categories'].append({
                    'name': '荧光扫描',
                    'mode': 'file',
                    'priority': 80,
                    'require_all': ['荧光扫描'],
                    'special_tokens': ['精选'],
                    'api_source': api_source
                })
            
            elif api_source == 'W0501030010006':  # 谱图分析
                enhanced_rules['categories'].extend([
                    {
                        'name': '轻烃谱图',
                        'mode': 'file',
                        'priority': 65,
                        'require_all': ['轻烃谱图'],
                        'reject_any': ['标样'],
                        'api_source': api_source
                    },
                    {
                        'name': '色谱谱图',
                        'mode': 'file',
                        'priority': 60,
                        'require_all': ['色谱谱图'],
                        'reject_any': ['标样'],
                        'api_source': api_source
                    },
                    {
                        'name': '热解谱图',
                        'mode': 'file',
                        'priority': 55,
                        'require_all': ['热解谱图'],
                        'reject_any': ['标样'],
                        'api_source': api_source
                    }
                ])
        
        # 增强样品类型规则
        enhanced_rules['sample_types'] = [
            {'label': '岩屑', 'tokens': ['岩屑', '钻屑', '岩粉']},
            {'label': '岩心', 'tokens': ['岩心', '取心', '岩芯']},
            {'label': '壁心', 'tokens': ['壁心', '壁取心', '壁芯']},
            {'label': '泥浆', 'tokens': ['泥浆', '循环泥浆']},
            {'label': '标样', 'tokens': ['标样1', '标样2', '标样3', '标样']}
        ]
        
        # 添加过滤规则
        enhanced_rules['filters'] = {
            'exclude_patterns': ['标样1', '标样2', '标样3'],  # 排除标准样品
            'special_handling': {
                '精选': '荧光扫描精选样品',
                '标样': '标准样品，用于校准'
            },
            'image_only': True,  # 只处理图片文件
            'image_extensions': list(self.image_extensions)
        }
        
        return enhanced_rules
