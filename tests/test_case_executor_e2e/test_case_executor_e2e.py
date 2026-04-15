"""
Test Case Executor E2E 测试脚本

该脚本用于自动化测试 test-case-executor 角色的功能：
1. 启动 Web 服务
2. 通过 WebSocket 连接服务
3. 切换角色到 test-case-executor
4. 执行浏览器自动化测试任务
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


class TestCaseExecutorE2E:
    """Test Case Executor E2E 测试类"""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent.parent
        self.venv_python = self.project_root / "venv" / "Scripts" / "python.exe"
        self.server_process = None
        self.ws_uri = "ws://127.0.0.1:8000/ws"
        self.test_task = "打开头条首页，找到今日要闻，点击第一条新闻，页面能正常打开"
        
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
                [str(self.venv_python), "-u", "-m", "src.main", "--web", "--port", "8000"],
                cwd=str(self.project_root),
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
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
                    self.log(f"服务进程意外退出 (退出码: {self.server_process.returncode})", "ERROR")
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
    
    async def send_command(self, websocket, command: str, timeout: int = 120) -> dict:
        """发送命令并等待响应"""
        self.log(f"发送命令: {command}")
        
        message = {
            "type": "command",
            "content": command
        }
        
        await websocket.send(json.dumps(message))
        
        try:
            response = await asyncio.wait_for(
                websocket.recv(),
                timeout=timeout
            )
            data = json.loads(response)
            
            self.log(f"收到响应: {data.get('type')}")
            if data.get('type') == 'command_result':
                content = data.get('content', {})
                self.log(f"命令结果类型: {content.get('type')}")
                self.log(f"命令结果消息: {content.get('message', '')[:100]}...")
            return data
        except asyncio.TimeoutError:
            self.log(f"命令响应超时 ({timeout} 秒)", "ERROR")
            self.log("可能服务端处理命令时发生异常，请检查服务端日志", "ERROR")
            return {"type": "error", "content": f"命令响应超时 ({timeout} 秒)"}
    
    async def send_task(self, websocket, task: str, timeout: int = 600) -> str:
        """发送任务并收集完整响应"""
        self.log(f"发送任务: {task}")
        self.log(f"超时时间: {timeout} 秒")
        
        message = {
            "type": "task",
            "content": task
        }
        
        await websocket.send(json.dumps(message))
        
        full_response = ""
        chunk_count = 0
        start_time = time.time()
        
        while True:
            try:
                response = await asyncio.wait_for(
                    websocket.recv(), 
                    timeout=min(timeout, 120)
                )
                data = json.loads(response)
                msg_type = data.get("type")
                content = data.get("content", "")
                
                elapsed = time.time() - start_time
                
                if msg_type == "chunk":
                    chunk_count += 1
                    full_response += content
                    if chunk_count % 10 == 0:
                        print(".", end="", flush=True)
                        self.log(f"已接收 {chunk_count} 个响应块，耗时 {elapsed:.1f} 秒")
                elif msg_type == "done":
                    print()
                    total_time = time.time() - start_time
                    self.log(f"任务完成 (共 {chunk_count} 个响应块，总耗时 {total_time:.1f} 秒)")
                    break
                elif msg_type == "error":
                    print()
                    self.log(f"任务执行错误: {content}", "ERROR")
                    break
                else:
                    self.log(f"收到消息类型: {msg_type}")
                
                if elapsed > timeout:
                    self.log(f"任务执行超时 ({timeout} 秒)", "ERROR")
                    break
                    
            except asyncio.TimeoutError:
                self.log(f"单次接收超时 (120 秒无响应)", "WARNING")
                if full_response:
                    self.log("已接收到部分响应，继续等待...")
                    continue
                else:
                    self.log("未接收到任何响应", "ERROR")
                    break
            except websockets.exceptions.ConnectionClosed as e:
                self.log(f"WebSocket 连接关闭: {e}", "ERROR")
                break
            except Exception as e:
                self.log(f"接收响应错误: {e}", "ERROR")
                import traceback
                traceback.print_exc()
                break
        
        return full_response
    
    async def run_test(self) -> bool:
        """运行测试"""
        self.log("=" * 80)
        self.log("Test Case Executor E2E 测试开始")
        self.log("=" * 80)
        
        try:
            self.log(f"连接 WebSocket: {self.ws_uri}")
            
            async with websockets.connect(
                self.ws_uri,
                ping_interval=20,
                ping_timeout=120,
                close_timeout=120
            ) as websocket:
                response = await websocket.recv()
                data = json.loads(response)
                self.log(f"连接成功: {data.get('content')}")
                
                self.log("\n" + "=" * 80)
                self.log("步骤 1: 切换角色到 test-case-executor")
                self.log("=" * 80)
                
                result = await self.send_command(websocket, "/role test-case-executor")
                
                if result.get("type") == "error":
                    self.log("角色切换失败", "ERROR")
                    return False
                
                if result.get("type") == "command_result":
                    content = result.get("content", {})
                    if content.get("type") == "ERROR":
                        self.log(f"角色切换失败: {content.get('message')}", "ERROR")
                        return False
                    role_data = content.get("data", {})
                    self.log(f"角色切换成功: {role_data.get('role', 'unknown')}")
                else:
                    self.log(f"收到未知响应类型: {result.get('type')}", "WARNING")
                
                await asyncio.sleep(2)
                
                self.log("\n" + "=" * 80)
                self.log("步骤 2: 执行浏览器自动化测试任务")
                self.log("=" * 80)
                
                self.log(f"测试任务: {self.test_task}")
                
                full_response = await self.send_task(websocket, self.test_task, timeout=600)
                
                self.log("\n" + "=" * 80)
                self.log("步骤 3: 验证测试结果")
                self.log("=" * 80)
                
                validation_results = self.validate_response(full_response)
                
                self.log("\n" + "=" * 80)
                self.log("测试结果汇总")
                self.log("=" * 80)
                
                for check, passed in validation_results.items():
                    status = "[PASS]" if passed else "[FAIL]"
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
                
                self.save_test_report(full_response, all_passed)
                
                return all_passed
                
        except Exception as e:
            self.log(f"测试执行失败: {e}", "ERROR")
            import traceback
            traceback.print_exc()
            return False
    
    def validate_response(self, response: str) -> dict:
        """验证响应内容"""
        validation_results = {
            "包含测试步骤": any(kw in response for kw in ["步骤", "测试步骤", "执行步骤", "Step"]),
            "包含浏览器操作": any(kw in response for kw in ["打开", "浏览器", "页面", "点击", "头条", "navigate", "click", "open"]),
            "包含操作结果": any(kw in response for kw in ["成功", "完成", "结果", "正常", "success", "完成"]),
            "包含测试结论": any(kw in response for kw in ["测试", "结论", "通过", "验证", "test", "result"]),
        }
        
        return validation_results
    
    def save_test_report(self, response: str, success: bool):
        """保存测试报告"""
        report_dir = self.project_root / "test_reports"
        report_dir.mkdir(exist_ok=True)
        
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        report_file = report_dir / f"test_case_executor_e2e_{timestamp}.md"
        
        with open(report_file, "w", encoding="utf-8") as f:
            f.write("# Test Case Executor E2E 测试报告\n\n")
            f.write(f"**测试时间**: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"**测试结果**: {'通过' if success else '失败'}\n\n")
            f.write("## 测试环境\n\n")
            f.write(f"- 工作目录: {self.project_root}\n")
            f.write(f"- 测试任务: {self.test_task}\n")
            f.write(f"- Web 服务地址: {self.ws_uri}\n\n")
            f.write("## 测试响应\n\n")
            f.write("```\n")
            f.write(response)
            f.write("\n```\n")
        
        self.log(f"测试报告已保存: {report_file}")


def main():
    """主函数"""
    test = TestCaseExecutorE2E()
    
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
