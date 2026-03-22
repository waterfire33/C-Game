from orchestrator import Orchestrator


def test_unknown_task():
    orchestrator = Orchestrator()
    result = orchestrator.run_task("video", "edit a video")

    if result == "No agent found for task type: video":
        print("Unknown task test passed")
    else:
        print("Unknown task test failed")


if __name__ == "__main__":
    test_unknown_task()