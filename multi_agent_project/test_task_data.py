from orchestrator import Orchestrator


def test_run_supported_task_data():
    orchestrator = Orchestrator()
    task_data = {"type": "math", "task": "add 8 4"}
    result = orchestrator.run_task_data(task_data)

    if result == "MathAgent result: 8 + 4 = 12":
        print("Supported task data test passed")
    else:
        print("Supported task data test failed")

def test_run_unsupported_task_data():
    orchestrator = Orchestrator()
    task_data = {"type": "video", "task": "edit a video"}
    result = orchestrator.run_task_data(task_data)

    if result == "No agent found for task type: video":
        print("Unsupported task data test passed")
    else:
        print("Unsupported task data test failed")  


if __name__ == "__main__":
    test_run_supported_task_data()
    test_run_unsupported_task_data()