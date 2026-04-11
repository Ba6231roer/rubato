from ..base import BaseCommand
from ..models import CommandResult, ResultType
from ..registry import command
from ...config.validators import ConfigValidationError
from ...utils.logger import get_llm_logger


@command
class RoleCommand(BaseCommand):
    name = "role"
    description = "角色管理"
    usage = "/role <name> | /role list | /role show <name>"
    
    def __init__(self):
        self._logger = get_llm_logger()
    
    async def execute(self, args: str, context) -> CommandResult:
        if not context.role_manager:
            return CommandResult(
                type=ResultType.ERROR,
                message="角色管理未启用，请检查 RoleManager 配置"
            )
        
        parts = args.split(maxsplit=1)
        sub_cmd = parts[0].lower() if parts else ""
        role_name = parts[1] if len(parts) > 1 else ""
        
        if sub_cmd == "list":
            return await self._list_roles(context)
        elif sub_cmd == "show":
            if not role_name:
                return CommandResult(
                    type=ResultType.ERROR,
                    message="请指定角色名称：/role show <name>"
                )
            return await self._show_role(context, role_name)
        elif sub_cmd:
            return await self._switch_role(context, sub_cmd)
        else:
            return CommandResult(
                type=ResultType.INFO,
                message=self.usage
            )
    
    async def _list_roles(self, context) -> CommandResult:
        roles = context.role_manager.list_roles()
        if not roles:
            return CommandResult(
                type=ResultType.INFO,
                message="没有可用的角色"
            )
        
        current_role = context.role_manager.get_current_role()
        current_name = current_role.name if current_role else None
        
        role_list = []
        lines = ["可用角色："]
        for role_name in roles:
            role = context.role_manager.get_role(role_name)
            if role:
                is_current = role_name == current_name
                marker = " (当前)" if is_current else ""
                lines.append(f"  - {role_name}{marker}: {role.description}")
                role_list.append({
                    "name": role_name,
                    "description": role.description,
                    "is_current": is_current
                })
        
        return CommandResult(
            type=ResultType.INFO,
            message="\n".join(lines),
            data={"roles": role_list}
        )
    
    async def _show_role(self, context, name: str) -> CommandResult:
        info = context.role_manager.get_role_info(name)
        if not info:
            return CommandResult(
                type=ResultType.ERROR,
                message=f"未找到角色：{name}"
            )
        
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
        
        return CommandResult(
            type=ResultType.INFO,
            message="\n".join(lines),
            data={"role_info": info}
        )
    
    async def _switch_role(self, context, name: str) -> CommandResult:
        try:
            if not context.role_manager.has_role(name):
                return CommandResult(
                    type=ResultType.ERROR,
                    message=f"角色 '{name}' 不存在。使用 /role list 查看可用角色。"
                )
            
            role = context.role_manager.switch_role(name)
            
            context.agent.clear_context()
            
            role_skills = None
            if role.tools and role.tools.skills:
                role_skills = role.tools.skills
            
            new_tool_registry = context.agent_pool._create_tool_registry(
                mcp_manager=getattr(context.agent, '_mcp_manager', None),
                role_config=role
            )
            
            context.agent.role_config = role
            context.agent.reload_tools(new_tool_registry)
            
            await context.agent.load_role_skills(role_skills)
            
            merged_model = context.role_manager.get_merged_model_config(name)
            if merged_model:
                context.agent.llm = context.agent._create_llm()
            
            tools_info = self._get_tools_summary(new_tool_registry)
            
            skills_info = ""
            if role_skills:
                skills_info = f"\nSkills: {', '.join(role_skills)}"
            
            skills_data = []
            if role_skills:
                for skill_name in role_skills:
                    metadata = context.skill_loader.registry.get_skill(skill_name)
                    if metadata:
                        skills_data.append({
                            "name": metadata.name,
                            "description": metadata.description,
                            "version": metadata.version,
                            "triggers": list(metadata.triggers) if metadata.triggers else []
                        })
                    else:
                        skills_data.append({
                            "name": skill_name,
                            "description": "Skill元数据未找到",
                            "version": "",
                            "triggers": []
                        })
            
            return CommandResult(
                type=ResultType.SUCCESS,
                message=f"已切换到角色 '{name}'：{role.description}\n上下文已清空，新对话已开始。\n{tools_info}{skills_info}",
                data={"role": name, "description": role.description, "skills": skills_data}
            )
            
        except ConfigValidationError as e:
            return CommandResult(
                type=ResultType.ERROR,
                message=f"切换角色失败：{str(e)}"
            )
        except Exception as e:
            return CommandResult(
                type=ResultType.ERROR,
                message=f"切换角色时发生错误：{str(e)}"
            )
    
    def _get_tools_summary(self, tool_registry) -> str:
        tools = tool_registry.get_all_tools()
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
