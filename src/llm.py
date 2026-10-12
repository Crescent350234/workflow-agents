"""LLM 客户端：兼容 OpenAI Chat Completions 接口（含 tool/function calling）。

特性：
- 仅使用 Python 标准库（urllib），无需安装任何第三方包即可运行。
- 支持真实 LLM 调用（OpenAI / 通义千问 DashScope / DeepSeek 等兼容接口）。
- 内置 Mock 模式：无 API Key 时也能完整跑通 Agent 循环，方便演示与评分。
- 内置错误重试机制（见 chat() 的 max_retries）。

本文件直接复用 Homework 1 的实现，未做改动。
"""
import json
import os
import re
import time
import urllib.request
import urllib.error


class LLMError(Exception):
    """LLM 调用相关异常。"""


class LLMClient:
    def __init__(self, base_url=None, api_key=None, model=None, mock=None,
                 temperature=0.3, timeout=60):
        self.base_url = (base_url or os.getenv("LLM_BASE_URL",
                                               "https://api.openai.com/v1")).rstrip("/")
        self.api_key = api_key if api_key is not None else os.getenv("LLM_API_KEY", "")
        self.model = model or os.getenv("LLM_MODEL", "gpt-4o-mini")
        # mock 优先级：显式参数 > 环境变量 MOCK_MODE > 无 API Key
        if mock is None:
            mock = os.getenv("MOCK_MODE", "0") == "1" or not self.api_key
        self.mock = mock
        self.temperature = temperature
        self.timeout = timeout

    def chat(self, messages, tools=None, max_retries=3):
        """调用 LLM，返回 {'role','content','tool_calls':[...]}。

        tool_calls 元素格式：{'id','name','arguments':dict}
        """
        last_err = None
        for attempt in range(max_retries):
            try:
                if self.mock:
                    return self._mock_chat(messages, tools)
                return self._real_chat(messages, tools)
            except LLMError as e:
                last_err = e
                # 指数退避后重试
                time.sleep(1.5 * (attempt + 1))
        raise LLMError(f"LLM 调用失败（已重试 {max_retries} 次）: {last_err}")

    # ---------- 真实调用 ----------
    def _real_chat(self, messages, tools):
        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, method="POST")
        req.add_header("Content-Type", "application/json")
        req.add_header("Authorization", f"Bearer {self.api_key}")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            raise LLMError(f"HTTP {e.code}: {e.reason}")
        except Exception as e:  # 网络/解析错误
            raise LLMError(str(e))

        choice = body["choices"][0]["message"]
        result = {"role": "assistant", "content": choice.get("content") or ""}
        tool_calls = choice.get("tool_calls") or []
        if tool_calls:
            result["tool_calls"] = [
                {
                    "id": tc.get("id"),
                    "name": tc["function"]["name"],
                    "arguments": json.loads(tc["function"].get("arguments") or "{}"),
                }
                for tc in tool_calls
            ]
        return result

    # ---------- Mock 演示模式 ----------
    def _mock_chat(self, messages, tools):
        """演示用：根据对话状态模拟一次工具调用或最终回答。

        目标：让 Agent 循环在无需 API Key 时也能完整跑通（输入→推理→工具→输出）。
        """
        last_user = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                last_user = m.get("content", "")
                break

        # 若上下文中已出现工具结果，则给出最终综合回答
        has_tool_result = any(m.get("role") == "tool" for m in messages)
        if has_tool_result:
            return {
                "role": "assistant",
                "content": (
                    "【演示模式 · 模拟 LLM 最终回答】\n"
                    "我已通过工具获取所需信息，分析结论如下：\n\n"
                    "1. 代码结构清晰，函数职责划分合理。\n"
                    "2. 建议为关键函数补充类型注解与 docstring。\n"
                    "3. 错误处理可更健壮：增加重试与结构化日志。\n"
                    "4. 核心逻辑建议补充单元测试（可使用 generate_unit_test 工具）。\n\n"
                    "（说明：当前为 MOCK_MODE=1 演示回答。配置 LLM_API_KEY 后，"
                    "上述结论将由真实大模型基于你的代码动态生成。）"
                ),
            }

        # 否则尝试发起一次相关工具调用以展示 Agent 循环
        if tools:
            path_match = re.search(
                r"([\w./\\-]+\.(?:py|js|ts|tsx|java|go|cpp|c|rs|txt|md|json))",
                last_user,
            )
            if path_match:
                for t in tools:
                    if t["function"]["name"] == "read_file":
                        return {
                            "role": "assistant",
                            "content": "我先读取你提到的文件以便进行分析。",
                            "tool_calls": [{
                                "id": "call_mock_1",
                                "name": "read_file",
                                "arguments": {"path": path_match.group(1)},
                            }],
                        }
            for t in tools:
                if t["function"]["name"] == "search_web":
                    return {
                        "role": "assistant",
                        "content": "我先检索相关技术资料。",
                        "tool_calls": [{
                            "id": "call_mock_1",
                            "name": "search_web",
                            "arguments": {"query": last_user[:60]},
                        }],
                    }
        return {
            "role": "assistant",
            "content": (
                "【演示模式 · 模拟 LLM 回答】\n"
                "这是 Mock 模式下生成的回复。请配置 LLM_API_KEY 与 LLM_BASE_URL "
                "以启用真实大模型。\n\n你的问题：\n" + last_user
            ),
        }
