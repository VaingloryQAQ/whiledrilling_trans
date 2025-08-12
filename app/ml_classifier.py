"""机器学习增强的分类器 - 结合规则引擎和ML模型"""

import re
import json
import pickle
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from collections import Counter
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, accuracy_score
import joblib

from normalizer import Normalizer
from config import load_rules

class MLClassifier:
    """机器学习增强的分类器"""
    
    def __init__(self, model_path: Optional[Path] = None):
        self.vectorizer = TfidfVectorizer(
            max_features=1000,
            ngram_range=(1, 3),
            stop_words=None,
            token_pattern=r'[a-zA-Z\u4e00-\u9fa5]+'
        )
        self.classifier = RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            random_state=42
        )
        self.is_trained = False
        self.class_labels = []
        self.model_path = model_path
        
        # 定义图片文件扩展名
        self.image_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif', '.gif', '.webp'}
        
        # 加载预训练模型
        if model_path and model_path.exists():
            self.load_model(model_path)
    
    def is_image_file(self, filename: str) -> bool:
        """检查文件是否为图片类型"""
        if not filename:
            return False
        
        # 获取文件扩展名
        file_ext = Path(filename).suffix.lower()
        return file_ext in self.image_extensions
    
    def extract_features(self, filename: str) -> str:
        """从文件名提取特征文本"""
        # 移除文件扩展名
        name = re.sub(r'\.[a-zA-Z]+$', '', filename)
        
        # 标准化文本
        name = Normalizer.normalize_text(name)
        
        # 提取关键特征
        features = []
        
        # 井名特征
        well_match = re.search(r'([A-Za-z0-9\-]+井)', name)
        if well_match:
            features.append(f"WELL_{well_match.group(1)}")
        
        # 深度特征
        depth_match = re.search(r'(\d+\.?\d*)m', name)
        if depth_match:
            depth = float(depth_match.group(1))
            # 深度分桶
            if depth < 1000:
                features.append("DEPTH_SHALLOW")
            elif depth < 3000:
                features.append("DEPTH_MEDIUM")
            else:
                features.append("DEPTH_DEEP")
        
        # 样品类型特征
        sample_types = ['岩屑', '岩心', '壁心', '泥浆', '标样']
        for st in sample_types:
            if st in name:
                features.append(f"SAMPLE_{st}")
                break
        
        # 类别特征
        categories = ['薄片鉴定', '三维谱图', '荧光扫描', '轻烃谱图', '色谱谱图', '热解谱图']
        for cat in categories:
            if cat in name:
                features.append(f"CATEGORY_{cat}")
                break
        
        # 特殊标记特征
        special_tokens = ['精选', '单偏光', '正交光', '指纹图', '立体图']
        for token in special_tokens:
            if token in name:
                features.append(f"SPECIAL_{token}")
        
        # 组合特征
        combined = f"{name} {' '.join(features)}"
        return combined
    
    def prepare_training_data(self, csv_dir: Path) -> Tuple[List[str], List[str]]:
        """从CSV文件准备训练数据"""
        features = []
        labels = []
        
        # 定义CSV文件到类别的映射
        csv_to_category = {
            'W0501010005002': '薄片鉴定',
            'W0501020005001': '三维谱图',
            'W0501030007001': '荧光扫描',
            'W0501030010006': '谱图分析'
        }
        
        import csv
        for csv_file in csv_dir.glob('*.csv'):
            api_source = csv_file.stem
            category = csv_to_category.get(api_source, '未知')
            
            with open(csv_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    filename = row.get('graphic_doc_name', '')
                    if filename and self.is_image_file(filename):
                        feature_text = self.extract_features(filename)
                        features.append(feature_text)
                        labels.append(category)
        
        return features, labels
    
    def train(self, csv_dir: Path, test_size: float = 0.2) -> Dict[str, Any]:
        """训练模型"""
        print("准备训练数据...")
        features, labels = self.prepare_training_data(csv_dir)
        
        if not features:
            raise ValueError("没有找到训练数据")
        
        print(f"训练数据: {len(features)} 个样本")
        
        # 分割训练集和测试集
        X_train, X_test, y_train, y_test = train_test_split(
            features, labels, test_size=test_size, random_state=42, stratify=labels
        )
        
        # 特征向量化
        print("特征向量化...")
        X_train_vectors = self.vectorizer.fit_transform(X_train)
        X_test_vectors = self.vectorizer.transform(X_test)
        
        # 训练分类器
        print("训练分类器...")
        self.classifier.fit(X_train_vectors, y_train)
        
        # 评估模型
        y_pred = self.classifier.predict(X_test_vectors)
        accuracy = accuracy_score(y_test, y_pred)
        
        # 生成分类报告
        report = classification_report(y_test, y_pred, output_dict=True)
        
        self.is_trained = True
        self.class_labels = list(set(labels))
        
        # 保存模型
        if self.model_path:
            self.save_model(self.model_path)
        
        return {
            'accuracy': accuracy,
            'classification_report': report,
            'training_samples': len(X_train),
            'test_samples': len(X_test),
            'feature_count': X_train_vectors.shape[1]
        }
    
    def predict(self, filename: str) -> Tuple[str, float]:
        """预测单个文件的类别"""
        if not self.is_trained:
            raise RuntimeError("模型未训练，请先调用 train() 方法")
        
        feature_text = self.extract_features(filename)
        feature_vector = self.vectorizer.transform([feature_text])
        
        # 预测类别和概率
        prediction = self.classifier.predict(feature_vector)[0]
        probabilities = self.classifier.predict_proba(feature_vector)[0]
        
        # 获取预测类别的概率
        pred_idx = self.classifier.classes_.tolist().index(prediction)
        confidence = probabilities[pred_idx]
        
        return prediction, confidence
    
    def predict_batch(self, filenames: List[str]) -> List[Tuple[str, str, float]]:
        """批量预测"""
        if not self.is_trained:
            raise RuntimeError("模型未训练，请先调用 train() 方法")
        
        features = [self.extract_features(fname) for fname in filenames]
        feature_vectors = self.vectorizer.transform(features)
        
        predictions = self.classifier.predict(feature_vectors)
        probabilities = self.classifier.predict_proba(feature_vectors)
        
        results = []
        for i, (filename, pred) in enumerate(zip(filenames, predictions)):
            pred_idx = self.classifier.classes_.tolist().index(pred)
            confidence = probabilities[i][pred_idx]
            results.append((filename, pred, confidence))
        
        return results
    
    def save_model(self, model_path: Path):
        """保存模型"""
        model_data = {
            'vectorizer': self.vectorizer,
            'classifier': self.classifier,
            'class_labels': self.class_labels,
            'is_trained': self.is_trained
        }
        joblib.dump(model_data, model_path)
        print(f"模型已保存到: {model_path}")
    
    def load_model(self, model_path: Path):
        """加载模型"""
        model_data = joblib.load(model_path)
        self.vectorizer = model_data['vectorizer']
        self.classifier = model_data['classifier']
        self.class_labels = model_data['class_labels']
        self.is_trained = model_data['is_trained']
        print(f"模型已从 {model_path} 加载")
    
    def get_feature_importance(self) -> Dict[str, float]:
        """获取特征重要性"""
        if not self.is_trained:
            return {}
        
        feature_names = self.vectorizer.get_feature_names_out()
        importances = self.classifier.feature_importances_
        
        # 按重要性排序
        feature_importance = list(zip(feature_names, importances))
        feature_importance.sort(key=lambda x: x[1], reverse=True)
        
        return dict(feature_importance[:20])  # 返回前20个重要特征


class HybridClassifier:
    """混合分类器 - 结合规则引擎和ML模型"""
    
    def __init__(self, rules: Optional[Dict] = None, ml_model_path: Optional[Path] = None):
        self.rules = rules or load_rules()
        self.ml_classifier = MLClassifier(ml_model_path) if ml_model_path else None
        self.confidence_threshold = 0.8  # ML模型置信度阈值
    
    def classify(self, filename: str, sample_type: Optional[str] = None) -> Tuple[Optional[str], Dict[str, Any]]:
        """混合分类方法"""
        # 首先使用规则引擎
        rule_result, rule_explain = self._rule_based_classify(filename, sample_type)
        
        # 如果规则引擎有结果，直接返回
        if rule_result:
            return rule_result, {
                'method': 'rule_based',
                'confidence': 1.0,
                'explanation': rule_explain
            }
        
        # 如果ML模型可用，使用ML分类
        if self.ml_classifier and self.ml_classifier.is_trained:
            try:
                ml_result, ml_confidence = self.ml_classifier.predict(filename)
                
                # 如果ML置信度足够高，使用ML结果
                if ml_confidence >= self.confidence_threshold:
                    return ml_result, {
                        'method': 'ml_based',
                        'confidence': ml_confidence,
                        'explanation': f'ML模型预测: {ml_result} (置信度: {ml_confidence:.3f})'
                    }
            except Exception as e:
                print(f"ML分类失败: {e}")
        
        # 如果都没有结果，返回None
        return None, {
            'method': 'none',
            'confidence': 0.0,
            'explanation': '规则引擎和ML模型都无法分类'
        }
    
    def _rule_based_classify(self, filename: str, sample_type: Optional[str] = None) -> Tuple[Optional[str], Dict[str, Any]]:
        """基于规则的分类（简化版）"""
        # 这里可以调用现有的classifier.py中的逻辑
        # 为了简化，这里实现一个基础版本
        
        filename_lower = filename.lower()
        
        # 薄片鉴定
        if '薄片鉴定' in filename:
            if '单偏光' in filename:
                return '单偏光', {'rule': '薄片鉴定_单偏光'}
            elif '正交光' in filename:
                return '正交光', {'rule': '薄片鉴定_正交光'}
        
        # 三维谱图
        if '三维谱图' in filename:
            if '指纹图' in filename or '等值图' in filename:
                return '三维指纹', {'rule': '三维谱图_指纹图/等值图'}
            elif '立体图' in filename or '三维图' in filename:
                return '三维立体', {'rule': '三维谱图_立体图/三维图'}
        
        # 荧光扫描
        if '荧光扫描' in filename:
            return '荧光扫描', {'rule': '荧光扫描'}
        
        # 谱图分析
        if '轻烃谱图' in filename and '标样' not in filename:
            return '轻烃谱图', {'rule': '轻烃谱图'}
        elif '色谱谱图' in filename and '标样' not in filename:
            return '色谱谱图', {'rule': '色谱谱图'}
        elif '热解谱图' in filename and '标样' not in filename:
            return '热解谱图', {'rule': '热解谱图'}
        
        return None, {'rule': 'no_match'}
    
    def train_ml_model(self, csv_dir: Path) -> Dict[str, Any]:
        """训练ML模型"""
        if not self.ml_classifier:
            self.ml_classifier = MLClassifier()
        
        return self.ml_classifier.train(csv_dir)
    
    def evaluate_hybrid_performance(self, test_files: List[str]) -> Dict[str, Any]:
        """评估混合分类器性能"""
        results = {
            'rule_based': {'count': 0, 'success': 0},
            'ml_based': {'count': 0, 'success': 0},
            'none': {'count': 0}
        }
        
        # 过滤出图片文件
        image_files = [f for f in test_files if self.ml_classifier.is_image_file(f)]
        non_image_files = [f for f in test_files if not self.ml_classifier.is_image_file(f)]
        
        print(f"评估文件总数: {len(test_files)}, 图片文件: {len(image_files)}, 非图片文件: {len(non_image_files)}")
        
        for filename in image_files:
            result, explain = self.classify(filename)
            
            method = explain['method']
            results[method]['count'] += 1
            
            if method == 'rule_based':
                if result:
                    results[method]['success'] += 1
            elif method == 'ml_based':
                if result and explain['confidence'] >= self.confidence_threshold:
                    results[method]['success'] += 1
        
        # 计算成功率
        for method in ['rule_based', 'ml_based']:
            if results[method]['count'] > 0:
                results[method]['success_rate'] = results[method]['success'] / results[method]['count']
            else:
                results[method]['success_rate'] = 0.0
        
        return results
