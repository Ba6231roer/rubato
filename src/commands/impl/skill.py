from ..base import BaseCommand
from ..models import CommandResult, ResultType
from ..registry import command


@command
class SkillCommand(BaseCommand):
    name = "skill"
    description = "Skill管理"
    usage = "/skill list | show <name> | load <name> [<name2> ...]"
    
    async def execute(self, args: str, context) -> CommandResult:
        if not context.skill_loader:
            return CommandResult(
                type=ResultType.ERROR,
                message="Skill加载器未初始化"
            )
        
        parts = args.split()
        sub_cmd = parts[0].lower() if parts else ""
        
        if sub_cmd == "list":
            return await self._list_skills(context)
        elif sub_cmd == "show":
            skill_name = parts[1] if len(parts) > 1 else ""
            if not skill_name:
                return CommandResult(
                    type=ResultType.ERROR,
                    message="请指定Skill名称：/skill show <name>"
                )
            return await self._show_skill(context, skill_name)
        elif sub_cmd == "load":
            skill_names = parts[1:]
            if not skill_names:
                return CommandResult(
                    type=ResultType.ERROR,
                    message="请指定Skill名称：/skill load <name> [<name2> ...]"
                )
            return await self._load_skills(context, skill_names)
        else:
            return CommandResult(
                type=ResultType.INFO,
                message=self.usage
            )
    
    async def _list_skills(self, context) -> CommandResult:
        skills = context.skill_loader.list_skills()
        if not skills:
            return CommandResult(
                type=ResultType.INFO,
                message="没有可用的Skills"
            )
        
        skill_list = []
        lines = ["可用Skills："]
        for skill in skills:
            lines.append(f"  - {skill.name}: {skill.description}")
            skill_list.append({
                "name": skill.name,
                "description": skill.description,
                "version": skill.version,
                "triggers": list(skill.triggers) if skill.triggers else []
            })
        
        return CommandResult(
            type=ResultType.INFO,
            message="\n".join(lines),
            data={"skills": skill_list}
        )
    
    async def _show_skill(self, context, name: str) -> CommandResult:
        metadata = context.skill_loader.registry.get_skill(name)
        if not metadata:
            return CommandResult(
                type=ResultType.ERROR,
                message=f"未找到Skill：{name}"
            )
        
        lines = [
            f"Skill: {metadata.name}",
            f"描述: {metadata.description}",
            f"版本: {metadata.version}",
            f"触发词: {', '.join(metadata.triggers)}",
        ]
        
        return CommandResult(
            type=ResultType.INFO,
            message="\n".join(lines),
            data={
                "name": metadata.name,
                "description": metadata.description,
                "version": metadata.version,
                "triggers": list(metadata.triggers)
            }
        )
    
    async def _load_skills(self, context, names: list) -> CommandResult:
        loaded = []
        already_loaded = []
        not_found = []
        
        for name in names:
            if context.agent.context_manager.is_skill_loaded(name):
                already_loaded.append(name)
                if context.agent._system_prompt_registry.has_skill(name):
                    context.agent._system_prompt_registry.mark_skill_referenced(name)
                continue
            
            if not context.skill_loader.has_skill(name):
                not_found.append(name)
                continue
            
            content = await context.skill_loader.load_full_skill(name)
            context.agent._system_prompt_registry.add_skill(name, content)
            context.agent._current_system_prompt = context.agent._system_prompt_registry.build()
            context.agent._rebuild_query_engine()
            context.agent.context_manager.mark_skill_loaded(name)
            loaded.append(name)
        
        lines = []
        if loaded:
            lines.append(f"已加载Skill：{', '.join(loaded)}")
        if already_loaded:
            lines.append(f"已加载过，跳过：{', '.join(already_loaded)}")
        if not_found:
            lines.append(f"未找到Skill：{', '.join(not_found)}")
        
        return CommandResult(
            type=ResultType.INFO,
            message="\n".join(lines),
            data={"loaded": loaded, "already_loaded": already_loaded, "not_found": not_found}
        )
