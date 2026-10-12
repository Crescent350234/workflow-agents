"""对话记忆：内存存储 + JSON 文件持久化，支持上下文记忆与长度裁剪。

本文件直接复用 Homework 1 的实现，未做改动。
"""
import json
import os


class Memory:
    def __init__(self, path="memory.json", max_turns=20):
        self.path = path
        self.max_turns = max_turns
        self.history = self._load()

    def _load(self):
        if os.path.exists(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return []
        return []

    def save(self):
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self.history, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def add(self, role, content=None, tool_calls=None, name=None, tool_call_id=None):
        msg = {"role": role}
        if content is not None:
            msg["content"] = content
        if tool_calls is not None:
            msg["tool_calls"] = tool_calls
        if name is not None:
            msg["name"] = name
        if tool_call_id is not None:
            msg["tool_call_id"] = tool_call_id
        self.history.append(msg)
        # 成对裁剪，保留最近 max_turns 轮
        if len(self.history) > self.max_turns * 2:
            self.history = self.history[-self.max_turns * 2:]
        self.save()

    def get_messages(self):
        return list(self.history)

    def reset(self):
        self.history = []
        if os.path.exists(self.path):
            try:
                os.remove(self.path)
            except Exception:
                pass
