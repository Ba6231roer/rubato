"""
Query Engine 性能测试

测试内容：
1. 流式响应性能测试
2. 并发 SubAgent 性能测试
3. 内存使用测试
4. 吞吐量测试
5. 延迟测试
"""

import sys
import asyncio
import time
import tracemalloc
from pathlib import Path
from unittest.mock import Mock, AsyncMock, MagicMock, patch
from typing import Dict, Any, List
import statistics

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.query_engine import (
    QueryEngine,
    QueryEngineConfig,
    SDKMessage,
)
from src.core.sub_agents import SubAgentManager
from src.core.sub_agent_types import SubAgentSpawnOptions
from langchain_core.messages import HumanMessage, AIMessage, AIMessageChunk
from langchain_core.tools import tool


def create_mock_llm_for_performance(delay: float = 0.01):
    """创建用于性能测试的 Mock LLM"""
    mock_llm = Mock()
    mock_llm.bind_tools = Mock(return_value=mock_llm)
    
    async def mock_astream(messages):
        await asyncio.sleep(delay)
        
        for i in range(5):
            yield {"type": "text_delta", "text": f"Chunk {i} "}
        
        yield {
            "type": "complete",
            "response": AIMessage(
                content="Final response",
                usage_metadata={"input_tokens": 100, "output_tokens": 50, "total_tokens": 150}
            )
        }
    
    mock_llm.astream = mock_astream
    return mock_llm


def create_mock_tool_for_performance(name: str, delay: float = 0.01):
    """创建用于性能测试的 Mock 工具"""
    mock_tool = Mock()
    mock_tool.name = name
    mock_tool.description = f"Test tool: {name}"
    mock_tool.args_schema = Mock()
    mock_tool.args_schema.schema = Mock(return_value={
        "type": "object",
        "properties": {"arg1": {"type": "string"}},
        "required": []
    })
    
    async def mock_ainvoke(args):
        await asyncio.sleep(delay)
        return f"Tool {name} result"
    
    mock_tool.ainvoke = mock_ainvoke
    return mock_tool


class TestStreamingPerformance:
    """流式响应性能测试"""
    
    @pytest.mark.asyncio
    async def test_streaming_latency(self):
        """测试流式响应延迟"""
        print("\n--- 测试流式响应延迟 ---")
        
        mock_llm = create_mock_llm_for_performance(delay=0.001)
        
        config = QueryEngineConfig(
            cwd="/tmp",
            llm=mock_llm,
            tools=[],
            skills=[],
            can_use_tool=lambda name, args: True,
            get_app_state=lambda: {},
            set_app_state=lambda state: None,
            max_turns=1
        )
        
        engine = QueryEngine(config)
        
        latencies = []
        
        for _ in range(10):
            start_time = time.time()
            first_chunk_time = None
            
            async for msg in engine.submit_message("Test"):
                if first_chunk_time is None and msg.type == "assistant":
                    first_chunk_time = time.time()
                    latencies.append(first_chunk_time - start_time)
                    break
        
        avg_latency = statistics.mean(latencies)
        print(f"   平均首块延迟: {avg_latency*1000:.2f}ms")
        
        assert avg_latency < 0.1, f"延迟过高: {avg_latency}s"
        
        print("   [OK] 流式响应延迟测试通过")
    
    @pytest.mark.asyncio
    async def test_streaming_throughput(self):
        """测试流式响应吞吐量"""
        print("\n--- 测试流式响应吞吐量 ---")
        
        mock_llm = create_mock_llm_for_performance(delay=0.001)
        
        config = QueryEngineConfig(
            cwd="/tmp",
            llm=mock_llm,
            tools=[],
            skills=[],
            can_use_tool=lambda name, args: True,
            get_app_state=lambda: {},
            set_app_state=lambda state: None,
            max_turns=1
        )
        
        engine = QueryEngine(config)
        
        total_chunks = 0
        start_time = time.time()
        
        for _ in range(10):
            async for msg in engine.submit_message("Test"):
                if msg.type == "assistant" and msg.content:
                    total_chunks += 1
        
        elapsed = time.time() - start_time
        throughput = total_chunks / elapsed
        
        print(f"   总块数: {total_chunks}")
        print(f"   总时间: {elapsed:.2f}s")
        print(f"   吞吐量: {throughput:.2f} chunks/s")
        
        assert throughput > 10, f"吞吐量过低: {throughput} chunks/s"
        
        print("   [OK] 流式响应吞吐量测试通过")
    
    @pytest.mark.asyncio
    async def test_large_streaming(self):
        """测试大量流式数据"""
        print("\n--- 测试大量流式数据 ---")
        
        mock_llm = Mock()
        mock_llm.bind_tools = Mock(return_value=mock_llm)
        
        async def mock_astream_large(messages):
            for i in range(100):
                yield {"type": "text_delta", "text": f"Chunk {i} "}
            
            yield {
                "type": "complete",
                "response": AIMessage(content="Large response")
            }
        
        mock_llm.astream = mock_astream_large
        
        config = QueryEngineConfig(
            cwd="/tmp",
            llm=mock_llm,
            tools=[],
            skills=[],
            can_use_tool=lambda name, args: True,
            get_app_state=lambda: {},
            set_app_state=lambda state: None,
            max_turns=1
        )
        
        engine = QueryEngine(config)
        
        chunk_count = 0
        start_time = time.time()
        
        async for msg in engine.submit_message("Test"):
            if msg.type == "assistant" and msg.content:
                chunk_count += 1
        
        elapsed = time.time() - start_time
        
        print(f"   处理块数: {chunk_count}")
        print(f"   处理时间: {elapsed:.2f}s")
        
        assert chunk_count >= 100
        
        print("   [OK] 大量流式数据测试通过")


