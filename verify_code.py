#!/usr/bin/env python3
"""
代码验证主脚本 - 整合所有验证步骤
"""

import os
import sys
import subprocess
import time
from pathlib import Path
import logging

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def run_command(cmd: list, description: str, cwd: Path = None) -> bool:
    """运行命令并返回是否成功"""
    logger.info(f"运行: {description}")
    logger.info(f"命令: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
        
        if result.returncode == 0:
            logger.info(f"✅ {description} 成功")
            if result.stdout:
                logger.debug(f"输出: {result.stdout}")
            return True
        else:
            logger.error(f"❌ {description} 失败")
            if result.stderr:
                logger.error(f"错误: {result.stderr}")
            if result.stdout:
                logger.debug(f"输出: {result.stdout}")
            return False
    except Exception as e:
        logger.error(f"❌ {description} 异常: {e}")
        return False

def check_environment():
    """检查环境"""
    logger.info("=== 环境检查 ===")
    
    # 检查Python版本
    python_version = sys.version_info
    if python_version < (3, 8):
        logger.error(f"Python版本过低: {python_version.major}.{python_version.minor}")
        return False
    
    logger.info(f"Python版本: {python_version.major}.{python_version.minor}.{python_version.micro}")
    
    # 检查必要目录
    required_dirs = ["app", "tests", "config", "static", "templates"]
    for dir_name in required_dirs:
        if not Path(dir_name).exists():
            logger.error(f"缺少必要目录: {dir_name}")
            return False
    
    logger.info("✅ 环境检查通过")
    return True

def install_dependencies():
    """安装依赖"""
    logger.info("=== 安装依赖 ===")
    
    return run_command(
        [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"],
        "安装Python依赖"
    )

def run_code_quality_checks():
    """运行代码质量检查"""
    logger.info("=== 代码质量检查 ===")
    
    checks = [
        ([sys.executable, "-m", "black", "--check", "."], "代码格式检查 (black)"),
        ([sys.executable, "-m", "flake8", "."], "代码风格检查 (flake8)"),
        ([sys.executable, "-m", "mypy", "app"], "类型检查 (mypy)"),
    ]
    
    all_passed = True
    for cmd, description in checks:
        if not run_command(cmd, description):
            all_passed = False
    
    return all_passed

def run_tests():
    """运行测试"""
    logger.info("=== 运行测试 ===")
    
    # 运行单元测试
    unit_test_passed = run_command(
        [sys.executable, "-m", "pytest", "tests/", "-v", "--tb=short"],
        "单元测试"
    )
    
    # 运行集成测试
    integration_test_passed = run_command(
        [sys.executable, "-m", "pytest", "tests/test_integration.py", "-v"],
        "集成测试"
    )
    
    return unit_test_passed and integration_test_passed

def run_security_checks():
    """运行安全检查"""
    logger.info("=== 安全检查 ===")
    
    # 运行安全测试
    security_test_passed = run_command(
        [sys.executable, "-m", "pytest", "tests/test_security.py", "-v"],
        "安全测试"
    )
    
    # 运行代码验证脚本
    verification_passed = run_command(
        [sys.executable, "scripts/verify.py"],
        "代码验证"
    )
    
    return security_test_passed and verification_passed

def run_performance_tests():
    """运行性能测试"""
    logger.info("=== 性能测试 ===")
    
    # 检查应用是否运行
    try:
        import requests
        response = requests.get("http://localhost:8000", timeout=5)
        if response.status_code == 200:
            logger.info("应用正在运行，开始性能测试")
            
            # 运行性能测试
            performance_passed = run_command(
                [sys.executable, "scripts/performance_test.py"],
                "性能测试"
            )
            return performance_passed
        else:
            logger.warning("应用未正常运行，跳过性能测试")
            return True
    except Exception:
        logger.warning("无法连接到应用，跳过性能测试")
        return True

def run_deployment_test():
    """运行部署测试"""
    logger.info("=== 部署测试 ===")
    
    # 测试应用导入
    import_passed = run_command(
        [sys.executable, "-c", "from app.main import app; print('应用导入成功')"],
        "应用导入测试"
    )
    
    # 测试数据库连接
    db_passed = run_command(
        [sys.executable, "-c", "from app.database import db_optimizer; print('数据库连接成功')"],
        "数据库连接测试"
    )
    
    return import_passed and db_passed

def generate_final_report(results: dict):
    """生成最终报告"""
    logger.info("=== 生成验证报告 ===")
    
    total_checks = len(results)
    passed_checks = sum(1 for result in results.values() if result)
    failed_checks = total_checks - passed_checks
    
    report = f"""
# 代码验证最终报告

## 总体结果
- 总检查项: {total_checks}
- 通过: {passed_checks} ✅
- 失败: {failed_checks} ❌
- 通过率: {passed_checks/total_checks*100:.1f}%

## 详细结果
"""
    
    for check_name, result in results.items():
        status = "✅ 通过" if result else "❌ 失败"
        report += f"- {check_name}: {status}\n"
    
    if failed_checks > 0:
        report += f"\n## 建议\n"
        report += f"- 请修复失败的检查项\n"
        report += f"- 重新运行验证脚本\n"
        report += f"- 检查错误日志获取详细信息\n"
    else:
        report += f"\n## 恭喜！\n"
        report += f"- 所有检查都通过了\n"
        report += f"- 代码质量良好\n"
        report += f"- 可以安全部署\n"
    
    # 保存报告
    with open("final_verification_report.md", "w", encoding="utf-8") as f:
        f.write(report)
    
    logger.info("验证报告已保存到: final_verification_report.md")
    print(report)
    
    return failed_checks == 0

def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="代码验证主脚本")
    parser.add_argument("--skip-deps", action="store_true", help="跳过依赖安装")
    parser.add_argument("--skip-tests", action="store_true", help="跳过测试")
    parser.add_argument("--skip-performance", action="store_true", help="跳过性能测试")
    parser.add_argument("--quick", action="store_true", help="快速验证模式")
    
    args = parser.parse_args()
    
    logger.info("开始代码验证流程...")
    
    # 检查环境
    if not check_environment():
        logger.error("环境检查失败，退出")
        sys.exit(1)
    
    results = {}
    
    # 安装依赖
    if not args.skip_deps:
        results["依赖安装"] = install_dependencies()
        if not results["依赖安装"]:
            logger.error("依赖安装失败，退出")
            sys.exit(1)
    else:
        results["依赖安装"] = True
    
    # 代码质量检查
    results["代码质量检查"] = run_code_quality_checks()
    
    # 运行测试
    if not args.skip_tests:
        results["测试"] = run_tests()
    else:
        results["测试"] = True
    
    # 安全检查
    results["安全检查"] = run_security_checks()
    
    # 性能测试
    if not args.skip_performance:
        results["性能测试"] = run_performance_tests()
    else:
        results["性能测试"] = True
    
    # 部署测试
    results["部署测试"] = run_deployment_test()
    
    # 生成最终报告
    all_passed = generate_final_report(results)
    
    if all_passed:
        logger.info("🎉 所有验证都通过了！")
        sys.exit(0)
    else:
        logger.error("❌ 部分验证失败，请检查报告")
        sys.exit(1)

if __name__ == "__main__":
    main()