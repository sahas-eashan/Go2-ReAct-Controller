from __future__ import annotations

import threading
import uuid
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_openai import ChatOpenAI
from rai.agents.langchain import create_react_runnable

from unitree_go2_robot_controller.config import AppConfig
from unitree_go2_robot_controller.prompts import SYSTEM_PROMPT
from unitree_go2_robot_controller.robot_runtime import RobotRuntime
from unitree_go2_robot_controller.tools import build_tools


def _message_text(message: BaseMessage) -> str:
    content = message.content
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                text = str(item.get("text", "")).strip()
                if text:
                    parts.append(text)
            else:
                text = str(item).strip()
                if text:
                    parts.append(text)
        return "\n".join(parts).strip()
    return str(content).strip()


def _last_ai_text(messages: list[BaseMessage]) -> str:
    for message in reversed(messages):
        if isinstance(message, AIMessage):
            text = _message_text(message)
            if text:
                return text
    return ""


class RobotAgentService:
    def __init__(self, config: AppConfig, runtime: RobotRuntime):
        self._lock = threading.RLock()
        self._sessions: dict[str, dict[str, list[BaseMessage]]] = {}
        self._agent = create_react_runnable(
            llm=ChatOpenAI(
                model=config.openai_model,
                api_key=config.openai_api_key,
                temperature=0,
                streaming=False,
            ),
            tools=build_tools(config, runtime),
            system_prompt=SYSTEM_PROMPT,
        )

    def chat(self, text: str, session_id: str | None = None) -> dict[str, Any]:
        normalized = text.strip()
        if not normalized:
            return {
                "status": "error",
                "error_code": "empty_input",
                "reason": "text is required",
            }

        resolved_session_id = session_id or uuid.uuid4().hex
        with self._lock:
            state = self._sessions.setdefault(resolved_session_id, {"messages": []})
            state["messages"].append(HumanMessage(content=normalized))
            result = self._agent.invoke(state)
            messages = list(result["messages"])
            self._sessions[resolved_session_id] = {"messages": messages}

        response = _last_ai_text(messages)
        return {
            "status": "ok",
            "session_id": resolved_session_id,
            "response": response,
        }