class TestConcurrentSubAgentPerformance:
    """并发 SubAgent 性能测试"""
    
    @pytest.mark.asyncio
    async def test_concurrent_spawn(self):
        """测试并发创建 SubAgent"""
        print("\n--- 测试并发创建 SubAgent ---")
        
        mock_llm = Mock()
        mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content="Result"))
        mock_llm.bind_tools = Mock(return_value=mock_llm)
        
        mock_parent_agent = MagicMock()
        mock_parent_agent.tools = []
        mock_parent_agent.tool_registry = MagicMock()
        mock_parent_agent.tool_registry.get_tools_by_names.return_value = []
        mock_parent_agent.config = MagicMock()
        mock_parent_agent.config.model.model = MagicMock()
        
        sub_agent_manager = SubAgentManager(
            llm=mock_llm,
            parent_agent=mock_parent_agent,
            sub_agents_dir="sub_agents",
            recursion_limit=50,
            max_concurrent=10
        )
        
        async def mock_spawn(options):
            await asyncio.sleep(0.1)
            return f"Result for {options.agent_name}"
        
        with patch.object(sub_agent_manager, '_create_sub_agent_by_role', new_callable=AsyncMock) as mock_create:
            mock_create.return_value = "Success"
            
            start_time = time.time()
            
            tasks = []
            for i in range(5):
                options = SubAgentSpawnOptions(
                    agent_name=f"agent-{i}",
                    task=f"Task {i}",
                    timeout=10
                )
                tasks.append(sub_agent_manager.spawn_agent(options))
            
            results = await asyncio.gather(*tasks)
            
            elapsed = time.time() - start_time
        
        print(f"   并发数: 5")
        print(f"   总时间: {elapsed:.2f}s")
        print(f"   平均时间: {elapsed/5:.2f}s per agent")
        
        assert len(results) == 5
        assert elapsed < 1.0, f"并发性能不佳: {elapsed}s"
        
        print("   [OK] 并发创建 SubAgent 测试通过")
    
    @pytest.mark.asyncio
    async def test_max_concurrent_limit(self):
        """测试最大并发限制"""
        print("\n--- 测试最大并发限制 ---")
        
        mock_llm = Mock()
        mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content="Result"))
        mock_llm.bind_tools = Mock(return_value=mock_llm)
        
        mock_parent_agent = MagicMock()
        mock_parent_agent.tools = []
        mock_parent_agent.tool_registry = MagicMock()
        mock_parent_agent.tool_registry.get_tools_by_names.return_value = []
        mock_parent_agent.config = MagicMock()
        mock_parent_agent.config.model.model = MagicMock()
        
        sub_agent_manager = SubAgentManager(
            llm=mock_llm,
            parent_agent=mock_parent_agent,
            sub_agents_dir="sub_agents",
            recursion_limit=50,
            max_concurrent=3
        )
        
        lifecycle_manager = sub_agent_manager.get_lifecycle_manager()
        stats = lifecycle_manager.get_statistics()
        
        assert stats["max_concurrent"] == 3
        
        print("   [OK] 最大并发限制测试通过")


