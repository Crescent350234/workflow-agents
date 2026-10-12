"""脚本化 LLM：用于无 API Key 的离线演示。

它按构造时给定的「剧本」顺序返回预设消息，从而让 ReAct 循环在无需真实大模型时
也能完整跑通：编码 Agent 写文件 → 测试失败 → 修复 Agent 读/改/验 → 测试通过。

仅用于演示与教学，不影响真实 LLM 接入路径（LLMClient 保持不变）。
"""


class ScriptedLLM:
    def __init__(self, script):
        self.script = list(script)
        self.i = 0

    def chat(self, messages, tools=None, max_retries=3):
        if self.i >= len(self.script):
            return {"role": "assistant", "content": "（演示剧本已结束）"}
        resp = self.script[self.i]
        self.i += 1
        return resp
