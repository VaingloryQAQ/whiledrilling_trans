#!/usr/bin/env python3
"""
代码验证脚本 - 全面的代码质量检查和验证
"""

import os
import sys
import subprocess
import time
import json
from pathlib import Path
import logging
from typing import Dict, List, Tuple

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class CodeVerifier:
    """代码验证器"""
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.results = {}
        
    def run_all_checks(self) -> Dict[str, bool]:
        """运行所有检查"""
        logger.info("开始代码验证...")
        
        checks = [
            ("代码格式检查", self.check_code_format),
            ("语法检查", self.check_syntax),
            ("导入检查", self.check_imports),
            ("安全漏洞检查", self.check_security),
            ("单元测试", self.run_unit_tests),
            ("集成测试", self.run_integration_tests),
            ("性能测试", self.run_performance_tests),
            ("文档检查", self.check_documentation),
            ("配置检查", self.check_configuration),
            ("依赖检查", self.check_dependencies),
        ]
        
        for check_name, check_func in checks:
            try:
                logger.info(f"运行 {check_name}...")
                result = check_func()
                self.results[check_name] = result
                status = "✅ 通过" if result else "❌ 失败"
                logger.info(f"{check_name}: {status}")
            except Exception as e:
                logger.error(f"{check_name} 出错: {e}")
                self.results[check_name] = False
        
        return self.results
    
    def check_code_format(self) -> bool:
        """检查代码格式"""
        try:
            # 检查Python文件格式
            python_files = list(self.project_root.rglob("*.py"))
            
            # 使用black检查格式
            result = subprocess.run([
                sys.executable, "-m", "black", "--check", "--diff", str(self.project_root)
            ], capture_output=True, text=True)
            
            if result.returncode != 0:
                logger.warning("代码格式不符合black标准")
                logger.warning(result.stdout)
                return False
            
            # 检查flake8
            result = subprocess.run([
                sys.executable, "-m", "flake8", str(self.project_root)
            ], capture_output=True, text=True)
            
            if result.returncode != 0:
                logger.warning("代码风格检查失败")
                logger.warning(result.stdout)
                return False
            
            return True
        except Exception as e:
            logger.error(f"代码格式检查失败: {e}")
            return False
    
    def check_syntax(self) -> bool:
        """检查语法错误"""
        try:
            python_files = list(self.project_root.rglob("*.py"))
            errors = []
            
            for py_file in python_files:
                try:
                    with open(py_file, 'r', encoding='utf-8') as f:
                        compile(f.read(), py_file, 'exec')
                except SyntaxError as e:
                    errors.append(f"{py_file}: {e}")
            
            if errors:
                logger.error("发现语法错误:")
                for error in errors:
                    logger.error(f"  {error}")
                return False
            
            return True
        except Exception as e:
            logger.error(f"语法检查失败: {e}")
            return False
    
    def check_imports(self) -> bool:
        """检查导入错误"""
        try:
            # 检查app模块的导入
            app_dir = self.project_root / "app"
            if app_dir.exists():
                result = subprocess.run([
                    sys.executable, "-c", "import app"
                ], capture_output=True, text=True, cwd=self.project_root)
                
                if result.returncode != 0:
                    logger.error("app模块导入失败:")
                    logger.error(result.stderr)
                    return False
            
            return True
        except Exception as e:
            logger.error(f"导入检查失败: {e}")
            return False
    
    def check_security(self) -> bool:
        """检查安全漏洞"""
        try:
            # 检查常见安全问题的模式
            security_patterns = [
                (r"eval\(", "使用eval()函数"),
                (r"exec\(", "使用exec()函数"),
                (r"os\.system\(", "使用os.system()"),
                (r"subprocess\.call\(", "使用subprocess.call()"),
                (r"\.\./", "路径遍历"),
                (r"SELECT.*FROM", "SQL注入风险"),
                (r"password.*=.*['\"]", "硬编码密码"),
            ]
            
            python_files = list(self.project_root.rglob("*.py"))
            issues = []
            
            for py_file in python_files:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    for pattern, description in security_patterns:
                        import re
                        if re.search(pattern, content, re.IGNORECASE):
                            issues.append(f"{py_file}: {description}")
            
            if issues:
                logger.warning("发现潜在安全问题:")
                for issue in issues:
                    logger.warning(f"  {issue}")
                return False
            
            return True
        except Exception as e:
            logger.error(f"安全检查失败: {e}")
            return False
    
    def run_unit_tests(self) -> bool:
        """运行单元测试"""
        try:
            test_dir = self.project_root / "tests"
            if not test_dir.exists():
                logger.warning("未找到测试目录")
                return True
            
            result = subprocess.run([
                sys.executable, "-m", "pytest", str(test_dir), "-v", "--tb=short"
            ], capture_output=True, text=True, cwd=self.project_root)
            
            if result.returncode != 0:
                logger.error("单元测试失败:")
                logger.error(result.stdout)
                logger.error(result.stderr)
                return False
            
            logger.info("单元测试通过")
            return True
        except Exception as e:
            logger.error(f"单元测试失败: {e}")
            return False
    
    def run_integration_tests(self) -> bool:
        """运行集成测试"""
        try:
            # 检查应用是否能正常启动
            result = subprocess.run([
                sys.executable, "-c", "from app.main import app; print('App imported successfully')"
            ], capture_output=True, text=True, cwd=self.project_root)
            
            if result.returncode != 0:
                logger.error("应用导入失败:")
                logger.error(result.stderr)
                return False
            
            logger.info("集成测试通过")
            return True
        except Exception as e:
            logger.error(f"集成测试失败: {e}")
            return False
    
    def run_performance_tests(self) -> bool:
        """运行性能测试"""
        try:
            # 简单的性能测试：检查导入时间
            start_time = time.time()
            result = subprocess.run([
                sys.executable, "-c", "import app"
            ], capture_output=True, text=True, cwd=self.project_root)
            import_time = time.time() - start_time
            
            if import_time > 5.0:  # 导入时间超过5秒
                logger.warning(f"应用导入时间过长: {import_time:.2f}秒")
                return False
            
            logger.info(f"性能测试通过 (导入时间: {import_time:.2f}秒)")
            return True
        except Exception as e:
            logger.error(f"性能测试失败: {e}")
            return False
    
    def check_documentation(self) -> bool:
        """检查文档"""
        try:
            required_files = [
                "README.md",
                "requirements.txt",
            ]
            
            missing_files = []
            for file_name in required_files:
                if not (self.project_root / file_name).exists():
                    missing_files.append(file_name)
            
            if missing_files:
                logger.warning(f"缺少文档文件: {missing_files}")
                return False
            
            # 检查README内容
            readme_file = self.project_root / "README.md"
            with open(readme_file, 'r', encoding='utf-8') as f:
                content = f.read()
                
            required_sections = ["项目简介", "安装", "使用"]
            missing_sections = []
            for section in required_sections:
                if section not in content:
                    missing_sections.append(section)
            
            if missing_sections:
                logger.warning(f"README缺少必要章节: {missing_sections}")
                return False
            
            return True
        except Exception as e:
            logger.error(f"文档检查失败: {e}")
            return False
    
    def check_configuration(self) -> bool:
        """检查配置"""
        try:
            # 检查配置文件
            config_files = [
                "config/app.yaml",
                "config/rules.yaml",
            ]
            
            for config_file in config_files:
                config_path = self.project_root / config_file
                if not config_path.exists():
                    logger.warning(f"缺少配置文件: {config_file}")
                    return False
            
            # 检查环境变量配置
            env_file = self.project_root / ".env"
            if not env_file.exists():
                logger.warning("缺少.env配置文件")
                return False
            
            return True
        except Exception as e:
            logger.error(f"配置检查失败: {e}")
            return False
    
    def check_dependencies(self) -> bool:
        """检查依赖"""
        try:
            requirements_file = self.project_root / "requirements.txt"
            if not requirements_file.exists():
                logger.error("缺少requirements.txt文件")
                return False
            
            # 检查依赖是否可以安装
            result = subprocess.run([
                sys.executable, "-m", "pip", "check"
            ], capture_output=True, text=True)
            
            if result.returncode != 0:
                logger.error("依赖检查失败:")
                logger.error(result.stdout)
                return False
            
            return True
        except Exception as e:
            logger.error(f"依赖检查失败: {e}")
            return False
    
    def generate_report(self) -> str:
        """生成验证报告"""
        total_checks = len(self.results)
        passed_checks = sum(1 for result in self.results.values() if result)
        failed_checks = total_checks - passed_checks
        
        report = f"""
# 代码验证报告

## 总体结果
- 总检查项: {total_checks}
- 通过: {passed_checks} ✅
- 失败: {failed_checks} ❌
- 通过率: {passed_checks/total_checks*100:.1f}%

## 详细结果
"""
        
        for check_name, result in self.results.items():
            status = "✅ 通过" if result else "❌ 失败"
            report += f"- {check_name}: {status}\n"
        
        if failed_checks > 0:
            report += f"\n## 建议\n"
            report += f"- 请修复失败的检查项\n"
            report += f"- 重新运行验证脚本\n"
        
        return report
    
    def save_report(self, report: str, output_file: str = "verification_report.md"):
        """保存验证报告"""
        report_path = self.project_root / output_file
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report)
        logger.info(f"验证报告已保存到: {report_path}")

def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="代码验证脚本")
    parser.add_argument("--project-root", type=Path, default=Path("."), help="项目根目录")
    parser.add_argument("--output", type=str, default="verification_report.md", help="输出报告文件")
    parser.add_argument("--check", type=str, help="只运行特定检查")
    
    args = parser.parse_args()
    
    verifier = CodeVerifier(args.project_root)
    
    if args.check:
        # 运行特定检查
        check_func = getattr(verifier, f"check_{args.check}", None)
        if check_func:
            result = check_func()
            status = "通过" if result else "失败"
            logger.info(f"{args.check}: {status}")
        else:
            logger.error(f"未知的检查项: {args.check}")
            sys.exit(1)
    else:
        # 运行所有检查
        results = verifier.run_all_checks()
        
        # 生成报告
        report = verifier.generate_report()
        print(report)
        
        # 保存报告
        verifier.save_report(report, args.output)
        
        # 如果有失败的检查，退出码为1
        if any(not result for result in results.values()):
            sys.exit(1)

if __name__ == "__main__":
    main()