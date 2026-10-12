"""命令行入口：演示（离线脚本化）与真实运行两种模式。

用法：
  python -m src.cli --demo            # 离线脚本化演示（无需 API Key）
  python -m src.cli --task "..."      # 用真实 LLM 运行（需配置 .env 的 Key）
  python -m src.cli --task "..." --workdir samples --test "python test_calc.py"
"""
import argparse
import os
import sys

from .agent import CodeAgent
from .orchestrator import Orchestrator, CODER_SYSTEM_PROMPT, FIXER_SYSTEM_PROMPT
from . import tools as tools_mod
from . import llm as llm_mod
from .scripted_llm import ScriptedLLM


# ---------- 离线演示剧本 ----------
# 编码 Agent：写一个「有 Bug」的 calc.py（add 写成减法、div 未处理除零）
CODER_SCRIPT = [
    {
        "role": "assistant",
        "content": "我来实现 calc.py，包含 add 与 div 两个函数。",
        "tool_calls": [{
            "id": "c1",
            "name": "write_file",
            "arguments": {
                "path": "calc.py",
                "content": (
                    "def add(a, b):\n"
                    "    return a - b\n"
                    "\n"
                    "\n"
                    "def div(a, b):\n"
                    "    return a / b\n"
                ),
            },
        }],
    },
    {
        "role": "assistant",
        "content": "已创建 calc.py，包含 add(a,b) 与 div(a,b)。",
    },
]

# 修复 Agent：读文件 → 修正 add 的符号 → 给 div 加除零保护 → 自验
FIXER_SCRIPT = [
    {
        "role": "assistant",
        "content": "我先读取 calc.py 看当前实现。",
        "tool_calls": [{
            "id": "f1",
            "name": "read_file",
            "arguments": {"path": "calc.py"},
        }],
    },
    {
        "role": "assistant",
        "content": "发现问题：add 写成了减法；div 未处理除零。先修 add。",
        "tool_calls": [{
            "id": "f2",
            "name": "edit_file",
            "arguments": {
                "path": "calc.py",
                "old_string": "def add(a, b):\n    return a - b",
                "new_string": "def add(a, b):\n    return a + b",
            },
        }],
    },
    {
        "role": "assistant",
        "content": "再给 div 增加除零保护，按测试要求返回 float('inf')。",
        "tool_calls": [{
            "id": "f3",
            "name": "edit_file",
            "arguments": {
                "path": "calc.py",
                "old_string": "def div(a, b):\n    return a / b",
                "new_string": (
                    "def div(a, b):\n"
                    "    if b == 0:\n"
                    "        return float('inf')\n"
                    "    return a / b"
                ),
            },
        }],
    },
    {
        "role": "assistant",
        "content": "重新运行测试验证。",
        "tool_calls": [{
            "id": "f4",
            "name": "run_command",
            "arguments": {"command": "python test_calc.py"},
        }],
    },
    {
        "role": "assistant",
        "content": "测试已通过，修复完成：add 修正为加法，div 增加除零保护。",
    },
]


def _print_report(report):
    print("=" * 60)
    print("多 Agent 协作结果报告")
    print("=" * 60)
    print(f"任务：{report['task']}")
    print(f"测试命令：{report['test_command']}")
    print(f"整体状态：{'✅ 成功（测试通过）' if report['success'] else '❌ 失败（超出修复上限）'}")
    print(f"迭代轮次：{report['iterations']}")
    print("-" * 60)
    print("编码 Agent 步骤：")
    for line in report["coder_log"]:
        print("   •", line)
    for r in report["fix_rounds"]:
        print(f"\n修复 Agent 第 {r['attempt']} 轮：")
        for line in r["log"]:
            print("   •", line)
    print("\n" + "=" * 60)
    print("最终交付说明：")
    print(report["final_output"])


def run_demo():
    workdir = "samples"
    if not os.path.isdir(workdir):
        print(f"[错误] 找不到示例目录 {workdir}，请在项目根目录运行。")
        sys.exit(1)
    # 清掉上一次留下的 calc.py，保证演示可重复
    calc_path = os.path.join(workdir, "calc.py")
    if os.path.exists(calc_path):
        os.remove(calc_path)

    orch = Orchestrator(
        workdir=workdir,
        test_command="python test_calc.py",
        max_fix=3,
        coder=CodeAgent(
            llm=ScriptedLLM(CODER_SCRIPT), workdir=workdir,
            memory_path="coder_memory.json",
            tools=tools_mod.CODER_TOOLS, system_prompt=CODER_SYSTEM_PROMPT,
        ),
        fixer=CodeAgent(
            llm=ScriptedLLM(FIXER_SCRIPT), workdir=workdir,
            memory_path="fixer_memory.json",
            tools=tools_mod.FIXER_TOOLS, system_prompt=FIXER_SYSTEM_PROMPT,
        ),
    )
    task = "实现 calc.py：add(a,b) 返回 a+b；div(a,b) 返回 a/b，且 div(1,0) 返回 float('inf')，使其通过 test_calc.py。"
    report = orch.run(task)
    _print_report(report)
    sys.exit(0 if report["success"] else 1)


def run_real(task, workdir, test_command):
    orch = Orchestrator(workdir=workdir, test_command=test_command)
    report = orch.run(task)
    _print_report(report)
    sys.exit(0 if report["success"] else 1)


def main():
    parser = argparse.ArgumentParser(description="Homework 2 · 多 Agent 协作系统")
    parser.add_argument("--demo", action="store_true", help="离线脚本化演示（无需 API Key）")
    parser.add_argument("--task", default="实现 calc.py：add 与 div 函数，并通过测试。")
    parser.add_argument("--workdir", default=".")
    parser.add_argument("--test", default="python test_calc.py")
    args = parser.parse_args()

    if args.demo:
        run_demo()
    else:
        run_real(args.task, args.workdir, args.test)


if __name__ == "__main__":
    main()
