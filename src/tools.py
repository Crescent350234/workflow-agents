"""Agent 可调用的工具集合。

Homework 1 已有 5 个工具：read_file / list_directory / run_command / search_web /
generate_unit_test。Homework 2 在此之上新增两个「写」类工具，分别服务于不同角色：

- write_file：编码 Agent（coder）用它**创建/覆盖**新文件（生成代码的落盘手段）；
- edit_file ：修复 Agent（fixer）用它对被测文件做**精准的局部字符串替换**（最小修改）。

所有写操作均做「工作目录越权校验」，禁止 Agent 写到项目目录之外。
"""
import os
import subprocess

# ---------- Homework 1 原有 5 个工具的描述 ----------
TOOLS_SPEC = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "读取指定路径的源代码或文本文件内容，用于代码审查、解释与重构分析。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "文件相对或绝对路径"}
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_directory",
            "description": "列出目录下的文件与子目录，帮助定位代码文件。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "目录路径，默认当前目录"}
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": "在项目目录内执行一条 shell 命令（如运行测试、代码格式化）。出于安全限制，仅允许白名单命令并禁止危险操作。",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "要执行的命令字符串"}
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": "检索公开技术资料或官方文档（演示模式下返回内置示例链接）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "检索关键词"}
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_unit_test",
            "description": "为一个给定的源代码文件生成单元测试骨架（演示模式返回模板）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "目标源代码文件路径"}
                },
                "required": ["path"],
            },
        },
    },
]

# ---------- Homework 2 新增：write_file（编码 Agent 专用） ----------
WRITE_FILE_SPEC = {
    "type": "function",
    "function": {
        "name": "write_file",
        "description": "在项目目录内创建或覆盖一个文件，并写入给定内容。用于把生成的代码落盘。"
                       "只能写在工作目录之内，禁止写到项目之外。",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "目标文件相对路径，如 calc.py 或 src/utils.py"},
                "content": {"type": "string", "description": "要写入的完整文件内容"},
            },
            "required": ["path", "content"],
        },
    },
}

# ---------- Homework 2 新增：edit_file（修复 Agent 专用） ----------
EDIT_FILE_SPEC = {
    "type": "function",
    "function": {
        "name": "edit_file",
        "description": "对被测文件做最小、精准的局部修改：把 old_string 首次出现处替换为 "
                       "new_string。仅当 old_string 精确匹配文件内容时才生效，避免误改。"
                       "只能编辑工作目录之内的文件。",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "目标文件相对路径"},
                "old_string": {"type": "string", "description": "待替换的原始文本片段（需精确匹配）"},
                "new_string": {"type": "string", "description": "替换后的新文本片段"},
            },
            "required": ["path", "old_string", "new_string"],
        },
    },
}

# 角色工具集：编码 Agent 在 5 个工具基础上增加 write_file；
# 修复 Agent 不需要生成新文件，保留读/列/运行/检索 + edit_file。
CODER_TOOLS = TOOLS_SPEC + [WRITE_FILE_SPEC]
FIXER_TOOLS = [t for t in TOOLS_SPEC if t["function"]["name"] != "generate_unit_test"]
FIXER_TOOLS = FIXER_TOOLS + [EDIT_FILE_SPEC]

# 命令白名单：仅允许这些命令开头，避免任意代码执行风险
_ALLOWED_CMD = ("python", "python3", "pytest", "pip", "ls", "dir", "cat",
                "echo", "node", "npm", "git")


def _safe_join(workdir, path):
    """将相对路径安全拼接进 workdir，返回绝对路径；越权返回 None。"""
    base = os.path.abspath(workdir)
    target = os.path.abspath(os.path.join(base, path))
    if target != base and not target.startswith(base + os.sep):
        return None
    return target


