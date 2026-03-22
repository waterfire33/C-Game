from orchestrator import Orchestrator


def test_run_task_data():
    orchestrator = Orchestrator()
    task_data = {"type": "math", "task": "add 8 4"}
    result = orchestrator.run_task_data(task_data)

    if result == "MathAgent result: 8 + 4 = 12":
        print("Task data test passed")
    else:
        print("Task data test failed")


if __name__ == "__main__":
    test_run_task_data()