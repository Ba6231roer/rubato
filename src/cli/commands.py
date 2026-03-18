from typing import Dict, Callable, Optional, Awaitable
from ..core.agent import RubatoAgent
from ..skills.loader import SkillLoader
from ..mcp.client import MCPManager
import asyncio


class CommandHandler:
    """命令处理器"""
    
    def __init__(
        self,
        agent: RubatoAgent,
        skill_loader: SkillLoader,
        mcp_manager: Optional[MCPManager] = None
    ):
        self.agent = agent
        self.skill_loader = skill_loader
        self.mcp_manager = mcp_manager
        self.commands: Dict[str, Callable] = {
            'help': self._cmd_help,
            'quit': self._cmd_quit,
            'exit': self._cmd_quit,
            'config': self._cmd_config,
            'history': self._cmd_history,
            'clear': self._cmd_clear,
            'skill': self._cmd_skill,
            'tool': self._cmd_tool,
            'prompt': self._cmd_prompt,
            'browser': self._cmd_browser,
        }
        self._running = True
    
    def is_running(self) -> bool:
        """检查是否继续运行"""
        return self._running
    
    async def handle_async(self, user_input: str) -> Optional[str]:
        """异步处理用户输入"""
        user_input = user_input.strip()
        
        if not user_input:
            return None
        
        if user_input.startswith('/'):
            cmd_parts = user_input[1:].split(maxsplit=1)
            cmd = cmd_parts[0].lower()
            args = cmd_parts[1] if len(cmd_parts) > 1 else ""
            
            if cmd in self.commands:
                result = self.commands[cmd](args)
                if asyncio.iscoroutine(result):
                    return await result
                return result
            else:
                return f"未知命令：{cmd}。输入 /help 查看帮助。"
        
        return None
    
    def handle(self, user_input: str) -> Optional[str]:
        """同步处理用户输入（向后兼容）"""
        user_input = user_input.strip()
        
        if not user_input:
            return None
        
        if user_input.startswith('/'):
            cmd_parts = user_input[1:].split(maxsplit=1)
            cmd = cmd_parts[0].lower()
            args = cmd_parts[1] if len(cmd_parts) > 1 else ""
            
            if cmd in self.commands:
                result = self.commands[cmd](args)
                if asyncio.iscoroutine(result):
                    return "此命令需要异步执行，请使用 handle_async"
                return result
            else:
                return f"未知命令：{cmd}。输入 /help 查看帮助。"
        
        return None
    
    def _cmd_help(self, args: str) -> str:
        """显示帮助信息"""
        return """
可用命令：
  /help          - 显示帮助信息
  /quit, /exit   - 退出程序
  /config        - 显示当前配置
  /history       - 显示对话历史
  /clear         - 清空对话历史
  /skill list    - 列出所有可用Skills
  /skill show <name> - 显示Skill详情
  /tool list     - 列出所有可用工具
  /prompt show   - 显示当前系统提示词
  /browser status - 查看浏览器状态
  /browser close  - 关闭浏览器
  /browser reopen - 重新打开浏览器

直接输入问题与Agent对话。
"""
    
    def _cmd_quit(self, args: str) -> str:
        """退出程序"""
        self._running = False
        return "再见！"
    
    def _cmd_config(self, args: str) -> str:
        """显示当前配置"""
        config = self.agent.config
        model = config.model.model
        
        lines = [
            "当前配置：",
            f"  模型: {model.provider}/{model.name}",
            f"  Temperature: {model.temperature}",
            f"  Max Tokens: {model.max_tokens}",
        ]
        
        if self.mcp_manager:
            status = "已连接" if self.mcp_manager.is_connected else "未连接"
            lines.append(f"  MCP状态: {status}")
        
        return "\n".join(lines)
    
    def _cmd_history(self, args: str) -> str:
        """显示对话历史"""
        messages = self.agent.context_manager.get_messages()
        
        if not messages:
            return "对话历史为空"
        
        lines = ["对话历史："]
        for i, msg in enumerate(messages, 1):
            msg_type = type(msg).__name__
            content = msg.content[:100] + "..." if len(msg.content) > 100 else msg.content
            lines.append(f"  [{i}] {msg_type}: {content}")
        
        return "\n".join(lines)
    
    def _cmd_clear(self, args: str) -> str:
        """清空对话历史"""
        self.agent.clear_context()
        return "对话历史已清空"
    
    def _cmd_skill(self, args: str) -> str:
        """Skill相关命令"""
        parts = args.split(maxsplit=1)
        sub_cmd = parts[0].lower() if parts else ""
        skill_name = parts[1] if len(parts) > 1 else ""
        
        if sub_cmd == "list":
            skills = self.skill_loader.list_skills()
            if not skills:
                return "没有可用的Skills"
            
            lines = ["可用Skills："]
            for skill in skills:
                lines.append(f"  - {skill.name}: {skill.description}")
            return "\n".join(lines)
        
        elif sub_cmd == "show":
            if not skill_name:
                return "请指定Skill名称：/skill show <name>"
            
            metadata = self.skill_loader.registry.get_skill(skill_name)
            if not metadata:
                return f"未找到Skill：{skill_name}"
            
            lines = [
                f"Skill: {metadata.name}",
                f"描述: {metadata.description}",
                f"版本: {metadata.version}",
                f"触发词: {', '.join(metadata.triggers)}",
            ]
            return "\n".join(lines)
        
        else:
            return "用法：/skill list | /skill show <name>"
    
    def _cmd_tool(self, args: str) -> str:
        """工具相关命令"""
        parts = args.split(maxsplit=1)
        sub_cmd = parts[0].lower() if parts else ""
        
        if sub_cmd == "list":
            tools = self.agent.tools
            if not tools:
                return "没有可用的工具"
            
            lines = ["可用工具："]
            for tool in tools:
                lines.append(f"  - {tool.name}: {tool.description[:50]}...")
            return "\n".join(lines)
        
        else:
            return "用法：/tool list"
    
    def _cmd_prompt(self, args: str) -> str:
        """提示词相关命令"""
        parts = args.split(maxsplit=1)
        sub_cmd = parts[0].lower() if parts else ""
        
        if sub_cmd == "show":
            prompt = self.agent.get_system_prompt()
            lines = ["系统提示词：", "-" * 40]
            lines.append(prompt[:500] + "..." if len(prompt) > 500 else prompt)
            return "\n".join(lines)
        
        else:
            return "用法：/prompt show"
    
    async def _cmd_browser(self, args: str) -> str:
        """浏览器相关命令"""
        parts = args.split(maxsplit=1)
        sub_cmd = parts[0].lower() if parts else ""
        
        if not self.mcp_manager:
            return "MCP未启用，无法管理浏览器"
        
        if sub_cmd == "status":
            if not self.mcp_manager.is_connected:
                return "MCP未连接"
            
            alive = await self.mcp_manager.check_browser_alive()
            status = "运行中" if alive else "已关闭"
            return f"浏览器状态: {status}"
        
        elif sub_cmd == "close":
            if not self.mcp_manager.is_connected:
                return "MCP未连接"
            
            success = await self.mcp_manager.close_browser()
            return "浏览器已关闭" if success else "关闭浏览器失败"
        
        elif sub_cmd == "reopen":
            if not self.mcp_manager.is_connected:
                return "MCP未连接"
            
            success = await self.mcp_manager.ensure_browser()
            return "浏览器已重新打开" if success else "重新打开浏览器失败"
        
        else:
            return "用法：/browser status | /browser close | /browser reopen"
