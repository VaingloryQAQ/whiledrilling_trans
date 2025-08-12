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