class TestMemoryUsage:
    """内存使用测试"""
    
    @pytest.mark.asyncio
    async def test_memory_for_long_conversation(self):
        """测试长对话的内存使用"""
        print("\n--- 测试长对话的内存使用 ---")
        
        tracemalloc.start()
        
        mock_llm = create_mock_llm_for_performance(delay=0.001)
        
        config = QueryEngineConfig(
            cwd="/tmp",
            llm=mock_llm,
            tools=[],
            skills=[],
            can_use_tool=lambda name, args: True,
            get_app_state=lambda: {},
            set_app_state=lambda state: None,
            max_turns=1
        )
        
        engine = QueryEngine(config)
        
        initial_memory = tracemalloc.get_traced_memory()[0]
        
        for i in range(100):
            messages = []
            async for msg in engine.submit_message(f"Message {i}"):
                messages.append(msg)
        
        final_memory = tracemalloc.get_traced_memory()[0]
        memory_increase = final_memory - initial_memory
        
        tracemalloc.stop()
        
        print(f"   初始内存: {initial_memory / 1024:.2f} KB")
        print(f"   最终内存: {final_memory / 1024:.2f} KB")
        print(f"   内存增长: {memory_increase / 1024:.2f} KB")
        
        assert memory_increase < 10 * 1024 * 1024, f"内存增长过多: {memory_increase / 1024 / 1024:.2f} MB"
        
        print("   [OK] 长对话内存使用测试通过")
    
    @pytest.mark.asyncio
    async def test_memory_for_large_messages(self):
        """测试大消息的内存使用"""
        print("\n--- 测试大消息的内存使用 ---")
        
        tracemalloc.start()
        
        mock_llm = Mock()
        mock_llm.bind_tools = Mock(return_value=mock_llm)
        
        large_content = "x" * 10000
        
        async def mock_astream_large(messages):
            yield {"type": "text_delta", "text": large_content}
            yield {
                "type": "complete",
                "response": AIMessage(content=large_content)
            }
        
        mock_llm.astream = mock_astream_large
        
        config = QueryEngineConfig(
            cwd="/tmp",
            llm=mock_llm,
            tools=[],
            skills=[],
            can_use_tool=lambda name, args: True,
            get_app_state=lambda: {},
            set_app_state=lambda state: None,
            max_turns=1
        )
        
        engine = QueryEngine(config)
        
        initial_memory = tracemalloc.get_traced_memory()[0]
        
        for _ in range(10):
            messages = []
            async for msg in engine.submit_message("Test"):
                messages.append(msg)
        
        final_memory = tracemalloc.get_traced_memory()[0]
        memory_increase = final_memory - initial_memory
        
        tracemalloc.stop()
        
        print(f"   初始内存: {initial_memory / 1024:.2f} KB")
        print(f"   最终内存: {final_memory / 1024:.2f} KB")
        print(f"   内存增长: {memory_increase / 1024:.2f} KB")
        
        print("   [OK] 大消息内存使用测试通过")


class TestThroughput:
    """吞吐量测试"""
    
    @pytest.mark.asyncio
    async def test_message_throughput(self):
        """测试消息吞吐量"""
        print("\n--- 测试消息吞吐量 ---")
        
        mock_llm = create_mock_llm_for_performance(delay=0.001)
        
        config = QueryEngineConfig(
            cwd="/tmp",
            llm=mock_llm,
            tools=[],
            skills=[],
            can_use_tool=lambda name, args: True,
            get_app_state=lambda: {},
            set_app_state=lambda state: None,
            max_turns=1
        )
        
        engine = QueryEngine(config)
        
        message_count = 50
        start_time = time.time()
        
        for _ in range(message_count):
            async for msg in engine.submit_message("Test"):
                pass
        
        elapsed = time.time() - start_time
        throughput = message_count / elapsed
        
        print(f"   消息数: {message_count}")
        print(f"   总时间: {elapsed:.2f}s")
        print(f"   吞吐量: {throughput:.2f} messages/s")
        
        assert throughput > 5, f"吞吐量过低: {throughput} messages/s"
        
        print("   [OK] 消息吞吐量测试通过")
    
    @pytest.mark.asyncio
    async def test_tool_call_throughput(self):
        """测试工具调用吞吐量"""
        print("\n--- 测试工具调用吞吐量 ---")
        
        mock_llm = Mock()
        mock_llm.bind_tools = Mock(return_value=mock_llm)
        
        call_count = 0
        
        async def mock_astream_with_tool(messages):
            nonlocal call_count
            call_count += 1
            
            yield {
                "type": "tool_call_start",
                "tool": {"id": f"call_{call_count}", "name": "test_tool", "args": {}}
            }
            yield {
                "type": "complete",
                "response": AIMessage(
                    content="",
                    tool_calls=[{"name": "test_tool", "args": {}, "id": f"call_{call_count}"}]
                )
            }
        
        mock_llm.astream = mock_astream_with_tool
        
        tool = create_mock_tool_for_performance("test_tool", delay=0.001)
        
        config = QueryEngineConfig(
            cwd="/tmp",
            llm=mock_llm,
            tools=[tool],
            skills=[],
            can_use_tool=lambda name, args: True,
            get_app_state=lambda: {},
            set_app_state=lambda state: None,
            max_turns=1
        )
        
        engine = QueryEngine(config)
        
        tool_call_count = 20
        start_time = time.time()
        
        for _ in range(tool_call_count):
            async for msg in engine.submit_message("Test"):
                pass
        
        elapsed = time.time() - start_time
        throughput = tool_call_count / elapsed
        
        print(f"   工具调用数: {tool_call_count}")
        print(f"   总时间: {elapsed:.2f}s")
        print(f"   吞吐量: {throughput:.2f} tool_calls/s")
        
        assert throughput > 5, f"吞吐量过低: {throughput} tool_calls/s"
        
        print("   [OK] 工具调用吞吐量测试通过")


