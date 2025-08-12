"""数据库优化模块 - 提供查询优化、缓存、连接池等功能"""

import time
from functools import lru_cache, wraps
from typing import Dict, List, Optional, Any, Callable
from sqlmodel import Session, create_engine, select
from sqlalchemy import Index, text
from sqlalchemy.pool import QueuePool
from sqlalchemy.orm import sessionmaker
import logging

logger = logging.getLogger(__name__)

class DatabaseOptimizer:
    """数据库优化器"""
    
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.engine = None
        self.SessionLocal = None
        self._init_engine()
        self._create_indexes()
    
    def _init_engine(self):
        """初始化数据库引擎，配置连接池"""
        self.engine = create_engine(
            self.database_url,
            echo=False,  # 生产环境关闭SQL日志
            poolclass=QueuePool,
            pool_size=10,  # 连接池大小
            max_overflow=20,  # 最大溢出连接数
            pool_pre_ping=True,  # 连接前ping检查
            pool_recycle=3600,  # 连接回收时间(秒)
        )
        self.SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine
        )
    
    def _create_indexes(self):
        """创建数据库索引"""
        try:
            with self.engine.connect() as conn:
                # 创建复合索引
                conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_well_category_depth 
                    ON images (well_name, category, start_depth)
                """))
                
                conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_sample_type 
                    ON images (sample_type)
                """))
                
                conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_rel_path 
                    ON images (rel_path)
                """))
                
                conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_created_at 
                    ON images (created_at)
                """))
                
                conn.commit()
                logger.info("数据库索引创建成功")
        except Exception as e:
            logger.warning(f"创建索引失败: {e}")
    
    def get_session(self) -> Session:
        """获取数据库会话"""
        return self.SessionLocal()
    
    def close_session(self, session: Session):
        """关闭数据库会话"""
        if session:
            session.close()

class QueryCache:
    """查询缓存管理器"""
    
    def __init__(self, max_size: int = 128, ttl: int = 300):
        self.max_size = max_size
        self.ttl = ttl
        self.cache: Dict[str, Dict[str, Any]] = {}
    
    def _generate_key(self, func_name: str, *args, **kwargs) -> str:
        """生成缓存键"""
        import hashlib
        key_data = f"{func_name}:{str(args)}:{str(sorted(kwargs.items()))}"
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        if key in self.cache:
            item = self.cache[key]
            if time.time() - item['timestamp'] < self.ttl:
                return item['value']
            else:
                del self.cache[key]
        return None
    
    def set(self, key: str, value: Any):
        """设置缓存值"""
        if len(self.cache) >= self.max_size:
            # 删除最旧的缓存项
            oldest_key = min(self.cache.keys(), 
                           key=lambda k: self.cache[k]['timestamp'])
            del self.cache[oldest_key]
        
        self.cache[key] = {
            'value': value,
            'timestamp': time.time()
        }
    
    def clear(self):
        """清空缓存"""
        self.cache.clear()

# 全局缓存实例
query_cache = QueryCache(max_size=128, ttl=300)

def cached_query(func: Callable) -> Callable:
    """查询缓存装饰器"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        cache_key = query_cache._generate_key(func.__name__, *args, **kwargs)
        
        # 尝试从缓存获取
        cached_result = query_cache.get(cache_key)
        if cached_result is not None:
            return cached_result
        
        # 执行查询
        result = func(*args, **kwargs)
        
        # 缓存结果
        query_cache.set(cache_key, result)
        
        return result
    return wrapper

class OptimizedQueries:
    """优化查询方法集合"""
    
    def __init__(self, db_optimizer: DatabaseOptimizer):
        self.db_optimizer = db_optimizer
    
    @cached_query
    def get_well_names(self, session: Session) -> List[str]:
        """获取井名列表（带缓存）"""
        from .models import Image
        result = session.exec(select(Image.well_name).distinct()).all()
        return [w for w in result if w]
    
    @cached_query
    def get_categories(self, session: Session) -> List[str]:
        """获取分类列表（带缓存）"""
        from .models import Image
        result = session.exec(select(Image.category).distinct()).all()
        return [c for c in result if c]
    
    @cached_query
    def get_sample_types(self, session: Session) -> List[str]:
        """获取样品类型列表（带缓存）"""
        from .models import Image
        result = session.exec(select(Image.sample_type).distinct()).all()
        return [s for s in result if s]
    
    def get_images_paginated(self, session: Session, page: int, per_page: int, 
                            filters: Dict[str, Any]) -> Dict[str, Any]:
        """分页查询图片（优化版本）"""
        from .models import Image
        from sqlalchemy import and_, or_, not_
        
        # 构建基础查询
        query = select(Image)
        
        # 应用过滤器
        if filters.get('well_name'):
            query = query.where(Image.well_name == filters['well_name'])
        
        if filters.get('category'):
            query = query.where(Image.category == filters['category'])
        
        if filters.get('sample_type'):
            query = query.where(Image.sample_type == filters['sample_type'])
        
        if filters.get('depth_min') is not None:
            query = query.where(Image.end_depth >= filters['depth_min'])
        
        if filters.get('depth_max') is not None:
            query = query.where(Image.start_depth <= filters['depth_max'])
        
        # 计算总数
        count_query = select(Image.id).where(query.whereclause)
        total = len(session.exec(count_query).all())
        
        # 分页
        offset = (page - 1) * per_page
        query = query.offset(offset).limit(per_page)
        
        # 排序
        query = query.order_by(Image.well_name, Image.category, Image.start_depth)
        
        # 执行查询
        items = session.exec(query).all()
        
        return {
            'items': items,
            'total': total,
            'page': page,
            'per_page': per_page,
            'pages': (total + per_page - 1) // per_page
        }
    
    def get_images_by_well(self, session: Session, well_name: str, 
                          limit: Optional[int] = None) -> List[Any]:
        """根据井名查询图片（优化版本）"""
        from .models import Image
        
        query = select(Image).where(Image.well_name == well_name)
        
        if limit:
            query = query.limit(limit)
        
        query = query.order_by(Image.start_depth, Image.category)
        
        return session.exec(query).all()

# 全局数据库优化器实例
db_optimizer = DatabaseOptimizer("sqlite:///./data/images.db")
optimized_queries = OptimizedQueries(db_optimizer)

def get_db_session() -> Session:
    """获取数据库会话的依赖函数"""
    return db_optimizer.get_session()

def close_db_session(session: Session):
    """关闭数据库会话的依赖函数"""
    db_optimizer.close_session(session)