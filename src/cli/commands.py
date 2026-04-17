from typing import Dict, Callable, Optional, Awaitable, Tuple
from ..core.agent import RubatoAgent
from ..core.role_manager import RoleManager
from ..core.agent_pool import AgentPool
from ..skills.loader import SkillLoader
from ..mcp.client import MCPManager
from ..config.loader import ConfigLoader
from ..config.validators import ConfigValidationError
import asyncio


class CommandHandler:
    """命令处理器"""
    
    def __init__(
        self,
        agent: RubatoAgent,
        skill_loader: SkillLoader,
        mcp_manager: Optional[MCPManager] = None,
        role_manager: Optional[RoleManager] = None,
        config_loader: Optional[ConfigLoader] = None,
        agent_pool: Optional[AgentPool] = None
    ):
        self.agent = agent
        self.skill_loader = skill_loader
        self.mcp_manager = mcp_manager
        self.role_manager = role_manager
        self.config_loader = config_loader
        self.agent_pool = agent_pool
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
            'role': self._cmd_role,
            'new': self._cmd_new,
            'reload': self._cmd_reload,
            'status': self._cmd_status,
        }
        self._running = True
    
    def is_running(self) -> bool:
        return self._running

    @staticmethod
    def _parse_command_input(user_input: str) -> Optional[Tuple[str, str]]:
        user_input = user_input.strip()
        if not user_input or not user_input.startswith('/'):
            return None
        cmd_parts = user_input[1:].split(maxsplit=1)
        cmd = cmd_parts[0].lower()
        args = cmd_parts[1] if len(cmd_parts) > 1 else ""
        return cmd, args

    @staticmethod
    def _parse_sub_cmd(args: str) -> Tuple[str, str]:
        parts = args.split(maxsplit=1)
        sub_cmd = parts[0].lower() if parts else ""
        sub_args = parts[1] if len(parts) > 1 else ""
        return sub_cmd, sub_args

    @staticmethod
    def _truncate(text: str, max_len: int) -> str:
        return text[:max_len] + "..." if len(text) > max_len else text

    async def handle_async(self, user_input: str) -> Optional[str]:
        parsed = self._parse_command_input(user_input)
        if parsed is None:
            return None

        cmd, args = parsed
        if cmd in self.commands:
            result = self.commands[cmd](args)
            if asyncio.iscoroutine(result):
                return await result
            return result
        else:
            return f"未知命令：{cmd}。输入 /help 查看帮助。"

    def handle(self, user_input: str) -> Optional[str]:
        parsed = self._parse_command_input(user_input)
        if parsed is None:
            return None

        cmd, args = parsed
        if cmd in self.commands:
            result = self.commands[cmd](args)
            if asyncio.iscoroutine(result):
                return "此命令需要异步执行，请使用 handle_async"
            return result
        else:
            return f"未知命令：{cmd}。输入 /help 查看帮助。"
    
    def _cmd_help(self, args: str) -> str:
        """显示帮助信息"""
        return """
可用命令：
  /help          - 显示帮助信息
  /quit, /exit   - 退出程序
  /config        - 显示当前配置
  /history       - 显示对话历史
  /clear         - 清空对话历史
  /new           - 开始新对话（清空上下文，保留角色和系统提示词）
  /reload        - 重新加载所有配置（模型、角色、Skill）

状态查看：
  /status        - 显示当前状态概览
  /status full   - 显示完整状态信息
  /status tools  - 显示当前可用工具
  /status prompt - 显示完整系统提示词

角色管理：
  /role <name>   - 切换到指定角色
  /role list     - 列出所有可用角色
  /role show <name> - 显示角色详细信息

Skill管理：
  /skill list    - 列出所有可用Skills
  /skill show <name> - 显示Skill详情

工具管理：
  /tool list     - 列出所有可用工具
  /prompt show   - 显示当前系统提示词

浏览器管理：
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
        messages = self.agent._query_engine.get_messages()

        if not messages:
            return "对话历史为空"

        lines = ["对话历史："]
        for i, msg in enumerate(messages, 1):
            msg_type = type(msg).__name__
            content = self._truncate(msg.content, 100)
            lines.append(f"  [{i}] {msg_type}: {content}")
        
        return "\n".join(lines)
    
    def _cmd_clear(self, args: str) -> str:
        """清空对话历史"""
        self.agent.clear_context()
        return "对话历史已清空"
    
    def _cmd_skill(self, args: str) -> str:
        sub_cmd, skill_name = self._parse_sub_cmd(args)
        
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
        
        elif sub_cmd == "load":
            parts = args.split()
            skill_names = parts[1:]
            if not skill_names:
                return "请指定Skill名称：/skill load <name> [<name2> ...]"
            
            loaded = []
            already_loaded = []
            not_found = []
            
            for name in skill_names:
                if self.agent.context_manager.is_skill_loaded(name):
                    already_loaded.append(name)
                    continue
                
                if not self.skill_loader.has_skill(name):
                    not_found.append(name)
                    continue
                
                content = self.skill_loader.get_skill_content_sync(name)
                self.agent._system_prompt_registry.add_skill(name, content)
                self.agent._current_system_prompt = self.agent._system_prompt_registry.build()
                self.agent._rebuild_query_engine()
                self.agent.context_manager.mark_skill_loaded(name)
                loaded.append(name)
            
            lines = []
            if loaded:
                lines.append(f"已加载Skill：{', '.join(loaded)}")
            if already_loaded:
                lines.append(f"已加载过，跳过：{', '.join(already_loaded)}")
            if not_found:
                lines.append(f"未找到Skill：{', '.join(not_found)}")
            return "\n".join(lines)
        
        else:
            return "用法：/skill list | show <name> | load <name> [<name2> ...]"
    
    def _format_tool_list(self, tools, desc_max_len: int = 50) -> str:
        if not tools:
            return "没有可用的工具"

        lines = ["可用工具："]
        for tool in tools:
            desc = self._truncate(tool.description, desc_max_len)
            lines.append(f"  - {tool.name}: {desc}")
        return "\n".join(lines)

    def _cmd_tool(self, args: str) -> str:
        sub_cmd, _ = self._parse_sub_cmd(args)

        if sub_cmd == "list":
            return self._format_tool_list(self.agent.tools, desc_max_len=50)
        else:
            return "用法：/tool list"
    
    def _cmd_prompt(self, args: str) -> str:
        sub_cmd, _ = self._parse_sub_cmd(args)

        if sub_cmd == "show":
            prompt = self.agent.get_system_prompt()
            lines = ["系统提示词：", "-" * 40]
            lines.append(self._truncate(prompt, 500))
            return "\n".join(lines)
        else:
            return "用法：/prompt show"
    
    async def _cmd_browser(self, args: str) -> str:
        sub_cmd, _ = self._parse_sub_cmd(args)

        if not self.mcp_manager:
            return "MCP未启用，无法管理浏览器"

        if not self.mcp_manager.is_connected:
            return "MCP未连接"

        if sub_cmd == "status":
            alive = await self.mcp_manager.check_browser_alive()
            status = "运行中" if alive else "已关闭"
            return f"浏览器状态: {status}"

        elif sub_cmd == "close":
            success = await self.mcp_manager.close_browser()
            return "浏览器已关闭" if success else "关闭浏览器失败"

        elif sub_cmd == "reopen":
            success = await self.mcp_manager.ensure_browser()
            return "浏览器已重新打开" if success else "重新打开浏览器失败"

        else:
            return "用法：/browser status | /browser close | /browser reopen"
    
    async def _cmd_role(self, args: str) -> str:
        if not self.role_manager:
            return "角色管理未启用，请检查 RoleManager 配置"

        sub_cmd, role_name = self._parse_sub_cmd(args)
        
        if sub_cmd == "list":
            return await self._role_list()
        elif sub_cmd == "show":
            if not role_name:
                return "请指定角色名称：/role show <name>"
            return await self._role_show(role_name)
        elif sub_cmd:
            return await self._role_switch(sub_cmd)
        else:
            return "用法：/role <name> | /role list | /role show <name>"
    
    async def _role_list(self) -> str:
        """列出所有可用角色"""
        roles = self.role_manager.list_roles()
        if not roles:
            return "没有可用的角色"
        
        current_role = self.role_manager.get_current_role()
        current_name = current_role.name if current_role else None
        
        lines = ["可用角色："]
        for role_name in roles:
            role = self.role_manager.get_role(role_name)
            if role:
                marker = " (当前)" if role_name == current_name else ""
                lines.append(f"  - {role_name}{marker}: {role.description}")
        
        return "\n".join(lines)
    
    async def _role_show(self, name: str) -> str:
        """显示角色详细信息"""
        info = self.role_manager.get_role_info(name)
        if not info:
            return f"未找到角色：{name}"
        
        lines = [
            f"角色: {info['name']}",
            f"描述: {info['description']}",
            "",
            "模型配置:",
            f"  继承默认配置: {'是' if info['model']['inherit'] else '否'}",
            f"  提供商: {info['model']['provider']}",
            f"  模型: {info['model']['name']}",
            f"  Temperature: {info['model']['temperature']}",
            f"  Max Tokens: {info['model']['max_tokens']}",
            "",
            "执行参数:",
            f"  最大上下文Token: {info['execution']['max_context_tokens']}",
            f"  超时时间: {info['execution']['timeout']}秒",
            f"  递归限制: {info['execution']['recursion_limit']}",
            f"  子Agent递归限制: {info['execution']['sub_agent_recursion_limit']}",
            "",
            f"可用工具: {', '.join(info['available_tools']) if info['available_tools'] else '全部'}",
        ]
        
        if info['metadata']:
            lines.append("")
            lines.append("元数据:")
            for key, value in info['metadata'].items():
                lines.append(f"  {key}: {value}")
        
        return "\n".join(lines)
    
    def _update_model_for_role(self, name: str) -> None:
        merged_model = self.role_manager.get_merged_model_config(name)
        if merged_model:
            self.agent.llm = self.agent._create_llm(merged_model)
            self.agent.logger.log_agent_action("model_config_updated", {
                "role_name": name,
                "model_name": merged_model.name,
                "provider": merged_model.provider,
                "temperature": merged_model.temperature,
                "max_tokens": merged_model.max_tokens
            })

    def _format_skills_info(self, role_skills) -> str:
        if not role_skills:
            return ""

        skill_details = []
        for skill_name in role_skills:
            metadata = self.skill_loader.registry.get_skill(skill_name)
            if metadata:
                skill_details.append(f"{metadata.name}: {metadata.description}")
            else:
                skill_details.append(f"{skill_name}: Skill元数据未找到")
        return f"\nSkills: {', '.join(skill_details)}"

    async def _role_switch(self, name: str) -> str:
        try:
            if not self.role_manager.has_role(name):
                return f"角色 '{name}' 不存在。使用 /role list 查看可用角色。"

            role = self.role_manager.switch_role(name)

            self.agent.clear_context()

            role_skills = None
            if role.tools and role.tools.skills:
                role_skills = role.tools.skills

            new_tool_registry = None
            if self.agent_pool:
                new_tool_registry = self.agent_pool._create_tool_registry(
                    mcp_manager=getattr(self.agent, '_mcp_manager', None),
                    role_config=role
                )
                self.agent.role_config = role
                self.agent.reload_tools(new_tool_registry)

            await self.agent.load_role_skills(role_skills)

            self._update_model_for_role(name)

            tools_info = self._get_tools_summary(new_tool_registry, self.agent.tools) if new_tool_registry else ""
            skills_info = self._format_skills_info(role_skills)

            return f"已切换到角色 '{name}'：{role.description}\n上下文已清空，新对话已开始。\n{tools_info}{skills_info}"

        except ConfigValidationError as e:
            return f"切换角色失败：{str(e)}"
        except Exception as e:
            return f"切换角色时发生错误：{str(e)}"
    
    def _get_tools_summary(self, tool_registry, agent_tools=None) -> str:
        tools = agent_tools if agent_tools is not None else tool_registry.get_all_tools()
        if not tools:
            return "工具: 无"
        
        builtin_tools = []
        mcp_tools = []
        other_tools = []
        
        builtin_names = {'spawn_agent', 'shell_tool', 'file_read', 'file_write', 
                        'file_list', 'file_search', 'file_exists', 'file_mkdir', 
                        'file_replace', 'file_delete'}
        
        for tool in tools:
            tool_name = tool.name if hasattr(tool, 'name') else str(tool)
            if tool_name in builtin_names:
                builtin_tools.append(tool_name)
            elif tool_name.startswith('browser_') or tool_name.startswith('mcp_'):
                mcp_tools.append(tool_name)
            else:
                other_tools.append(tool_name)
        
        lines = [f"工具加载完成: {len(tools)}个工具"]
        if builtin_tools:
            lines.append(f"  - 内置工具: {', '.join(builtin_tools)}")
        if mcp_tools:
            lines.append(f"  - MCP工具: {', '.join(mcp_tools)}")
        if other_tools:
            lines.append(f"  - 其他工具: {', '.join(other_tools)}")
        
        return "\n".join(lines)
    
    async def _cmd_new(self, args: str) -> str:
        """清空当前对话历史，开始新对话"""
        try:
            self.agent.clear_context()
            
            current_role = self.role_manager.get_current_role() if self.role_manager else None
            if current_role:
                self.agent.reload_system_prompt(current_role)
            
            return "新对话已开始。当前角色和系统提示词已保留，浏览器状态保持不变。"
            
        except Exception as e:
            return f"开始新对话时发生错误：{str(e)}"
    
    async def _cmd_reload(self, args: str) -> str:
        """重新加载所有配置"""
        results = []
        
        try:
            if self.role_manager:
                self.role_manager.reload_roles()
                results.append("✓ 角色配置已重新加载")
            
            if self.config_loader:
                self.config_loader.load_all()
                results.append("✓ 模型配置已重新加载")
            
            if self.skill_loader:
                await self.skill_loader.load_skill_metadata()
                results.append("✓ Skill配置已重新加载")
            
            if not results:
                return "没有可重新加载的配置"
            
            self.agent._rebuild_query_engine()
            
            return "配置重新加载完成：\n" + "\n".join(results)
            
        except Exception as e:
            return f"重新加载配置时发生错误：{str(e)}"
    
    def _cmd_status(self, args: str) -> str:
        sub_cmd, _ = self._parse_sub_cmd(args)
        
        if sub_cmd == "full":
            return self._status_full()
        elif sub_cmd == "tools":
            return self._status_tools()
        elif sub_cmd == "prompt":
            return self._status_prompt()
        else:
            return self._status_overview()
    
    def _status_overview(self) -> str:
        """显示状态概览"""
        current_role = self.role_manager.get_current_role() if self.role_manager else None
        role_name = current_role.name if current_role else "未设置"
        role_desc = current_role.description if current_role else ""
        
        tool_count = len(self.agent.tools)
        
        prompt = self.agent.get_current_system_prompt()
        prompt_length = len(prompt)
        
        lines = [
            "当前状态概览：",
            "=" * 50,
            f"角色: {role_name}",
            f"描述: {role_desc}",
            f"可用工具数量: {tool_count}",
            f"系统提示词长度: {prompt_length} 字符",
            "",
            "提示：使用 /status full 查看完整系统提示词",
            "      使用 /status tools 查看工具列表"
        ]
        return "\n".join(lines)
    
    def _status_full(self) -> str:
        """显示完整状态信息"""
        lines = [
            self._status_overview(),
            "\n" + "=" * 50,
            "\n系统提示词（含工具说明）：",
            self._status_prompt()
        ]
        return "\n".join(lines)
    
    def _status_tools(self) -> str:
        tools = self.agent.tools
        if not tools:
            return "没有可用的工具"

        lines = ["可用工具列表："]
        for i, tool in enumerate(tools, 1):
            desc = self._truncate(tool.description, 100)
            lines.append(f"  {i}. {tool.name}")
            lines.append(f"     描述: {desc}")
        return "\n".join(lines)
    
    def _status_prompt(self) -> str:
        """显示完整系统提示词"""
        prompt = self.agent.get_current_system_prompt()
        lines = [
            "当前系统提示词（包含工具说明）：",
            "=" * 50,
            prompt
        ]
        return "\n".join(lines)
