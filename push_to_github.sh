#!/bin/bash

# 快速推送到GitHub脚本

echo "🚀 快速推送到GitHub"
echo "=================="

# 检查是否已设置远程仓库
if ! git remote get-url origin &> /dev/null; then
    echo "❌ 未设置远程仓库"
    echo ""
    echo "请先创建GitHub仓库，然后运行："
    echo "git remote add origin https://github.com/YOUR_USERNAME/REPO_NAME.git"
    exit 1
fi

# 显示当前远程仓库
echo "📡 当前远程仓库："
git remote -v

echo ""
echo "📤 推送代码到GitHub..."

# 确保在main分支
git branch -M main

# 推送代码
git push -u origin main

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ 代码推送成功！"
    echo "🌐 访问您的GitHub仓库查看代码"
else
    echo ""
    echo "❌ 推送失败，请检查网络连接和GitHub权限"
fi
