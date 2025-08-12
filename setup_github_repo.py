#!/usr/bin/env python3
"""
GitHub仓库自动创建和代码上传脚本
自动创建GitHub仓库并上传除了data目录以外的所有代码文件
"""

import os
import subprocess
import sys
from pathlib import Path

def run_command(command, cwd=None):
    """执行命令并返回结果"""
    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True, cwd=cwd)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"命令执行失败: {command}")
        print(f"错误信息: {e.stderr}")
        return None

def create_gitignore():
    """创建.gitignore文件"""
    gitignore_content = """# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# 虚拟环境
venv/
env/
ENV/

# IDE
.vscode/
.idea/
*.swp
*.swo

# 系统文件
.DS_Store
Thumbs.db

# 日志文件
*.log
logs/

# 数据文件
data/
*.csv
*.xlsx
*.xls

# 临时文件
*.tmp
*.temp

# 配置文件（包含敏感信息）
.env
config/local.py

# 缓存
.cache/
"""
    
    with open('.gitignore', 'w', encoding='utf-8') as f:
        f.write(gitignore_content)
    print("✅ 已创建 .gitignore 文件")

def create_readme():
    """创建README.md文件"""
    readme_content = """# 钻井数据智能分析系统

## 项目简介

这是一个基于机器学习的钻井数据智能分析系统，能够自动学习和识别钻井井名规则，提供数据清洗、分析和可视化功能。

## 主要功能

- 🔍 **智能井名识别**: 基于机器学习的井名规则学习
- 📊 **数据清洗**: 自动数据清洗和标准化
- 📈 **数据分析**: 多维度数据分析和可视化
- 🌐 **Web界面**: 现代化的Web用户界面
- 🔧 **规则学习**: 自动学习和优化识别规则

## 技术栈

- **后端**: Python, FastAPI, SQLAlchemy
- **前端**: HTML, CSS, JavaScript
- **机器学习**: scikit-learn, pandas, numpy
- **数据库**: SQLite (可扩展)

## 快速开始

### 环境要求

- Python 3.8+
- pip

### 安装依赖

```bash
pip install -r requirements.txt
```

### 运行应用

```bash
python app/main.py
```

访问 http://localhost:8000 查看Web界面

## 项目结构

```
├── app/                    # 核心应用代码
│   ├── main.py            # 主应用入口
│   ├── rule_learner.py    # 规则学习模块
│   ├── csv_analyzer.py    # CSV分析器
│   └── ...
├── frontend/              # 前端资源
├── templates/             # HTML模板
├── static/                # 静态资源
├── config/                # 配置文件
└── requirements.txt       # Python依赖
```

## 使用说明

1. 将钻井数据CSV文件放入data目录
2. 运行应用进行数据分析和规则学习
3. 通过Web界面查看分析结果

## 贡献

欢迎提交Issue和Pull Request！

## 许可证

MIT License
"""
    
    with open('README.md', 'w', encoding='utf-8') as f:
        f.write(readme_content)
    print("✅ 已创建 README.md 文件")

def setup_github_repo():
    """设置GitHub仓库"""
    print("🚀 开始设置GitHub仓库...")
    
    # 检查是否已初始化Git
    if not os.path.exists('.git'):
        print("📁 初始化Git仓库...")
        run_command('git init')
    
    # 创建.gitignore和README
    create_gitignore()
    create_readme()
    
    # 添加所有文件（除了data目录）
    print("📤 添加文件到Git...")
    run_command('git add .')
    
    # 提交初始代码
    print("💾 提交初始代码...")
    run_command('git commit -m "Initial commit: 钻井数据智能分析系统"')
    
    print("\n" + "="*50)
    print("🎉 本地Git仓库设置完成！")
    print("\n接下来需要手动创建GitHub仓库：")
    print("1. 访问 https://github.com/new")
    print("2. 创建新仓库（建议名称：whiledrilling_trans）")
    print("3. 不要初始化README、.gitignore或license")
    print("4. 创建后，运行以下命令推送代码：")
    print("\n   git remote add origin https://github.com/YOUR_USERNAME/REPO_NAME.git")
    print("   git branch -M main")
    print("   git push -u origin main")
    print("\n" + "="*50)

def main():
    """主函数"""
    print("🔧 GitHub仓库自动设置工具")
    print("="*30)
    
    # 检查当前目录
    current_dir = Path.cwd()
    print(f"当前工作目录: {current_dir}")
    
    # 检查必要文件
    if not os.path.exists('requirements.txt'):
        print("❌ 未找到 requirements.txt 文件")
        return
    
    if not os.path.exists('app/main.py'):
        print("❌ 未找到 app/main.py 文件")
        return
    
    print("✅ 项目结构检查通过")
    
    # 设置GitHub仓库
    setup_github_repo()

if __name__ == "__main__":
    main()
