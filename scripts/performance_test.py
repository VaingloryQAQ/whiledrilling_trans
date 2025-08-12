#!/usr/bin/env python3
"""
性能测试脚本 - 测试系统性能指标
"""

import time
import threading
import requests
import statistics
from pathlib import Path
import logging
from typing import Dict, List, Tuple
import json

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class PerformanceTester:
    """性能测试器"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.results = {}
        
    def test_response_time(self, endpoint: str, method: str = "GET", 
                          params: Dict = None, data: Dict = None) -> Dict:
        """测试响应时间"""
        url = f"{self.base_url}{endpoint}"
        
        try:
            start_time = time.time()
            if method.upper() == "GET":
                response = requests.get(url, params=params, timeout=30)
            elif method.upper() == "POST":
                response = requests.post(url, json=data, timeout=30)
            else:
                raise ValueError(f"不支持的HTTP方法: {method}")
            
            end_time = time.time()
            response_time = end_time - start_time
            
            return {
                "status_code": response.status_code,
                "response_time": response_time,
                "success": response.status_code < 400
            }
        except Exception as e:
            logger.error(f"请求失败 {endpoint}: {e}")
            return {
                "status_code": None,
                "response_time": None,
                "success": False,
                "error": str(e)
            }
    
    def test_concurrent_requests(self, endpoint: str, num_requests: int = 10, 
                                method: str = "GET", params: Dict = None) -> Dict:
        """测试并发请求"""
        results = []
        errors = []
        
        def make_request():
            try:
                result = self.test_response_time(endpoint, method, params)
                results.append(result)
            except Exception as e:
                errors.append(str(e))
        
        # 创建线程
        threads = []
        for i in range(num_requests):
            thread = threading.Thread(target=make_request)
            threads.append(thread)
        
        # 启动所有线程
        start_time = time.time()
        for thread in threads:
            thread.start()
        
        # 等待所有线程完成
        for thread in threads:
            thread.join()
        end_time = time.time()
        
        total_time = end_time - start_time
        
        # 分析结果
        successful_requests = [r for r in results if r["success"]]
        failed_requests = [r for r in results if not r["success"]]
        
        if successful_requests:
            response_times = [r["response_time"] for r in successful_requests]
            avg_response_time = statistics.mean(response_times)
            min_response_time = min(response_times)
            max_response_time = max(response_times)
            std_response_time = statistics.stdev(response_times) if len(response_times) > 1 else 0
        else:
            avg_response_time = min_response_time = max_response_time = std_response_time = 0
        
        return {
            "total_requests": num_requests,
            "successful_requests": len(successful_requests),
            "failed_requests": len(failed_requests),
            "success_rate": len(successful_requests) / num_requests * 100,
            "total_time": total_time,
            "requests_per_second": num_requests / total_time,
            "avg_response_time": avg_response_time,
            "min_response_time": min_response_time,
            "max_response_time": max_response_time,
            "std_response_time": std_response_time,
            "errors": errors
        }
    
    def test_database_performance(self) -> Dict:
        """测试数据库性能"""
        results = {}
        
        # 测试井名查询性能
        logger.info("测试井名查询性能...")
        well_query_result = self.test_concurrent_requests("/api/wells", num_requests=20)
        results["well_query"] = well_query_result
        
        # 测试带参数的井名查询
        logger.info("测试带参数的井名查询性能...")
        well_query_with_params = self.test_concurrent_requests(
            "/api/wells", num_requests=20, params={"q": "BZ"}
        )
        results["well_query_with_params"] = well_query_with_params
        
        return results
    
    def test_file_operations(self) -> Dict:
        """测试文件操作性能"""
        results = {}
        
        # 测试静态文件访问
        logger.info("测试静态文件访问性能...")
        static_file_result = self.test_concurrent_requests("/static/styles.css", num_requests=10)
        results["static_file_access"] = static_file_result
        
        # 测试favicon访问
        logger.info("测试favicon访问性能...")
        favicon_result = self.test_concurrent_requests("/favicon.ico", num_requests=10)
        results["favicon_access"] = favicon_result
        
        return results
    
    def test_page_load_performance(self) -> Dict:
        """测试页面加载性能"""
        results = {}
        
        # 测试主页加载
        logger.info("测试主页加载性能...")
        home_page_result = self.test_concurrent_requests("/", num_requests=10)
        results["home_page"] = home_page_result
        
        # 测试上传页面加载
        logger.info("测试上传页面加载性能...")
        upload_page_result = self.test_concurrent_requests("/upload", num_requests=10)
        results["upload_page"] = upload_page_result
        
        # 测试画廊页面加载
        logger.info("测试画廊页面加载性能...")
        gallery_page_result = self.test_concurrent_requests("/gallery", num_requests=10)
        results["gallery_page"] = gallery_page_result
        
        # 测试分组页面加载
        logger.info("测试分组页面加载性能...")
        grouped_page_result = self.test_concurrent_requests("/grouped", num_requests=10)
        results["grouped_page"] = grouped_page_result
        
        return results
    
    def test_api_performance(self) -> Dict:
        """测试API性能"""
        results = {}
        
        # 测试各种API端点
        api_endpoints = [
            "/api/wells",
            "/api/wells?q=BZ",
            "/api/wells?q=LK",
        ]
        
        for endpoint in api_endpoints:
            logger.info(f"测试API性能: {endpoint}")
            result = self.test_concurrent_requests(endpoint, num_requests=15)
            results[endpoint] = result
        
        return results
    
    def test_memory_usage(self) -> Dict:
        """测试内存使用情况"""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        memory_info = process.memory_info()
        
        return {
            "rss_memory_mb": memory_info.rss / 1024 / 1024,
            "vms_memory_mb": memory_info.vms / 1024 / 1024,
            "percent_memory": process.memory_percent(),
            "cpu_percent": process.cpu_percent(),
            "num_threads": process.num_threads(),
        }
    
    def run_all_tests(self) -> Dict:
        """运行所有性能测试"""
        logger.info("开始性能测试...")
        
        all_results = {}
        
        # 测试数据库性能
        logger.info("=== 数据库性能测试 ===")
        all_results["database"] = self.test_database_performance()
        
        # 测试文件操作性能
        logger.info("=== 文件操作性能测试 ===")
        all_results["file_operations"] = self.test_file_operations()
        
        # 测试页面加载性能
        logger.info("=== 页面加载性能测试 ===")
        all_results["page_load"] = self.test_page_load_performance()
        
        # 测试API性能
        logger.info("=== API性能测试 ===")
        all_results["api"] = self.test_api_performance()
        
        # 测试内存使用
        logger.info("=== 内存使用测试 ===")
        all_results["memory"] = self.test_memory_usage()
        
        self.results = all_results
        return all_results
    
    def generate_report(self) -> str:
        """生成性能测试报告"""
        if not self.results:
            return "没有测试结果"
        
        report = "# 性能测试报告\n\n"
        
        # 总体统计
        total_requests = 0
        total_successful = 0
        total_failed = 0
        all_response_times = []
        
        for category, tests in self.results.items():
            if category == "memory":
                continue
                
            for test_name, result in tests.items():
                if isinstance(result, dict) and "total_requests" in result:
                    total_requests += result["total_requests"]
                    total_successful += result["successful_requests"]
                    total_failed += result["failed_requests"]
                    
                    if "avg_response_time" in result and result["avg_response_time"]:
                        all_response_times.append(result["avg_response_time"])
        
        if all_response_times:
            overall_avg_response_time = statistics.mean(all_response_times)
            overall_min_response_time = min(all_response_times)
            overall_max_response_time = max(all_response_times)
        else:
            overall_avg_response_time = overall_min_response_time = overall_max_response_time = 0
        
        report += f"## 总体统计\n"
        report += f"- 总请求数: {total_requests}\n"
        report += f"- 成功请求: {total_successful}\n"
        report += f"- 失败请求: {total_failed}\n"
        report += f"- 成功率: {total_successful/total_requests*100:.1f}%\n"
        report += f"- 平均响应时间: {overall_avg_response_time:.3f}秒\n"
        report += f"- 最小响应时间: {overall_min_response_time:.3f}秒\n"
        report += f"- 最大响应时间: {overall_max_response_time:.3f}秒\n\n"
        
        # 详细结果
        for category, tests in self.results.items():
            report += f"## {category.title()}\n\n"
            
            if category == "memory":
                # 内存使用情况
                for metric, value in tests.items():
                    if "memory" in metric or "percent" in metric:
                        report += f"- {metric}: {value:.2f}\n"
                    else:
                        report += f"- {metric}: {value}\n"
            else:
                # 性能测试结果
                for test_name, result in tests.items():
                    if isinstance(result, dict) and "total_requests" in result:
                        report += f"### {test_name}\n"
                        report += f"- 总请求数: {result['total_requests']}\n"
                        report += f"- 成功请求: {result['successful_requests']}\n"
                        report += f"- 失败请求: {result['failed_requests']}\n"
                        report += f"- 成功率: {result['success_rate']:.1f}%\n"
                        report += f"- 平均响应时间: {result['avg_response_time']:.3f}秒\n"
                        report += f"- 最小响应时间: {result['min_response_time']:.3f}秒\n"
                        report += f"- 最大响应时间: {result['max_response_time']:.3f}秒\n"
                        report += f"- 每秒请求数: {result['requests_per_second']:.2f}\n"
                        
                        if result['errors']:
                            report += f"- 错误: {len(result['errors'])}个\n"
                        
                        report += "\n"
        
        # 性能评估
        report += "## 性能评估\n\n"
        
        if overall_avg_response_time < 0.1:
            report += "✅ 响应时间优秀 (< 100ms)\n"
        elif overall_avg_response_time < 0.5:
            report += "✅ 响应时间良好 (< 500ms)\n"
        elif overall_avg_response_time < 1.0:
            report += "⚠️ 响应时间一般 (< 1s)\n"
        else:
            report += "❌ 响应时间较差 (> 1s)\n"
        
        if total_successful / total_requests > 0.95:
            report += "✅ 成功率优秀 (> 95%)\n"
        elif total_successful / total_requests > 0.9:
            report += "✅ 成功率良好 (> 90%)\n"
        elif total_successful / total_requests > 0.8:
            report += "⚠️ 成功率一般 (> 80%)\n"
        else:
            report += "❌ 成功率较差 (< 80%)\n"
        
        return report
    
    def save_report(self, report: str, output_file: str = "performance_report.md"):
        """保存性能测试报告"""
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(report)
        logger.info(f"性能测试报告已保存到: {output_file}")

def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="性能测试脚本")
    parser.add_argument("--url", default="http://localhost:8000", help="应用URL")
    parser.add_argument("--output", default="performance_report.md", help="输出报告文件")
    parser.add_argument("--test", choices=["database", "file", "page", "api", "memory", "all"], 
                       default="all", help="要运行的测试类型")
    
    args = parser.parse_args()
    
    tester = PerformanceTester(args.url)
    
    try:
        if args.test == "all":
            results = tester.run_all_tests()
        elif args.test == "database":
            results = {"database": tester.test_database_performance()}
        elif args.test == "file":
            results = {"file_operations": tester.test_file_operations()}
        elif args.test == "page":
            results = {"page_load": tester.test_page_load_performance()}
        elif args.test == "api":
            results = {"api": tester.test_api_performance()}
        elif args.test == "memory":
            results = {"memory": tester.test_memory_usage()}
        
        # 生成报告
        report = tester.generate_report()
        print(report)
        
        # 保存报告
        tester.save_report(report, args.output)
        
    except KeyboardInterrupt:
        logger.info("测试被用户中断")
    except Exception as e:
        logger.error(f"性能测试失败: {e}")
        raise

if __name__ == "__main__":
    main()