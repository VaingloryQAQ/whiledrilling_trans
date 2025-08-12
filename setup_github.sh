#!/bin/bash

# GitHub仓库自动设置脚本
# 自动创建GitHub仓库并上传除了data目录以外的所有代码文件

echo "🔧 GitHub仓库自动设置工具"
echo "================================"

# 检查Git是否安装
if ! command -v git &> /dev/null; then
    echo "❌ Git未安装，请先安装Git"
    exit 1
fi

# 检查是否在正确的目录
if [ ! -f "requirements.txt" ] || [ ! -f "app/main.py" ]; then
    echo "❌ 请在项目根目录运行此脚本"
    exit 1
fi

echo "✅ 项目结构检查通过"

# 创建.gitignore文件
echo "📝 创建 .gitignore 文件..."
cat > .gitignore << 'EOF'
# Python
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
EOF

# 创建README.md文件
echo "📝 创建 README.md 文件..."
cat > README.md << 'EOF'
# 钻井数据智能分析系统

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
EOF

# 初始化Git仓库（如果还没有）
if [ ! -d ".git" ]; then
    echo "📁 初始化Git仓库..."
    git init
fi

# 添加所有文件
echo "📤 添加文件到Git..."
git add .

# 提交初始代码
echo "💾 提交初始代码..."
git commit -m "Initial commit: 钻井数据智能分析系统"

echo ""
echo "=================================================="
echo "🎉 本地Git仓库设置完成！"
echo ""
echo "接下来需要手动创建GitHub仓库："
echo "1. 访问 https://github.com/new"
echo "2. 创建新仓库（建议名称：whiledrilling_trans）"
echo "3. 不要初始化README、.gitignore或license"
echo "4. 创建后，运行以下命令推送代码："
echo ""
echo "   git remote add origin https://github.com/YOUR_USERNAME/REPO_NAME.git"
echo "   git branch -M main"
echo "   git push -u origin main"
echo ""
echo "=================================================="
