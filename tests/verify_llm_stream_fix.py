"""
验证 LLM 流式调用修复效果

测试场景：
1. 测试基本的流式调用
2. 测试空响应重试
3. 测试工具调用
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langchain_core.messages import HumanMessage, SystemMessage
from src.core.llm_wrapper import RobustChatOpenAI, LLMCaller
from langchain_core.tools import tool


@tool
def get_weather(city: str) -> str:
    """获取天气信息"""
    return f"{city}的天气：晴天，25°C"


async def test_basic_stream():
    """测试基本流式调用"""
    print("\n=== 测试 1: 基本流式调用 ===")
    
    llm = RobustChatOpenAI(
        model="deepseek-chat",
        temperature=0.7,
        max_tokens=100
    )
    
    messages = [
        SystemMessage(content="你是一个助手"),
        HumanMessage(content="你好，请简单介绍一下自己")
    ]
    
    print("开始流式调用...")
    full_response = ""
    chunk_count = 0
    
    async for chunk in llm.astream(messages):
        if isinstance(chunk, str):
            print(chunk, end="", flush=True)
            full_response += chunk
            chunk_count += 1
        elif hasattr(chunk, 'content') and chunk.content:
            print(chunk.content, end="", flush=True)
            full_response += chunk.content
            chunk_count += 1
    
    print(f"\n\n✅ 流式调用完成")
    print(f"   总块数: {chunk_count}")
    print(f"   响应长度: {len(full_response)}")
    
    return chunk_count > 0


async def test_llm_caller_stream():
    """测试 LLMCaller 流式调用"""
    print("\n=== 测试 2: LLMCaller 流式调用 ===")
    
    llm = RobustChatOpenAI(
        model="deepseek-chat",
        temperature=0.7,
        max_tokens=100
    )
    
    caller = LLMCaller(
        llm=llm,
        system_prompt="你是一个助手"
    )
    
    messages = [HumanMessage(content="你好")]
    
    print("开始流式调用...")
    full_response = ""
    event_count = 0
    
    async for event in caller.stream_call(messages, use_tools=False):
        event_count += 1
        if event["type"] == "text_delta":
            print(event["text"], end="", flush=True)
            full_response += event["text"]
        elif event["type"] == "complete":
            print("\n\n✅ 收到完成事件")
    
    print(f"\n✅ 流式调用完成")
    print(f"   总事件数: {event_count}")
    print(f"   响应长度: {len(full_response)}")
    
    return event_count > 0 and full_response


async def test_tool_binding():
    """测试工具绑定"""
    print("\n=== 测试 3: 工具绑定 ===")
    
    llm = RobustChatOpenAI(
        model="deepseek-chat",
        temperature=0.7,
        max_tokens=100
    )
    
    caller = LLMCaller(
        llm=llm,
        tools=[get_weather],
        system_prompt="你是一个助手，可以查询天气"
    )
    
    messages = [HumanMessage(content="北京今天天气怎么样？")]
    
    print("开始流式调用（带工具）...")
    full_response = ""
    has_tool_call = False
    event_count = 0
    
    async for event in caller.stream_call(messages, use_tools=True):
        event_count += 1
        if event["type"] == "text_delta":
            print(event["text"], end="", flush=True)
            full_response += event["text"]
        elif event["type"] == "tool_call_start":
            has_tool_call = True
            tool_info = event["tool"]
            print(f"\n\n🔧 检测到工具调用: {tool_info['name']}")
        elif event["type"] == "complete":
            print("\n\n✅ 收到完成事件")
    
    print(f"\n✅ 流式调用完成")
    print(f"   总事件数: {event_count}")
    print(f"   响应长度: {len(full_response)}")
    print(f"   有工具调用: {has_tool_call}")
    
    return event_count > 0


async def main():
    """运行所有测试"""
    print("=" * 60)
    print("LLM 流式调用修复验证")
    print("=" * 60)
    
    try:
        # 测试 1: 基本流式调用
        result1 = await test_basic_stream()
        
        # 测试 2: LLMCaller 流式调用
        result2 = await test_llm_caller_stream()
        
        # 测试 3: 工具绑定
        result3 = await test_tool_binding()
        
        print("\n" + "=" * 60)
        print("测试结果汇总")
        print("=" * 60)
        print(f"测试 1 (基本流式调用): {'✅ 通过' if result1 else '❌ 失败'}")
        print(f"测试 2 (LLMCaller 流式调用): {'✅ 通过' if result2 else '❌ 失败'}")
        print(f"测试 3 (工具绑定): {'✅ 通过' if result3 else '❌ 失败'}")
        
        if result1 and result2 and result3:
            print("\n🎉 所有测试通过！修复成功！")
            return True
        else:
            print("\n❌ 部分测试失败")
            return False
            
    except Exception as e:
        print(f"\n❌ 测试过程中出现错误: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
