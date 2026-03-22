from orchestrator import Orchestrator


def test_math_error():
    orchestrator = Orchestrator()
    result = orchestrator.run_task("math", "add three five")

    if result == "MathAgent error: please use numbers like 'add 3 5'":
        print("Math error test passed")
    else:
        print("Math error test failed")


if __name__ == "__main__":
    test_math_error()