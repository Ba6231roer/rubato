import re
from typing import Optional


NO_TOOLS_PREAMBLE = """CRITICAL: Respond with TEXT ONLY. Do NOT call any tools.

- Do NOT use Read, Bash, Grep, Glob, Edit, Write, or ANY other tool.
- You already have all the context you need in the conversation above.
- Tool calls will be REJECTED and will waste your only turn — you will fail the task.
- Your entire response must be plain text: an <analysis> block followed by a <summary> block."""


NO_TOOLS_TRAILER = """REMINDER: Do NOT call any tools. Respond with plain text only — an <analysis> block followed by a <summary> block. Tool calls will be rejected and you will fail the task."""


BASE_COMPACT_PROMPT = """Your task is to create a detailed summary of the conversation so far to serve as a persistent memory for a continued session. This summary must be comprehensive enough to allow seamless continuation without losing any critical context.

Analyze the conversation and produce a structured summary with the following sections:

1. **Primary Request and Intent**: The user's main goal and what they are trying to accomplish. Be specific about their requirements and constraints. If the user provided a specific task specification, test case steps, or operation checklist, you MUST preserve the core content of these specifications in full detail, including step numbers, operation targets, and key parameters.

2. **Task Specification**: If the user provided a specific task specification, test case steps, or operation checklist, reproduce it here with as much detail as possible. Include step numbers, operation targets, expected results, and key parameters. If no specific task specification was provided, write 'N/A'.

3. **Key Technical Concepts**: Technologies, frameworks, libraries, APIs, and key technical details relevant to the conversation. Include version numbers if mentioned.

4. **Files and Code Sections**: List all files that were created, modified, or discussed. For each file, describe what was changed and why. Include relevant code snippets or describe the key logic.

5. **Errors and Fixes**: Any errors encountered during the conversation and how they were resolved. Include error messages and the solutions applied.

6. **Problem Solving**: Describe the problem-solving approach taken. What strategies were tried, what worked, and what didn't. Include any debugging steps.

7. **All User Messages**: A complete list of all messages sent by the user, in order. Preserve the exact intent of each message. Pay special attention to preserving the content of the user's FIRST message, which contains the core task objective for the entire conversation.

8. **Pending Tasks**: Any tasks that were requested but not yet completed. Be specific about what remains to be done.

9. **Current Work**: What was being actively worked on when the conversation ended. Include the current state of any in-progress changes.

10. **Optional Next Step**: Suggest the next logical step to continue the work, based on the current state and pending tasks.

First, draft your analysis in an <analysis> block. Think through each section carefully, considering what information is essential for continuing the conversation. Then, produce your structured summary in a <summary> block.

<analysis>
[DRAFTING: Analyze the conversation here. Think through each section. Identify all key details, decisions, and context needed for continuation. This is your scratchpad — be thorough.]
</analysis>

<summary>
1. Primary Request and Intent:
[Fill in]

2. Task Specification:
[Fill in]

3. Key Technical Concepts:
[Fill in]

4. Files and Code Sections:
[Fill in]

5. Errors and Fixes:
[Fill in]

6. Problem Solving:
[Fill in]

7. All User Messages:
[Fill in]

8. Pending Tasks:
[Fill in]

9. Current Work:
[Fill in]

10. Optional Next Step:
[Fill in]
</summary>"""


PARTIAL_COMPACT_PROMPT_FROM = """Your task is to create a detailed summary of the recent messages in this conversation to serve as a persistent memory for a continued session. Focus specifically on the messages after the previously retained context. This summary must be comprehensive enough to allow seamless continuation without losing any critical context.

Analyze the recent messages and produce a structured summary with the following sections:

1. **Primary Request and Intent**: The user's main goal in the recent messages and what they are trying to accomplish. Be specific about their requirements and constraints. If the user provided a specific task specification, test case steps, or operation checklist, you MUST preserve the core content of these specifications in full detail, including step numbers, operation targets, and key parameters.

2. **Task Specification**: If the user provided a specific task specification, test case steps, or operation checklist, reproduce it here with as much detail as possible. Include step numbers, operation targets, expected results, and key parameters. If no specific task specification was provided, write 'N/A'.

3. **Key Technical Concepts**: Technologies, frameworks, libraries, APIs, and key technical details relevant to the recent messages. Include version numbers if mentioned.

4. **Files and Code Sections**: List all files that were created, modified, or discussed in the recent messages. For each file, describe what was changed and why. Include relevant code snippets or describe the key logic.

5. **Errors and Fixes**: Any errors encountered in the recent messages and how they were resolved. Include error messages and the solutions applied.

6. **Problem Solving**: Describe the problem-solving approach taken in the recent messages. What strategies were tried, what worked, and what didn't. Include any debugging steps.

7. **All User Messages**: A complete list of all user messages in the recent portion, in order. Preserve the exact intent of each message. Pay special attention to preserving the content of the user's FIRST message, which contains the core task objective for the entire conversation.

8. **Pending Tasks**: Any tasks that were requested but not yet completed. Be specific about what remains to be done.

9. **Current Work**: What was being actively worked on in the recent messages. Include the current state of any in-progress changes.

10. **Optional Next Step**: Suggest the next logical step to continue the work, based on the current state and pending tasks.

First, draft your analysis in an <analysis> block. Think through each section carefully, considering what information is essential for continuing the conversation. Then, produce your structured summary in a <summary> block.

<analysis>
[DRAFTING: Analyze the recent messages here. Think through each section. Identify all key details, decisions, and context needed for continuation. This is your scratchpad — be thorough.]
</analysis>

<summary>
1. Primary Request and Intent:
[Fill in]

2. Task Specification:
[Fill in]

3. Key Technical Concepts:
[Fill in]

4. Files and Code Sections:
[Fill in]

5. Errors and Fixes:
[Fill in]

6. Problem Solving:
[Fill in]

7. All User Messages:
[Fill in]

8. Pending Tasks:
[Fill in]

9. Current Work:
[Fill in]

10. Optional Next Step:
[Fill in]
</summary>"""


