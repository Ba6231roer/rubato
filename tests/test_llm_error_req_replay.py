"""
极简 LLM 错误请求报文回放测试脚本

用法:
    python tests/test_llm_error_req_replay.py <报文文件路径>
    python tests/test_llm_error_req_replay.py logs/llm_error_req_data_20260413_120000.log

功能:
    读取 llm_error_req_data_*.log 文件中的请求报文，
    使用 openai SDK 直接调用 LLM 进行验证。
"""
import sys
import json
import asyncio
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from openai import AsyncOpenAI


async def replay_request(filepath: str):
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    request = data.get("request", {})
    error_type = data.get("error_type", "unknown")
    error_message = data.get("error_message", "")
    timestamp = data.get("timestamp", "")
    
    print(f"=== LLM Error Request Replay ===")
    print(f"原始错误: [{error_type}] {error_message}")
    print(f"原始时间: {timestamp}")
    print(f"模型: {request.get('model', 'unknown')}")
    print(f"消息数: {len(request.get('messages', []))}")
    print(f"工具数: {len(request.get('tools', []))}")
    print(f"温度: {request.get('temperature', 'unknown')}")
    print(f"最大token: {request.get('max_tokens', 'unknown')}")
    print()
    
    api_key = os.environ.get("OPENAI_API_KEY", "")
    base_url = request.get("base_url")
    
    if not api_key:
        config_path = os.path.join(os.path.dirname(__file__), "..", "config", "model_config.yaml")
        if os.path.exists(config_path):
            import yaml
            with open(config_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
            api_key = config.get("model", {}).get("api_key", "")
            if not base_url:
                base_url = config.get("model", {}).get("base_url")
    
    if not api_key:
        print("错误: 未找到 API Key，请设置 OPENAI_API_KEY 环境变量或在 model_config.yaml 中配置")
        return
    
    client_kwargs = {"api_key": api_key}
    if base_url:
        client_kwargs["base_url"] = base_url
    
    client = AsyncOpenAI(**client_kwargs)
    
    call_params = {
        "model": request.get("model"),
        "messages": request.get("messages", []),
        "temperature": request.get("temperature", 0.7),
        "max_tokens": request.get("max_tokens", 80000),
    }
    
    if request.get("tools"):
        call_params["tools"] = request["tools"]
    
    print("--- 开始调用 LLM (流式) ---")
    print()
    
    try:
        call_params["stream"] = True
        stream = await client.chat.completions.create(**call_params)
        
        full_content = ""
        async for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if delta.content:
                print(delta.content, end="", flush=True)
                full_content += delta.content
            if delta.tool_calls:
                for tc in delta.tool_calls:
                    if tc.function and tc.function.name:
                        print(f"\n[Tool Call: {tc.function.name}]", flush=True)
        
        print()
        print()
        print(f"--- 调用成功 ---")
        print(f"响应长度: {len(full_content)} 字符")
        
    except Exception as e:
        print()
        print(f"--- 调用失败 ---")
        print(f"错误类型: {type(e).__name__}")
        print(f"错误信息: {e}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python tests/test_llm_error_req_replay.py <报文文件路径>")
        print("示例: python tests/test_llm_error_req_replay.py logs/llm_error_req_data_20260413_120000.log")
        sys.exit(1)
    
    filepath = sys.argv[1]
    if not os.path.exists(filepath):
        print(f"错误: 文件不存在: {filepath}")
        sys.exit(1)
    
    asyncio.run(replay_request(filepath))
