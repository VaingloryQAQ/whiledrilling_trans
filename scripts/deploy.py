#!/usr/bin/env python3
"""
部署脚本 - 自动化部署和配置检查
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path
import logging

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class Deployer:
    """部署器"""
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.app_dir = project_root / "app"
        self.data_dir = project_root / "data"
        self.static_dir = project_root / "static"
        
    def check_requirements(self):
        """检查部署要求"""
        logger.info("检查部署要求...")
        
        # 检查Python版本
        python_version = sys.version_info
        if python_version < (3, 8):
            raise RuntimeError(f"需要Python 3.8+，当前版本: {python_version.major}.{python_version.minor}")
        
        logger.info(f"Python版本: {python_version.major}.{python_version.minor}.{python_version.micro}")
        
        # 检查必要目录
        required_dirs = [self.app_dir, self.data_dir, self.static_dir]
        for dir_path in required_dirs:
            if not dir_path.exists():
                logger.info(f"创建目录: {dir_path}")
                dir_path.mkdir(parents=True, exist_ok=True)
        
        # 检查必要文件
        required_files = [
            self.project_root / "requirements.txt",
            self.app_dir / "main.py",
            self.project_root / "README.md"
        ]
        
        for file_path in required_files:
            if not file_path.exists():
                raise FileNotFoundError(f"缺少必要文件: {file_path}")
        
        logger.info("部署要求检查通过")
    
    def install_dependencies(self):
        """安装依赖"""
        logger.info("安装Python依赖...")
        
        requirements_file = self.project_root / "requirements.txt"
        if not requirements_file.exists():
            raise FileNotFoundError("requirements.txt 文件不存在")
        
        try:
            subprocess.run([
                sys.executable, "-m", "pip", "install", "-r", str(requirements_file)
            ], check=True, capture_output=True, text=True)
            logger.info("依赖安装完成")
        except subprocess.CalledProcessError as e:
            logger.error(f"依赖安装失败: {e.stderr}")
            raise
    
    def setup_database(self):
        """设置数据库"""
        logger.info("设置数据库...")
        
        # 确保数据目录存在
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # 初始化数据库
        try:
            subprocess.run([
                sys.executable, "-m", "app.ingest"
            ], check=True, capture_output=True, text=True)
            logger.info("数据库初始化完成")
        except subprocess.CalledProcessError as e:
            logger.warning(f"数据库初始化警告: {e.stderr}")
    
    def setup_permissions(self):
        """设置文件权限"""
        logger.info("设置文件权限...")
        
        # 设置数据目录权限
        for dir_path in [self.data_dir, self.data_dir / "uploads", self.data_dir / "cache"]:
            if dir_path.exists():
                try:
                    os.chmod(dir_path, 0o755)
                except Exception as e:
                    logger.warning(f"设置权限失败 {dir_path}: {e}")
    
    def create_config_files(self):
        """创建配置文件"""
        logger.info("创建配置文件...")
        
        # 创建.env文件模板
        env_template = """# 应用配置
DATABASE_URL=sqlite:///./data/images.db

# 安全配置
UPLOAD_MAX_SIZE=10485760
RATE_LIMIT_REQUESTS=100
RATE_LIMIT_WINDOW=60

# 性能配置
CACHE_MAX_SIZE=128
CACHE_TTL=300
DB_POOL_SIZE=10
DB_MAX_OVERFLOW=20

# 路径配置
BASE_DIR=.
DATA_DIR=./data
UPLOADS_DIR=./data/uploads
EXTRACTED_DIR=./data/extracted
THUMBS_DIR=./data/thumbs
CACHE_DIR=./data/cache
"""
        
        env_file = self.project_root / ".env"
        if not env_file.exists():
            with open(env_file, 'w', encoding='utf-8') as f:
                f.write(env_template)
            logger.info("创建.env配置文件")
    
    def run_tests(self):
        """运行测试"""
        logger.info("运行测试...")
        
        # 检查是否有测试文件
        test_dir = self.project_root / "tests"
        if test_dir.exists():
            try:
                subprocess.run([
                    sys.executable, "-m", "pytest", str(test_dir)
                ], check=True, capture_output=True, text=True)
                logger.info("测试通过")
            except subprocess.CalledProcessError as e:
                logger.warning(f"测试失败: {e.stderr}")
        else:
            logger.info("未找到测试文件，跳过测试")
    
    def start_application(self, host: str = "127.0.0.1", port: int = 8000):
        """启动应用"""
        logger.info(f"启动应用: http://{host}:{port}")
        
        try:
            subprocess.run([
                sys.executable, "-m", "uvicorn", "app.main:app",
                "--host", host, "--port", str(port), "--reload"
            ], check=True)
        except KeyboardInterrupt:
            logger.info("应用已停止")
        except subprocess.CalledProcessError as e:
            logger.error(f"应用启动失败: {e}")
            raise
    
    def deploy(self, start_app: bool = False):
        """执行完整部署"""
        logger.info("开始部署...")
        
        try:
            self.check_requirements()
            self.install_dependencies()
            self.setup_database()
            self.setup_permissions()
            self.create_config_files()
            self.run_tests()
            
            logger.info("部署完成!")
            
            if start_app:
                self.start_application()
                
        except Exception as e:
            logger.error(f"部署失败: {e}")
            raise

def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="钻井数据智能分析系统部署脚本")
    parser.add_argument("--start", action="store_true", help="部署后启动应用")
    parser.add_argument("--host", default="127.0.0.1", help="应用主机地址")
    parser.add_argument("--port", type=int, default=8000, help="应用端口")
    parser.add_argument("--project-root", type=Path, default=Path("."), help="项目根目录")
    
    args = parser.parse_args()
    
    deployer = Deployer(args.project_root)
    
    try:
        deployer.deploy(start_app=args.start)
    except Exception as e:
        logger.error(f"部署失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()