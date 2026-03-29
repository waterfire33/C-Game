from orchestrator import Orchestrator


def test_supported_task_types():
    orchestrator = Orchestrator()
    result = orchestrator.get_supported_task_types()

    expected = ["math", "text", "image", "greeting", "echo"]

    if result == expected:
        print("Supported types test passed")
    else:
        print("Supported types test failed")


def test_supported_task_type_check():
    orchestrator = Orchestrator()

    if orchestrator.is_supported_task_type("echo"):
        print("Supported check test passed")
    else:
        print("Supported check test failed")

def test_unsupported_task_type_check():
    orchestrator = Orchestrator()

    if not orchestrator.is_supported_task_type("video"):
        print("Unsupported check test passed")
    else:
        print("Unsupported check test failed")

def test_count_supported_task_types():
    orchestrator = Orchestrator()

    if orchestrator.count_supported_task_types() == 5:
        print("Supported count test passed")
    else:
        print("Supported count test failed")


if __name__ == "__main__":
    test_supported_task_types()
    test_supported_task_type_check()
    test_unsupported_task_type_check()
    test_count_supported_task_types()