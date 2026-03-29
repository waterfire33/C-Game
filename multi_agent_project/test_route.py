from orchestrator import Orchestrator


def test_supported_route():
    orchestrator = Orchestrator()
    agent = orchestrator.route("math")

    if agent is not None:
        print("Supported route test passed")
    else:
        print("Supported route test failed")


def test_unsupported_route():
    orchestrator = Orchestrator()
    agent = orchestrator.route("video")

    if agent is None:
        print("Unsupported route test passed")
    else:
        print("Unsupported route test failed")


if __name__ == "__main__":
    test_supported_route()
    test_unsupported_route()