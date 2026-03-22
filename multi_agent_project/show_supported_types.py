from orchestrator import Orchestrator


def show_supported_types():
    orchestrator = Orchestrator()
    supported_types = orchestrator.get_supported_task_types()

    for task_type in supported_types:
        print(f"- {task_type}")


if __name__ == "__main__":
    show_supported_types()