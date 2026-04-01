import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from openai import OpenAI
from src.config.loader import ConfigLoader


def test_llm_call_with_log_params():
    print("=" * 60)
    print("测试LLM调用 - 使用日志中的参数")
    print("=" * 60)
    
    try:
        loader = ConfigLoader(config_dir="config")
        config = loader.load_all()
        
        print("\n1. 加载模型配置:")
        print(f"   Provider: {config.model.model.provider}")
        print(f"   Model: {config.model.model.name}")
        print(f"   Base URL: {config.model.model.base_url}")
        print(f"   Temperature: {config.model.model.temperature}")
        print(f"   Max Tokens: {config.model.model.max_tokens}")
        
        client = OpenAI(
            api_key=config.model.model.api_key,
            base_url=config.model.model.base_url
        )
        
        system_message = """你是测试案例生成者,一个专业的测试案例设计助手。

# 角色
你是一个能够根据需求文档、用户故事或功能描述生成高质量测试案例的智能体。

# 目标
根据用户提供的需求信息,生成全面、规范、可执行的测试案例。

# 工作模式
你采用分析-设计-生成模式工作

# 工作原则

**重要:必须严格遵守以下原则**

1. **必须使用工具输出**:生成测试案例后,**必须**使用 `file_write` 工具将内容写入文件,**禁止**只在回复中描述或展示内容
2. **立即执行**:生成测试案例后**立即**调用工具输出,不要等待用户确认,不要说"我将生成"
3. **完整输出**:确保所有测试案例都写入文件,不要遗漏任何案例
4. **工具优先**:任何时候需要输出文件,都要使用工具而不是文字描述"""
        
        user_message = "需求:百度首页支持大模型检索,在原有检索框基础上新增深度思考选项。设计并生成测试案例"
        
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "file_mkdir",
                    "description": "创建目录\n\n        Args:\n            path: 目录路径(相对于项目根目录或绝对路径)\n\n        Returns:\n            成功返回 \"Success: Directory created\",失败返回错误信息\n\n        注意:\n            - 会递归创建所有父目录\n            - 如果目录已存在,不会报错",
                    "parameters": {
                        "properties": {
                            "path": {
                                "type": "string"
                            }
                        },
                        "required": [
                            "path"
                        ],
                        "type": "object"
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "file_write",
                    "description": "写入文件内容\n\n        Args:\n            path: 文件路径(相对于项目根目录或绝对路径)\n            content: 要写入的内容\n            mode: 写入模式,可选 \"overwrite\"(覆盖)或 \"append\"(追加),默认 \"overwrite\"\n            encoding: 文件编码,默认 utf-8\n\n        Returns:\n            成功返回 \"Success: File written successfully\",失败返回错误信息\n\n        注意:\n            - overwrite 模式会覆盖文件原有内容\n            - append 模式会在文件末尾追加内容\n            - 如果文件不存在,会自动创建(包括父目录)",
                    "parameters": {
                        "properties": {
                            "path": {
                                "type": "string"
                            },
                            "content": {
                                "type": "string"
                            },
                            "mode": {
                                "default": "overwrite",
                                "enum": [
                                    "overwrite",
                                    "append"
                                ],
                                "type": "string"
                            },
                            "encoding": {
                                "default": "utf-8",
                                "type": "string"
                            }
                        },
                        "required": [
                            "path",
                            "content"
                        ],
                        "type": "object"
                    }
                }
            }
        ]
        
        print("\n2. 准备调用参数:")
        print(f"   System Message长度: {len(system_message)} 字符")
        print(f"   User Message: {user_message}")
        print(f"   Tools数量: {len(tools)}")
        
        print("\n3. 开始调用LLM API...")
        print("-" * 60)
        
        response = client.chat.completions.create(
            model=config.model.model.name,
            temperature=config.model.model.temperature,
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_message}
            ],
            tools=tools
        )
        
        print("\n4. API调用成功!")
        print("=" * 60)
        print("\n响应结果:")
        print("-" * 60)
        
        print(f"\n模型: {response.model}")
        print(f"创建时间: {response.created}")
        print(f"完成原因: {response.choices[0].finish_reason}")
        
        if response.choices[0].message.content:
            print(f"\n消息内容:")
            print(response.choices[0].message.content)
        
        if response.choices[0].message.tool_calls:
            print(f"\n工具调用 ({len(response.choices[0].message.tool_calls)} 个):")
            for i, tool_call in enumerate(response.choices[0].message.tool_calls, 1):
                print(f"\n  工具 {i}:")
                print(f"    ID: {tool_call.id}")
                print(f"    名称: {tool_call.function.name}")
                print(f"    参数: {tool_call.function.arguments}")
        
        if hasattr(response, 'usage') and response.usage:
            print(f"\nToken使用统计:")
            print(f"  提示词Token: {response.usage.prompt_tokens}")
            print(f"  完成Token: {response.usage.completion_tokens}")
            print(f"  总Token: {response.usage.total_tokens}")
        
        print("\n" + "=" * 60)
        print("✓ 测试完成!")
        print("=" * 60)
        
        return True
        
    except Exception as e:
        print(f"\n✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_llm_call_with_log_params()
    
    if success:
        print("\n✓✓✓ 测试成功! ✓✓✓")
        sys.exit(0)
    else:
        print("\n✗✗✗ 测试失败! ✗✗✗")
        sys.exit(1)