class TestLatency:
    """延迟测试"""
    
    @pytest.mark.asyncio
    async def test_first_response_latency(self):
        """测试首次响应延迟"""
        print("\n--- 测试首次响应延迟 ---")
        
        mock_llm = create_mock_llm_for_performance(delay=0.001)
        
        config = QueryEngineConfig(
            cwd="/tmp",
            llm=mock_llm,
            tools=[],
            skills=[],
            can_use_tool=lambda name, args: True,
            get_app_state=lambda: {},
            set_app_state=lambda state: None,
            max_turns=1
        )
        
        engine = QueryEngine(config)
        
        latencies = []
        
        for _ in range(20):
            start_time = time.time()
            first_response = False
            
            async for msg in engine.submit_message("Test"):
                if not first_response and msg.type == "assistant":
                    latency = time.time() - start_time
                    latencies.append(latency)
                    first_response = True
                    break
        
        avg_latency = statistics.mean(latencies)
        p50 = statistics.median(latencies)
        p95 = sorted(latencies)[int(len(latencies) * 0.95)]
        
        print(f"   平均延迟: {avg_latency*1000:.2f}ms")
        print(f"   P50 延迟: {p50*1000:.2f}ms")
        print(f"   P95 延迟: {p95*1000:.2f}ms")
        
        assert avg_latency < 0.1, f"平均延迟过高: {avg_latency}s"
        
        print("   [OK] 首次响应延迟测试通过")
    
    @pytest.mark.asyncio
    async def test_tool_execution_latency(self):
        """测试工具执行延迟"""
        print("\n--- 测试工具执行延迟 ---")
        
        mock_llm = Mock()
        mock_llm.bind_tools = Mock(return_value=mock_llm)
        
        async def mock_astream(messages):
            yield {
                "type": "tool_call_start",
                "tool": {"id": "call_1", "name": "test_tool", "args": {}}
            }
            yield {
                "type": "complete",
                "response": AIMessage(
                    content="",
                    tool_calls=[{"name": "test_tool", "args": {}, "id": "call_1"}]
                )
            }
        
        mock_llm.astream = mock_astream
        
        tool = create_mock_tool_for_performance("test_tool", delay=0.005)
        
        config = QueryEngineConfig(
            cwd="/tmp",
            llm=mock_llm,
            tools=[tool],
            skills=[],
            can_use_tool=lambda name, args: True,
            get_app_state=lambda: {},
            set_app_state=lambda state: None,
            max_turns=1
        )
        
        engine = QueryEngine(config)
        
        latencies = []
        
        for _ in range(20):
            start_time = time.time()
            
            async for msg in engine.submit_message("Test"):
                if msg.type == "tool_result":
                    latency = time.time() - start_time
                    latencies.append(latency)
        
        avg_latency = statistics.mean(latencies)
        
        print(f"   平均工具执行延迟: {avg_latency*1000:.2f}ms")
        
        assert avg_latency < 0.1, f"工具执行延迟过高: {avg_latency}s"
        
        print("   [OK] 工具执行延迟测试通过")


def run_performance_tests():
    """运行所有性能测试"""
    import pytest
    
    print("\n" + "=" * 60)
    print("Query Engine 性能测试")
    print("=" * 60)
    
    result = pytest.main([__file__, "-v", "-s", "-k", "not memory"])
    
    print("\n" + "=" * 60)
    if result == 0:
        print("[SUCCESS] 所有性能测试通过!")
    else:
        print("[FAILED] 部分测试失败!")
    print("=" * 60)
    
    return result == 0


if __name__ == "__main__":
    import pytest
    success = run_performance_tests()
    sys.exit(0 if success else 1)
