"""
SubAgent 生命周期管理器

根据设计文档 11.7 节实现，管理 SubAgent 的完整生命周期。
"""

import asyncio
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from .sub_agent_types import (
    SubAgentDefinition,
    SubAgentInstance,
    SubAgentState,
)
from ..utils.logger import get_llm_logger


class SubAgentLifecycleManager:
    """SubAgent 生命周期管理器
    
    负责：
    - 创建和销毁 SubAgent 实例
    - 并发控制
    - 超时管理
    - 状态追踪
    - 回调触发
    """
    
    def __init__(self, max_concurrent: int = 10):
        """初始化生命周期管理器
        
        Args:
            max_concurrent: 最大并发 SubAgent 数量
        """
        self.max_concurrent = max_concurrent
        self._instances: Dict[str, SubAgentInstance] = {}
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._lock = asyncio.Lock()
        self._logger = get_llm_logger()
        
        self._on_created: List[Callable] = []
        self._on_started: List[Callable] = []
        self._on_completed: List[Callable] = []
        self._on_failed: List[Callable] = []
    
    async def create_instance(
        self,
        name: str,
        definition: SubAgentDefinition,
        task: str,
        parent_session_id: Optional[str] = None,
        depth: int = 0
    ) -> SubAgentInstance:
        """创建 SubAgent 实例
        
        Args:
            name: SubAgent 名称
            definition: SubAgent 定义
            task: 任务描述
            parent_session_id: 父会话 ID
            depth: 递归深度
            
        Returns:
            SubAgentInstance: 创建的实例
        """
        instance = SubAgentInstance(
            instance_id=str(uuid.uuid4()),
            name=name,
            definition=definition,
            task=task,
            parent_session_id=parent_session_id,
            depth=depth
        )
        
        async with self._lock:
            self._instances[instance.instance_id] = instance
        
        await self._trigger_callbacks(self._on_created, instance)
        
        self._logger.log_agent_action("sub_agent_instance_created", {
            "instance_id": instance.instance_id,
            "name": name,
            "depth": depth,
            "parent_session_id": parent_session_id
        })
        
        return instance
    
    async def start_instance(
        self,
        instance: SubAgentInstance,
        executor: Callable
    ) -> str:
        """启动 SubAgent 实例
        
        Args:
            instance: SubAgent 实例
            executor: 执行函数（异步可调用对象）
            
        Returns:
            执行结果
        """
        async with self._semaphore:
            instance.state = SubAgentState.RUNNING
            instance.started_at = datetime.now()
            
            await self._trigger_callbacks(self._on_started, instance)
            
            self._logger.log_agent_action("sub_agent_instance_started", {
                "instance_id": instance.instance_id,
                "name": instance.name,
                "timeout": instance.definition.execution.timeout
            })
            
            try:
                result = await asyncio.wait_for(
                    executor(),
                    timeout=instance.definition.execution.timeout
                )
                
                instance.state = SubAgentState.COMPLETED
                instance.result = result if isinstance(result, str) else str(result)
                instance.completed_at = datetime.now()
                
                await self._trigger_callbacks(self._on_completed, instance)
                
                duration = (
                    instance.completed_at - instance.started_at
                ).total_seconds()
                
                self._logger.log_agent_action("sub_agent_instance_completed", {
                    "instance_id": instance.instance_id,
                    "name": instance.name,
                    "duration_seconds": duration,
                    "result_length": len(instance.result) if instance.result else 0
                })
                
                return instance.result
                
            except asyncio.TimeoutError:
                instance.state = SubAgentState.TIMEOUT
                instance.error = f"执行超时（{instance.definition.execution.timeout}秒）"
                instance.completed_at = datetime.now()
                
                await self._trigger_callbacks(self._on_failed, instance)
                
                self._logger.log_agent_action("sub_agent_instance_timeout", {
                    "instance_id": instance.instance_id,
                    "name": instance.name,
                    "timeout": instance.definition.execution.timeout
                })
                
                raise TimeoutError(instance.error)
                
            except asyncio.CancelledError:
                instance.state = SubAgentState.CANCELLED
                instance.error = "任务被取消"
                instance.completed_at = datetime.now()
                
                await self._trigger_callbacks(self._on_failed, instance)
                
                self._logger.log_agent_action("sub_agent_instance_cancelled", {
                    "instance_id": instance.instance_id,
                    "name": instance.name
                })
                
                raise
                
            except Exception as e:
                instance.state = SubAgentState.FAILED
                instance.error = str(e)
                instance.completed_at = datetime.now()
                
                await self._trigger_callbacks(self._on_failed, instance)
                
                self._logger.log_agent_action("sub_agent_instance_failed", {
                    "instance_id": instance.instance_id,
                    "name": instance.name,
                    "error": str(e),
                    "error_type": type(e).__name__
                })
                
                raise
    
    async def cancel_instance(self, instance_id: str) -> bool:
        """取消 SubAgent 实例
        
        Args:
            instance_id: 实例 ID
            
        Returns:
            是否成功取消
        """
        async with self._lock:
            instance = self._instances.get(instance_id)
            if not instance:
                return False
            
            if instance.state == SubAgentState.RUNNING:
                instance.state = SubAgentState.CANCELLED
                instance.completed_at = datetime.now()
                
                self._logger.log_agent_action("sub_agent_instance_cancelled", {
                    "instance_id": instance_id,
                    "name": instance.name
                })
                
                return True
            
            return False
    
    async def destroy_instance(self, instance_id: str) -> bool:
        """销毁 SubAgent 实例
        
        Args:
            instance_id: 实例 ID
            
        Returns:
            是否成功销毁
        """
        async with self._lock:
            if instance_id in self._instances:
                instance = self._instances[instance_id]
                
                if instance.state == SubAgentState.RUNNING:
                    await self.cancel_instance(instance_id)
                
                del self._instances[instance_id]
                
                self._logger.log_agent_action("sub_agent_instance_destroyed", {
                    "instance_id": instance_id,
                    "name": instance.name
                })
                
                return True
            
            return False
    
    async def cleanup_completed_instances(self, max_age_hours: int = 24) -> int:
        """清理已完成的实例
        
        Args:
            max_age_hours: 最大保留时间（小时）
            
        Returns:
            清理的实例数量
        """
        async with self._lock:
            now = datetime.now()
            to_remove = []
            
            terminal_states = [
                SubAgentState.COMPLETED,
                SubAgentState.FAILED,
                SubAgentState.TIMEOUT,
                SubAgentState.CANCELLED
            ]
            
            for instance_id, instance in self._instances.items():
                if instance.state in terminal_states:
                    if instance.completed_at:
                        age = (now - instance.completed_at).total_seconds() / 3600
                        if age > max_age_hours:
                            to_remove.append(instance_id)
            
            for instance_id in to_remove:
                del self._instances[instance_id]
            
            if to_remove:
                self._logger.log_agent_action("sub_agent_instances_cleaned", {
                    "count": len(to_remove)
                })
            
            return len(to_remove)
    
    @asynccontextmanager
    async def managed_instance(
        self,
        name: str,
        definition: SubAgentDefinition,
        task: str,
        executor: Callable,
        parent_session_id: Optional[str] = None,
        depth: int = 0
    ):
        """管理 SubAgent 实例的上下文管理器
        
        自动处理创建、执行和销毁
        
        Args:
            name: SubAgent 名称
            definition: SubAgent 定义
            task: 任务描述
            executor: 执行函数
            parent_session_id: 父会话 ID
            depth: 递归深度
            
        Yields:
            tuple: (SubAgentInstance, result)
        """
        instance = await self.create_instance(
            name, definition, task, parent_session_id, depth
        )
        
        try:
            result = await self.start_instance(instance, executor)
            yield instance, result
        finally:
            await self.destroy_instance(instance.instance_id)
    
    def get_instance(self, instance_id: str) -> Optional[SubAgentInstance]:
        """获取实例
        
        Args:
            instance_id: 实例 ID
            
        Returns:
            SubAgentInstance 或 None
        """
        return self._instances.get(instance_id)
    
    def list_instances(
        self,
        state: Optional[SubAgentState] = None
    ) -> List[SubAgentInstance]:
        """列出实例
        
        Args:
            state: 过滤状态（可选）
            
        Returns:
            实例列表
        """
        if state:
            return [
                inst for inst in self._instances.values()
                if inst.state == state
            ]
        return list(self._instances.values())
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息
        
        Returns:
            统计信息字典
        """
        instances = list(self._instances.values())
        
        return {
            "total_instances": len(instances),
            "by_state": {
                state.value: len([i for i in instances if i.state == state])
                for state in SubAgentState
            },
            "total_tool_calls": sum(i.tool_calls for i in instances),
            "average_depth": (
                sum(i.depth for i in instances) / len(instances)
                if instances else 0
            ),
            "max_concurrent": self.max_concurrent,
        }
    
    def get_running_count(self) -> int:
        """获取正在运行的实例数量
        
        Returns:
            正在运行的实例数量
        """
        return len([i for i in self._instances.values() if i.state == SubAgentState.RUNNING])
    
    def get_available_slots(self) -> int:
        """获取可用的并发槽位
        
        Returns:
            可用槽位数量
        """
        return self.max_concurrent - self.get_running_count()
    
    async def _trigger_callbacks(
        self,
        callbacks: List[Callable],
        instance: SubAgentInstance
    ) -> None:
        """触发回调函数
        
        Args:
            callbacks: 回调函数列表
            instance: SubAgent 实例
        """
        for callback in callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(instance)
                else:
                    callback(instance)
            except Exception as e:
                self._logger.log_agent_action("callback_error", {
                    "error": str(e),
                    "callback_type": str(type(callback))
                })
    
    def on_created(self, callback: Callable) -> None:
        """注册创建回调
        
        Args:
            callback: 回调函数
        """
        self._on_created.append(callback)
    
    def on_started(self, callback: Callable) -> None:
        """注册启动回调
        
        Args:
            callback: 回调函数
        """
        self._on_started.append(callback)
    
    def on_completed(self, callback: Callable) -> None:
        """注册完成回调
        
        Args:
            callback: 回调函数
        """
        self._on_completed.append(callback)
    
    def on_failed(self, callback: Callable) -> None:
        """注册失败回调
        
        Args:
            callback: 回调函数
        """
        self._on_failed.append(callback)
    
    def clear_callbacks(self) -> None:
        """清除所有回调"""
        self._on_created.clear()
        self._on_started.clear()
        self._on_completed.clear()
        self._on_failed.clear()
