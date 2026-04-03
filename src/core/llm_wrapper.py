from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage
from langchain_core.outputs import ChatResult, ChatGeneration
from typing import List, Optional, Any
import time


class RobustChatOpenAI(ChatOpenAI):
    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[Any] = None,
        **kwargs: Any,
    ) -> ChatResult:
        max_retries = 3
        retry_delay = 1
        
        for attempt in range(max_retries):
            try:
                result = super()._generate(messages, stop, run_manager, **kwargs)
                
                if result.generations and len(result.generations) > 0:
                    return result
                else:
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay)
                        continue
                    else:
                        return ChatResult(
                            generations=[ChatGeneration(
                                message=BaseMessage(content="API返回空响应，请重试", type="ai")
                            )]
                        )
                        
            except TypeError as e:
                if "null value for 'choices'" in str(e):
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay)
                        continue
                    else:
                        return ChatResult(
                            generations=[ChatGeneration(
                                message=BaseMessage(
                                    content="API响应格式异常(choices为null)，已达到最大重试次数",
                                    type="ai"
                                )
                            )]
                        )
                else:
                    raise
            except Exception as e:
                raise
        
        return ChatResult(
            generations=[ChatGeneration(
                message=BaseMessage(content="生成失败，请重试", type="ai")
            )]
        )
    
    async def _agenerate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[Any] = None,
        **kwargs: Any,
    ) -> ChatResult:
        max_retries = 3
        retry_delay = 1
        
        for attempt in range(max_retries):
            try:
                result = await super()._agenerate(messages, stop, run_manager, **kwargs)
                
                if result.generations and len(result.generations) > 0:
                    return result
                else:
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay)
                        continue
                    else:
                        return ChatResult(
                            generations=[ChatGeneration(
                                message=BaseMessage(content="API返回空响应，请重试", type="ai")
                            )]
                        )
                        
            except TypeError as e:
                if "null value for 'choices'" in str(e):
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay)
                        continue
                    else:
                        return ChatResult(
                            generations=[ChatGeneration(
                                message=BaseMessage(
                                    content="API响应格式异常(choices为null)，已达到最大重试次数",
                                    type="ai"
                                )
                            )]
                        )
                else:
                    raise
            except Exception as e:
                raise
        
        return ChatResult(
            generations=[ChatGeneration(
                message=BaseMessage(content="生成失败，请重试", type="ai")
            )]
        )
