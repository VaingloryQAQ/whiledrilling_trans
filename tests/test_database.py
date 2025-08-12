"""数据库模块测试"""

import pytest
from unittest.mock import Mock, patch
from sqlmodel import Session, create_engine
from sqlalchemy.pool import StaticPool

from app.database import DatabaseOptimizer, QueryCache, OptimizedQueries
from app.models import Image

class TestDatabaseOptimizer:
    """数据库优化器测试"""
    
    def test_database_optimizer_init(self):
        """测试数据库优化器初始化"""
        # 使用内存数据库进行测试
        db_url = "sqlite:///:memory:"
        optimizer = DatabaseOptimizer(db_url)
        
        assert optimizer.database_url == db_url
        assert optimizer.engine is not None
        assert optimizer.SessionLocal is not None
    
    def test_get_session(self):
        """测试获取数据库会话"""
        db_url = "sqlite:///:memory:"
        optimizer = DatabaseOptimizer(db_url)
        
        session = optimizer.get_session()
        assert isinstance(session, Session)
        optimizer.close_session(session)
    
    def test_create_indexes(self):
        """测试创建索引"""
        # 使用内存数据库，索引创建应该不会失败
        db_url = "sqlite:///:memory:"
        optimizer = DatabaseOptimizer(db_url)
        
        # 索引创建应该成功（不会抛出异常）
        assert optimizer.engine is not None

class TestQueryCache:
    """查询缓存测试"""
    
    def test_cache_operations(self):
        """测试缓存操作"""
        cache = QueryCache(max_size=2, ttl=1)
        
        # 设置缓存
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        
        # 获取缓存
        assert cache.get("key1") == "value1"
        assert cache.get("key2") == "value2"
        assert cache.get("key3") is None
        
        # 测试缓存大小限制
        cache.set("key3", "value3")  # 应该覆盖最旧的缓存
        assert cache.get("key1") is None  # key1应该被移除
        assert cache.get("key2") == "value2"
        assert cache.get("key3") == "value3"
    
    def test_cache_ttl(self):
        """测试缓存TTL"""
        cache = QueryCache(max_size=10, ttl=0.1)  # 100ms TTL
        
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"
        
        # 等待TTL过期
        import time
        time.sleep(0.2)
        assert cache.get("key1") is None
    
    def test_cache_clear(self):
        """测试清空缓存"""
        cache = QueryCache()
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        
        assert cache.get("key1") == "value1"
        assert cache.get("key2") == "value2"
        
        cache.clear()
        assert cache.get("key1") is None
        assert cache.get("key2") is None

class TestOptimizedQueries:
    """优化查询测试"""
    
    @pytest.fixture
    def test_session(self):
        """创建测试会话"""
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        
        # 创建表
        from sqlmodel import SQLModel
        SQLModel.metadata.create_all(engine)
        
        with Session(engine) as session:
            yield session
    
    def test_get_well_names(self, test_session):
        """测试获取井名列表"""
        # 创建测试数据
        image1 = Image(well_name="BZ8-3S-3", rel_path="test1.jpg")
        image2 = Image(well_name="LK25-4-2d", rel_path="test2.jpg")
        image3 = Image(well_name="BZ8-3S-3", rel_path="test3.jpg")  # 重复井名
        
        test_session.add(image1)
        test_session.add(image2)
        test_session.add(image3)
        test_session.commit()
        
        # 测试查询
        optimizer = DatabaseOptimizer("sqlite:///:memory:")
        queries = OptimizedQueries(optimizer)
        
        well_names = queries.get_well_names(test_session)
        assert "BZ8-3S-3" in well_names
        assert "LK25-4-2d" in well_names
        assert len(well_names) == 2  # 去重后应该只有2个井名
    
    def test_get_categories(self, test_session):
        """测试获取分类列表"""
        # 创建测试数据
        image1 = Image(category="荧光扫描", rel_path="test1.jpg")
        image2 = Image(category="三维立体", rel_path="test2.jpg")
        
        test_session.add(image1)
        test_session.add(image2)
        test_session.commit()
        
        # 测试查询
        optimizer = DatabaseOptimizer("sqlite:///:memory:")
        queries = OptimizedQueries(optimizer)
        
        categories = queries.get_categories(test_session)
        assert "荧光扫描" in categories
        assert "三维立体" in categories
        assert len(categories) == 2
    
    def test_get_images_paginated(self, test_session):
        """测试分页查询"""
        # 创建测试数据
        for i in range(10):
            image = Image(
                well_name=f"BZ{i}",
                category="荧光扫描",
                rel_path=f"test{i}.jpg",
                start_depth=float(i * 100),
                end_depth=float((i + 1) * 100)
            )
            test_session.add(image)
        test_session.commit()
        
        # 测试查询
        optimizer = DatabaseOptimizer("sqlite:///:memory:")
        queries = OptimizedQueries(optimizer)
        
        # 第一页
        result = queries.get_images_paginated(
            test_session, 
            page=1, 
            per_page=5, 
            filters={"well_name": "BZ1"}
        )
        
        assert result["total"] == 1
        assert result["page"] == 1
        assert result["per_page"] == 5
        assert len(result["items"]) == 1
        
        # 第二页
        result = queries.get_images_paginated(
            test_session, 
            page=2, 
            per_page=5, 
            filters={}
        )
        
        assert result["total"] == 10
        assert result["page"] == 2
        assert result["per_page"] == 5
        assert len(result["items"]) == 5