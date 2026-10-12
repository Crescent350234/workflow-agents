"""多 Agent 编排器：编码 Agent（coder）+ 修复 Agent（fixer）。

这是 Homework 2 相对 Homework 1 新增的系统层。它把两个 Homework 1 风格的
CodeAgent（仅工具集与提示词不同）组织成一个「生成—验证—修复」闭环：

  1. Orchestrator 把用户任务交给 coder，coder 生成代码文件（write_file）；
  2. Orchestrator 用 test_command 运行测试，检查 returncode 判断是否通过；
  3. 通过 → 直接交付最终结果；
  4. 失败 → Orchestrator 把「测试失败输出」整理成结构化错误上下文，交给 fixer；
  5. fixer 读取被测文件、用 edit_file 做最小修改、用 run_command 自验；
  6. Orchestrator 再次运行 test_command，循环最多 max_fix 次；
  7. 超出上限仍未通过 → 返回失败报告，附最后一轮 fixer 的修改说明。

设计要点：
- coder 与 fixer 是**同一类**（CodeAgent）的两个实例，共享 workdir、各自独立记忆；
- 两 Agent 之间通过 Orchestrator 中转的「错误上下文」消息解耦，不直接互相调用；
- 测试权威判定由 Orchestrator 统一执行（确定性 subprocess），避免 Agent 自报通过。
"""
import os
import subprocess
import sys

from .agent import CodeAgent
from . import tools as tools_mod
from . import llm as llm_mod

CODER_SYSTEM_PROMPT = """你是一个「编码 Agent」，负责根据需求**生成代码**并落盘。

可用工具：
- write_file ：创建/覆盖文件并写入内容（生成代码的主要手段）
- read_file  ：读取文件（确认上下文）
- list_directory ：列出目录
- run_command ：运行命令（如 python 语法自检 `python -c "import x"`）
- search_web ：检索资料

工作准则：
1. 先理解需求，再用 write_file 把完整、可运行的代码写入对应文件；
2. 代码要满足用户描述的功能，并能被项目里的测试套件验证；
3. 一次写清整个文件，不要留 TODO/占位；
4. 用中文简要说明你创建了哪些文件、实现了什么。
"""

FIXER_SYSTEM_PROMPT = """你是一个「修复 Agent」，负责修复**未通过测试**的代码。

可用工具：
- read_file  ：读取被测文件，定位问题
- edit_file  ：对被测文件做最小、精准的局部修改（替换 old_string → new_string）
- run_command：重新运行测试，验证修改是否生效
- list_directory / search_web ：辅助定位

工作准则：
1. 先 read_file 看清失败文件与相关代码；
2. 对照测试报错，找出根因，用 edit_file 做**最小修改**，不要重写整个文件；
3. 用 run_command 重新运行测试验证；
4. 若一次未过，继续分析下一处问题，直到测试通过或用尽机会；
5. 用中文说明你改了什么、为什么。
"""


class Orchestrator:
    def __init__(self, workdir=".", test_command="pytest", max_fix=3,
                 coder=None, fixer=None, llm=None):
        self.workdir = workdir
        self.test_command = test_command
        self.max_fix = max_fix
        self.llm = llm or llm_mod.LLMClient()

        # 复用同一个 CodeAgent 类，仅工具集与提示词不同
        self.coder = coder or CodeAgent(
            llm=self.llm, workdir=workdir, memory_path="coder_memory.json",
            tools=tools_mod.CODER_TOOLS, system_prompt=CODER_SYSTEM_PROMPT,
        )
        self.fixer = fixer or CodeAgent(
            llm=self.llm, workdir=workdir, memory_path="fixer_memory.json",
            tools=tools_mod.FIXER_TOOLS, system_prompt=FIXER_SYSTEM_PROMPT,
        )

    def _resolve_test_cmd(self):
        """把命令里的 `python` 替换为当前解释器，确保子进程能找到 python。"""
        cmd = self.test_command
        stripped = cmd.strip()
        if stripped == "python":
            return sys.executable
        if stripped.startswith("python "):
            return sys.executable + cmd[len("python"):]
        return cmd

    def _run_tests(self):
        """运行测试命令，返回 (是否通过, 输出文本)。"""
        cmd = self._resolve_test_cmd()
        try:
            res = subprocess.run(cmd, shell=True, cwd=self.workdir,
                                 capture_output=True, text=True, timeout=120)
            out = (res.stdout or "") + (res.stderr or "")
            return res.returncode == 0, out
        except subprocess.TimeoutExpired:
            return False, "[错误] 测试执行超时（>120s）"
        except Exception as e:
            return False, f"[错误] 测试执行异常: {e}"

    def _build_fix_prompt(self, task, attempt, test_output):
        return (
            f"[修复任务 #{attempt}]\n"
            f"原始需求：{task}\n\n"
            f"测试命令 `{self.test_command}` 运行后**失败**，输出如下：\n\n"
            f"{test_output}\n\n"
            f"请：1) 定位失败根因（结合测试报错与被测文件）；"
            f"2) 使用 edit_file 做最小、精准的修改；"
            f"3) 用 run_command 重新运行测试验证。"
            f"只改必要的代码，不要整文件重写。"
        )

    def run(self, task):
        """执行一次「生成—验证—修复」流程，返回结果报告字典。"""
        report = {
            "task": task,
            "test_command": self.test_command,
            "coder_log": [],
            "fix_rounds": [],
            "success": False,
            "final_output": "",
            "iterations": 0,
        }

        # 1) 编码 Agent 生成代码
        coder_answer, coder_log = self.coder.run(task)
        report["coder_log"] = coder_log
        report["iterations"] += 1

        # 2) 运行测试
        passed, out = self._run_tests()
        if passed:
            report["success"] = True
            report["final_output"] = coder_answer
            return report

        # 3) 修复循环
        attempt = 1
        last_fixer_answer = coder_answer
        while attempt <= self.max_fix and not passed:
            prompt = self._build_fix_prompt(task, attempt, out)
            fixer_answer, fixer_log = self.fixer.run(prompt)
            last_fixer_answer = fixer_answer
            report["fix_rounds"].append({
                "attempt": attempt,
                "log": fixer_log,
                "answer": fixer_answer,
                "test_output_before_fix": out,
            })
            report["iterations"] += 1
            passed, out = self._run_tests()
            attempt += 1

        report["success"] = passed
        report["final_output"] = last_fixer_answer
        return report