def run_tool(name, arguments, workdir="."):
    """执行指定工具，返回字符串结果。所有异常被捕获并返回错误信息。"""
    try:
        if name == "read_file":
            p = _safe_join(workdir, arguments.get("path", ""))
            if p is None:
                return "[错误] 越权路径"
            if not os.path.isfile(p):
                return f"[错误] 文件不存在: {p}"
            with open(p, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            if len(content) > 8000:  # 防止上下文过长
                content = content[:8000] + "\n... (内容过长已截断) ..."
            return content

        elif name == "list_directory":
            d = arguments.get("path") or workdir
            d = _safe_join(workdir, d)
            if d is None:
                return "[错误] 越权路径"
            if not os.path.isdir(d):
                return f"[错误] 目录不存在: {d}"
            items = sorted(os.listdir(d))
            return "\n".join(items)

        elif name == "run_command":
            cmd = arguments.get("command", "")
            if not cmd.strip():
                return "[错误] 命令为空"
            head = cmd.strip().split()[0].lower()
            if head not in _ALLOWED_CMD:
                return (f"[拒绝] 出于安全考虑，不允许执行命令: {head}；"
                        f"允许前缀: {', '.join(_ALLOWED_CMD)}")
            try:
                res = subprocess.run(cmd, shell=True, cwd=workdir,
                                     capture_output=True, text=True, timeout=30)
                out = (res.stdout or "") + (res.stderr or "")
                return out[:4000] if out else "[命令执行完成，无输出]"
            except subprocess.TimeoutExpired:
                return "[错误] 命令执行超时（>30s）"

        elif name == "search_web":
            q = arguments.get("query", "")
            return (f"[演示检索结果] 关于「{q}」的参考资料：\n"
                    "- https://docs.python.org/3/  (Python 官方文档)\n"
                    "- https://peps.python.org/  (Python 增强提案)\n"
                    "- https://stackoverflow.com/  (技术问答社区)\n"
                    "（配置真实 LLM 与检索 API 后可返回实时结果）")

        elif name == "generate_unit_test":
            p = arguments.get("path", "")
            base = os.path.basename(p)
            mod = os.path.splitext(base)[0] or "module"
            return (
                f"# 为 {base} 生成的单元测试骨架（演示）\n"
                f"import unittest\n"
                f"# from {mod} import *\n\n"
                f"class Test{mod.capitalize()}(unittest.TestCase):\n"
                f"    def test_example(self):\n"
                f"        # TODO: 补充针对 {mod} 的真实断言\n"
                f"        self.assertTrue(True)\n\n"
                f"if __name__ == '__main__':\n"
                f"    unittest.main()\n"
            )

        elif name == "write_file":
            path = arguments.get("path", "")
            content = arguments.get("content", "")
            if not path:
                return "[错误] 未提供 path"
            p = _safe_join(workdir, path)
            if p is None:
                return f"[错误] 越权路径，禁止写到工作目录之外: {path}"
            parent = os.path.dirname(p)
            if parent and not os.path.isdir(parent):
                os.makedirs(parent, exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                f.write(content)
            return f"[成功] 已写入 {path}（{len(content)} 字符）"

        elif name == "edit_file":
            path = arguments.get("path", "")
            old_string = arguments.get("old_string", "")
            new_string = arguments.get("new_string", "")
            if not path:
                return "[错误] 未提供 path"
            if not old_string:
                return "[错误] old_string 为空，无法定位待替换文本"
            p = _safe_join(workdir, path)
            if p is None:
                return f"[错误] 越权路径，禁止编辑工作目录之外: {path}"
            if not os.path.isfile(p):
                return f"[错误] 文件不存在: {p}"
            with open(p, "r", encoding="utf-8") as f:
                cur = f.read()
            if old_string not in cur:
                return "[错误] 未在原文件中找到 old_string（请保证精确匹配，含缩进）"
            new = cur.replace(old_string, new_string, 1)
            with open(p, "w", encoding="utf-8") as f:
                f.write(new)
            return f"[成功] 已修改 {path}（替换 1 处）"

        else:
            return f"[错误] 未知工具: {name}"
    except Exception as e:
        return f"[工具执行异常] {e}"
