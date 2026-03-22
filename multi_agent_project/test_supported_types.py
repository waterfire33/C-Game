from orchestrator import Orchestrator


def test_supported_task_types():
    orchestrator = Orchestrator()
    result = orchestrator.get_supported_task_types()

    expected = ["math", "text", "image", "greeting", "echo"]

    if result == expected:
        print("Supported types test passed")
    else:
        print("Supported types test failed")


def test_is_supported_task_type():
    orchestrator = Orchestrator()

    if orchestrator.is_supported_task_type("echo"):
        print("Supported check test passed")
    else:
        print("Supported check test failed")


if __name__ == "__main__":
    test_supported_task_types()
    test_is_supported_task_type()