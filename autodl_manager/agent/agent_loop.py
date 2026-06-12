"""Agent Loop — 基于 LangGraph 的 ReAct 决策循环。

核心逻辑：用户自然语言 → LLM 决策 → 调用 Tool → 拿到结果 → LLM 再决策
直到 LLM 认为任务完成，返回最终回答。

使用：
  from autodl_manager.agent.agent_loop import run_agent_query

  result = await run_agent_query(
      "检查所有实例，利用率低于10%的建议关机",
      api_key="sk-xxx",
      api_base="https://api.deepseek.com/v1",
      model="deepseek-chat",
  )
"""

from typing import Annotated, TypedDict, Optional
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage

from .tools import ALL_TOOLS
from .prompts import get_system_prompt


# ─── 状态定义 ───

class AgentState(TypedDict):
    """Agent 全局状态。messages 是 append-only 的对话历史。"""
    messages: Annotated[list, add_messages]


# ─── Agent 构建 ───

def create_agent_loop(
    api_key: str = "",
    api_base: str = "https://api.deepseek.com/v1",
    model: str = "deepseek-chat",
    temperature: float = 0.1,
):
    """创建 Agent 决策循环。

    Args:
        api_key: LLM API 密钥
        api_base: API 地址（默认 DeepSeek，支持任何 OpenAI 兼容 API）
        model: 模型名称
        temperature: 模型温度（0-1），越低越确定

    Returns:
        编译后的 LangGraph App，可调用 .ainvoke() 执行。
    """
    llm = ChatOpenAI(
        model=model,
        api_key=api_key or "not-needed",  # ChatOpenAI 要求非空
        base_url=api_base,
        temperature=temperature,
    )
    llm_with_tools = llm.bind_tools(ALL_TOOLS)

    tool_node = ToolNode(ALL_TOOLS)

    def should_continue(state: AgentState) -> str:
        """判断下一步：调工具还是结束。"""
        last_message = state["messages"][-1]
        if hasattr(last_message, "tool_calls") and last_message.tool_calls:
            return "tools"
        return END

    def call_model(state: AgentState):
        """LLM 决策：基于当前对话历史决定下一步行动。"""
        messages = [SystemMessage(content=get_system_prompt())] + state["messages"]
        response = llm_with_tools.invoke(messages)
        return {"messages": [response]}

    graph = StateGraph(AgentState)
    graph.add_node("agent", call_model)
    graph.add_node("tools", tool_node)
    graph.set_entry_point("agent")
    graph.add_conditional_edges("agent", should_continue, {"tools": "tools", END: END})
    graph.add_edge("tools", "agent")

    return graph.compile()


# ─── 便捷调用 ───

async def run_agent_query(
    query: str,
    api_key: str = "",
    api_base: str = "https://api.deepseek.com/v1",
    model: str = "deepseek-chat",
) -> str:
    """执行一次 Agent 查询。

    Args:
        query: 用户自然语言请求。例如：
            "检查所有GPU实例"
            "哪些实例利用率低于10%？"
            "帮我关掉空闲的GPU"
            "余额还有多少？"
        api_key: LLM API 密钥
        api_base: API 地址
        model: 模型名称

    Returns:
        Agent 的最终回答文本。
    """
    app = create_agent_loop(api_key=api_key, api_base=api_base, model=model)
    result = await app.ainvoke({"messages": [HumanMessage(content=query)]})
    last_message = result["messages"][-1]
    return last_message.content
