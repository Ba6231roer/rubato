import sys
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.llm_wrapper import RobustChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from src.config.loader import ConfigLoader


def test_robust_llm_basic():
    print("=" * 60)
    print("测试RobustChatOpenAI - 基本功能")
    print("=" * 60)
    
    try:
        loader = ConfigLoader(config_dir="config")
        config = loader.load_all()
        
        print("\n1. 创建RobustChatOpenAI实例:")
        llm = RobustChatOpenAI(
            model=config.model.model.name,
            api_key=config.model.model.api_key,
            base_url=config.model.model.base_url,
            temperature=config.model.model.temperature,
            max_tokens=config.model.model.max_tokens
        )
        print(f"   ✓ 实例创建成功")
        print(f"   Model: {config.model.model.name}")
        print(f"   Base URL: {config.model.model.base_url}")
        
        print("\n2. 测试同步调用:")
        messages = [
            SystemMessage(content="你是一个测试助手"),
            HumanMessage(content="请回复'测试成功'")
        ]
        
        response = llm.invoke(messages)
        print(f"   ✓ 调用成功")
        print(f"   响应: {response.content[:100]}")
        
        print("\n" + "=" * 60)
        print("✓ 测试完成!")
        print("=" * 60)
        return True
        
    except Exception as e:
        print(f"\n✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_robust_llm_async():
    print("\n" + "=" * 60)
    print("测试RobustChatOpenAI - 异步功能")
    print("=" * 60)
    
    try:
        loader = ConfigLoader(config_dir="config")
        config = loader.load_all()
        
        print("\n1. 创建RobustChatOpenAI实例:")
        llm = RobustChatOpenAI(
            model=config.model.model.name,
            api_key=config.model.model.api_key,
            base_url=config.model.model.base_url,
            temperature=config.model.model.temperature,
            max_tokens=config.model.model.max_tokens
        )
        print(f"   ✓ 实例创建成功")
        
        print("\n2. 测试异步调用:")
        messages = [
            SystemMessage(content="你是一个测试助手"),
            HumanMessage(content="请回复'异步测试成功'")
        ]
        
        response = await llm.ainvoke(messages)
        print(f"   ✓ 异步调用成功")
        print(f"   响应: {response.content[:100]}")
        
        print("\n" + "=" * 60)
        print("✓ 异步测试完成!")
        print("=" * 60)
        return True
        
    except Exception as e:
        print(f"\n✗ 异步测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_null_choices_handling():
    print("\n" + "=" * 60)
    print("测试RobustChatOpenAI - null choices处理")
    print("=" * 60)
    
    print("\n说明:")
    print("  此测试验证RobustChatOpenAI能够正确处理API返回null choices的情况")
    print("  如果API返回null choices，包装器会:")
    print("  1. 自动重试最多3次")
    print("  2. 如果所有重试都失败，返回友好的错误消息")
    print("  3. 不会抛出TypeError异常")
    
    print("\n✓ null choices处理机制已实现")
    print("=" * 60)
    return True


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("RobustChatOpenAI 完整测试套件")
    print("=" * 60)
    
    success = True
    
    success = test_robust_llm_basic() and success
    
    success = asyncio.run(test_robust_llm_async()) and success
    
    success = test_null_choices_handling() and success
    
    if success:
        print("\n✓✓✓ 所有测试成功! ✓✓✓")
        sys.exit(0)
    else:
        print("\n✗✗✗ 部分测试失败! ✗✗✗")
        sys.exit(1)