PARTIAL_COMPACT_PROMPT_UP_TO = """Your task is to create a detailed summary of the earlier messages in this conversation to serve as a persistent memory for a continued session. Focus specifically on the messages before the most recent ones, which will be preserved verbatim. This summary must be comprehensive enough to allow seamless continuation without losing any critical context.

Analyze the earlier messages and produce a structured summary with the following sections:

1. **Primary Request and Intent**: The user's main goal in the earlier messages and what they were trying to accomplish. Be specific about their requirements and constraints. If the user provided a specific task specification, test case steps, or operation checklist, you MUST preserve the core content of these specifications in full detail, including step numbers, operation targets, and key parameters.

2. **Task Specification**: If the user provided a specific task specification, test case steps, or operation checklist, reproduce it here with as much detail as possible. Include step numbers, operation targets, expected results, and key parameters. If no specific task specification was provided, write 'N/A'.

3. **Key Technical Concepts**: Technologies, frameworks, libraries, APIs, and key technical details relevant to the earlier messages. Include version numbers if mentioned.

4. **Files and Code Sections**: List all files that were created, modified, or discussed in the earlier messages. For each file, describe what was changed and why. Include relevant code snippets or describe the key logic.

5. **Errors and Fixes**: Any errors encountered in the earlier messages and how they were resolved. Include error messages and the solutions applied.

6. **Problem Solving**: Describe the problem-solving approach taken in the earlier messages. What strategies were tried, what worked, and what didn't. Include any debugging steps.

7. **All User Messages**: A complete list of all user messages in the earlier portion, in order. Preserve the exact intent of each message. Pay special attention to preserving the content of the user's FIRST message, which contains the core task objective for the entire conversation.

8. **Pending Tasks**: Any tasks that were requested but not yet completed. Be specific about what remains to be done.

9. **Current Work**: What was being actively worked on in the earlier messages. Include the current state of any in-progress changes.

10. **Context for Continuing Work**: Key context and decisions from these earlier messages that are needed to understand and continue the work in the preserved recent messages.

First, draft your analysis in an <analysis> block. Think through each section carefully, considering what information is essential for continuing the conversation. Then, produce your structured summary in a <summary> block.

<analysis>
[DRAFTING: Analyze the earlier messages here. Think through each section. Identify all key details, decisions, and context needed for continuation. This is your scratchpad — be thorough.]
</analysis>

<summary>
1. Primary Request and Intent:
[Fill in]

2. Task Specification:
[Fill in]

3. Key Technical Concepts:
[Fill in]

4. Files and Code Sections:
[Fill in]

5. Errors and Fixes:
[Fill in]

6. Problem Solving:
[Fill in]

7. All User Messages:
[Fill in]

8. Pending Tasks:
[Fill in]

9. Current Work:
[Fill in]

10. Context for Continuing Work:
[Fill in]
</summary>"""


def get_compact_prompt(custom_instructions: Optional[str] = None) -> str:
    parts = [NO_TOOLS_PREAMBLE, "", BASE_COMPACT_PROMPT]
    if custom_instructions:
        parts.append("")
        parts.append("Additional Instructions:")
        parts.append(custom_instructions)
    parts.append("")
    parts.append(NO_TOOLS_TRAILER)
    return "\n".join(parts)


def get_partial_compact_prompt(
    custom_instructions: Optional[str] = None,
    direction: str = "from",
) -> str:
    if direction == "from":
        base_prompt = PARTIAL_COMPACT_PROMPT_FROM
    elif direction == "up_to":
        base_prompt = PARTIAL_COMPACT_PROMPT_UP_TO
    else:
        raise ValueError(f"Invalid direction: {direction!r}. Must be 'from' or 'up_to'.")

    parts = [NO_TOOLS_PREAMBLE, "", base_prompt]
    if custom_instructions:
        parts.append("")
        parts.append("Additional Instructions:")
        parts.append(custom_instructions)
    parts.append("")
    parts.append(NO_TOOLS_TRAILER)
    return "\n".join(parts)


def format_compact_summary(summary: str) -> str:
    summary = re.sub(r"<analysis>.*?</analysis>", "", summary, flags=re.DOTALL)
    summary = re.sub(r"</?summary>", "", summary)
    summary = re.sub(r"^\s*\n", "", summary)
    summary = re.sub(r"\n\s*\n\s*\n", "\n\n", summary)
    summary = summary.strip()
    if summary and not summary.startswith("Summary:"):
        summary = "Summary:\n" + summary
    return summary


def get_compact_user_summary_message(
    summary: str,
    suppress_follow_up_questions: bool = False,
    recent_messages_preserved: bool = False,
) -> str:
    parts = [
        "This session is being continued from a previous conversation that ran out of context. Here is a summary of the previous conversation:",
        "",
        summary,
    ]
    if recent_messages_preserved:
        parts.append("")
        parts.append("Recent messages are preserved verbatim.")
    if suppress_follow_up_questions:
        parts.append("")
        parts.append("Continue the task without asking any follow-up questions. Proceed directly with the next step based on the summary above.")
    return "\n".join(parts)
