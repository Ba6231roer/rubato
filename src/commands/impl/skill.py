from ..base import BaseCommand
from ..models import CommandResult, ResultType
from ..registry import command


@command
class SkillCommand(BaseCommand):
    name = "skill"
    description = "Skill管理"
    usage = "/skill list | /skill show <name>"
    
    async def execute(self, args: str, context) -> CommandResult:
        if not context.skill_loader:
            return CommandResult(
                type=ResultType.ERROR,
                message="Skill加载器未初始化"
            )
        
        parts = args.split(maxsplit=1)
        sub_cmd = parts[0].lower() if parts else ""
        skill_name = parts[1] if len(parts) > 1 else ""
        
        if sub_cmd == "list":
            return await self._list_skills(context)
        elif sub_cmd == "show":
            if not skill_name:
                return CommandResult(
                    type=ResultType.ERROR,
                    message="请指定Skill名称：/skill show <name>"
                )
            return await self._show_skill(context, skill_name)
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
