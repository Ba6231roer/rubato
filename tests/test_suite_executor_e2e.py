"""
Test Suite Executor E2E 测试脚本

该脚本用于自动化测试 test-suite-executor 角色的功能：
1. 启动 Web 服务
2. 通过 WebSocket 连接服务
3. 切换角色到 test-suite-executor
4. 执行测试案例集
5. 记录和验证测试结果
"""

import asyncio
import subprocess
import time
import sys
import os
from pathlib import Path
import websockets
import json
import signal


class TestSuiteExecutorE2E:
    """Test Suite Executor E2E 测试类"""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.venv_python = self.project_root / "venv" / "Scripts" / "python.exe"
        self.server_process = None
        self.ws_uri = "ws://127.0.0.1:8000/ws"
        self.test_case_dir = str(self.project_root / "test_case_path" / "test-suite-executor-testdata")
        
    def log(self, message: str, level: str = "INFO"):
        """打印日志"""
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] [{level}] {message}")
    
    def start_web_server(self) -> bool:
        """启动 Web 服务"""
        self.log("正在启动 Web 服务...")
        
        if not self.venv_python.exists():
            self.log(f"虚拟环境 Python 不存在: {self.venv_python}", "ERROR")
            return False
        
        try:
            env = os.environ.copy()
            env["PYTHONPATH"] = str(self.project_root)
            
            self.server_process = subprocess.Popen(
                [str(self.venv_python), "-m", "src.main", "--web", "--port", "8000"],
                cwd=str(self.project_root),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            self.log(f"服务进程已启动 (PID: {self.server_process.pid})")
            
            for i in range(30):
                time.sleep(1)
                try:
                    import requests
                    response = requests.get("http://127.0.0.1:8000/", timeout=1)
                    if response.status_code == 200:
                        self.log("Web 服务启动成功")
                        return True
                except:
                    pass
                
                if self.server_process.poll() is not None:
                    stdout, stderr = self.server_process.communicate()
                    self.log(f"服务进程意外退出", "ERROR")
                    self.log(f"STDOUT: {stdout}", "ERROR")
                    self.log(f"STDERR: {stderr}", "ERROR")
                    return False
            
            self.log("服务启动超时", "ERROR")
            return False
            
        except Exception as e:
            self.log(f"启动服务失败: {e}", "ERROR")
            return False
    
    def stop_web_server(self):
        """停止 Web 服务"""
        if self.server_process:
            self.log("正在停止 Web 服务...")
            try:
                self.server_process.terminate()
                self.server_process.wait(timeout=5)
                self.log("Web 服务已停止")
            except subprocess.TimeoutExpired:
                self.log("强制终止服务进程", "WARNING")
                self.server_process.kill()
            except Exception as e:
                self.log(f"停止服务失败: {e}", "ERROR")
    
    async def send_command(self, websocket, command: str) -> dict:
        """发送命令并等待响应"""
        self.log(f"发送命令: {command}")
        
        message = {
            "type": "command",
            "content": command
        }
        
        await websocket.send(json.dumps(message))
        
        response = await websocket.recv()
        data = json.loads(response)
        
        self.log(f"收到响应: {data.get('type')}")
        return data
    
    async def send_task(self, websocket, task: str) -> str:
        """发送任务并收集完整响应"""
        self.log(f"发送任务: {task}")
        
        message = {
            "type": "task",
            "content": task
        }
        
        await websocket.send(json.dumps(message))
        
        full_response = ""
        chunk_count = 0
        
        while True:
            try:
                response = await websocket.recv()
                data = json.loads(response)
                msg_type = data.get("type")
                content = data.get("content", "")
                
                if msg_type == "chunk":
                    chunk_count += 1
                    full_response += content
                    if chunk_count % 10 == 0:
                        print(".", end="", flush=True)
                elif msg_type == "done":
                    print()
                    self.log(f"任务完成 (共 {chunk_count} 个响应块)")
                    break
                elif msg_type == "error":
                    print()
                    self.log(f"任务执行错误: {content}", "ERROR")
                    break
                else:
                    self.log(f"收到消息类型: {msg_type}")
                    
            except Exception as e:
                self.log(f"接收响应错误: {e}", "ERROR")
                break
        
        return full_response
    
    async def run_test(self) -> bool:
        """运行测试"""
        self.log("=" * 80)
        self.log("Test Suite Executor E2E 测试开始")
        self.log("=" * 80)
        
        try:
            self.log(f"连接 WebSocket: {self.ws_uri}")
            
            async with websockets.connect(self.ws_uri) as websocket:
                response = await websocket.recv()
                data = json.loads(response)
                self.log(f"连接成功: {data.get('content')}")
                
                self.log("\n" + "=" * 80)
                self.log("步骤 1: 切换角色到 test-suite-executor")
                self.log("=" * 80)
                
                result = await self.send_command(websocket, "/role test-suite-executor")
                
                if result.get("type") == "error":
                    self.log("角色切换失败", "ERROR")
                    return False
                
                role_info = result.get("content", {})
                self.log(f"角色切换成功: {role_info.get('role_name', 'unknown')}")
                
                await asyncio.sleep(2)
                
                self.log("\n" + "=" * 80)
                self.log("步骤 2: 执行测试案例集")
                self.log("=" * 80)
                
                task = f"请执行 {self.test_case_dir} 目录下的所有测试案例"
                
                full_response = await self.send_task(websocket, task)
                
                self.log("\n" + "=" * 80)
                self.log("步骤 3: 验证测试结果")
                self.log("=" * 80)
                
                validation_results = self.validate_response(full_response)
                
                self.log("\n" + "=" * 80)
                self.log("测试结果汇总")
                self.log("=" * 80)
                
                for check, passed in validation_results.items():
                    status = "✓ 通过" if passed else "✗ 失败"
                    self.log(f"{status} - {check}")
                
                all_passed = all(validation_results.values())
                
                if all_passed:
                    self.log("\n所有验证点通过！", "INFO")
                else:
                    self.log("\n部分验证点失败", "WARNING")
                
                self.log("\n" + "=" * 80)
                self.log("完整响应内容")
                self.log("=" * 80)
                print(full_response)
                
                return all_passed
                
        except Exception as e:
            self.log(f"测试执行失败: {e}", "ERROR")
            import traceback
            traceback.print_exc()
            return False
    
    def validate_response(self, response: str) -> dict:
        """验证响应内容"""
        validation_results = {
            "包含测试案例集执行开始": "测试案例集执行开始" in response,
            "包含测试案例目录": "测试案例目录" in response or self.test_case_dir in response,
            "包含找到测试文件": "找到测试文件" in response or "测试文件" in response,
            "包含测试案例总数": "测试案例总数" in response or "总案例数" in response,
            "包含测试案例集执行汇总": "测试案例集执行汇总" in response or "执行汇总" in response,
            "包含通过数量": "通过" in response,
            "包含失败数量": "失败" in response or "错误" in response,
        }
        
        return validation_results
    
    def save_test_report(self, response: str, success: bool):
        """保存测试报告"""
        report_dir = self.project_root / "test_reports"
        report_dir.mkdir(exist_ok=True)
        
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        report_file = report_dir / f"test_suite_executor_e2e_{timestamp}.md"
        
        with open(report_file, "w", encoding="utf-8") as f:
            f.write("# Test Suite Executor E2E 测试报告\n\n")
            f.write(f"**测试时间**: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"**测试结果**: {'通过' if success else '失败'}\n\n")
            f.write("## 测试环境\n\n")
            f.write(f"- 工作目录: {self.project_root}\n")
            f.write(f"- 测试案例目录: {self.test_case_dir}\n")
            f.write(f"- Web 服务地址: {self.ws_uri}\n\n")
            f.write("## 测试响应\n\n")
            f.write("```\n")
            f.write(response)
            f.write("\n```\n")
        
        self.log(f"测试报告已保存: {report_file}")


def main():
    """主函数"""
    test = TestSuiteExecutorE2E()
    
    success = False
    
    try:
        if not test.start_web_server():
            test.log("无法启动 Web 服务，测试终止", "ERROR")
            sys.exit(1)
        
        time.sleep(2)
        
        success = asyncio.run(test.run_test())
        
    except KeyboardInterrupt:
        test.log("\n测试被用户中断", "WARNING")
    except Exception as e:
        test.log(f"测试执行异常: {e}", "ERROR")
        import traceback
        traceback.print_exc()
    finally:
        test.stop_web_server()
    
    test.log("\n" + "=" * 80)
    if success:
        test.log("测试完成: 所有验证点通过", "INFO")
        sys.exit(0)
    else:
        test.log("测试完成: 存在失败的验证点", "WARNING")
        sys.exit(1)


if __name__ == "__main__":
    main()
