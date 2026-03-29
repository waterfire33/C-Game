from orchestrator import Orchestrator


def test_unsupported_task():
    orchestrator = Orchestrator()
    result = orchestrator.run_task("video", "edit a video")

    if result == "No agent found for task type: video":
        print("Unsupported task test passed")
    else:
        print("Unsupported task test failed")


if __name__ == "__main__":
    test_unsupported_task()