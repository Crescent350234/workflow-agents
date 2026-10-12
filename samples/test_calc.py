"""calc.py 的单元测试（零依赖，直接用 `python test_calc.py` 运行）。

通过则退出码 0，失败则退出码 1 —— Orchestrator 正是根据退出码判定测试是否通过。

测试覆盖：
- add(a, b) 应为 a + b
- div(a, b) 应为 a / b，且 div(1, 0) 返回 float('inf')（除零保护）
"""
import sys

from calc import add, div


def test_add():
    assert add(2, 3) == 5, "add(2, 3) 应等于 5"
    assert add(-1, 1) == 0, "add(-1, 1) 应等于 0"


def test_div():
    assert div(10, 2) == 5, "div(10, 2) 应等于 5"
    assert div(1, 0) == float("inf"), "div(1, 0) 应返回 float('inf')"


def main():
    tests = [test_add, test_div]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS  {t.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL  {t.__name__}: {e}")
        except Exception as e:  # 含 ZeroDivisionError 等
            failed += 1
            print(f"ERROR {t.__name__}: {type(e).__name__}: {e}")
    total = len(tests)
    if failed:
        print(f"\n结果：{total - failed}/{total} 通过，{failed} 失败")
        sys.exit(1)
    print(f"\n结果：{total}/{total} 全部通过")
    sys.exit(0)


if __name__ == "__main__":
    main()
