from orchestrator import Orchestrator
from tasks import tasks
import test_task
import test_unknown_task
import test_utils
import test_supported_types
import test_math_error
import test_task_data


def run_demo_tasks():
    orchestrator = Orchestrator()

    for item in tasks:
        result = orchestrator.run_task_data(item)
        print(result)


def run_all():
    print("Running demo tasks")
    run_demo_tasks()

    print("Running tests")
    test_task.run_tests()

    print("Running unknown task test")
    test_unknown_task.test_unknown_task()

    print("Running utils test")
    test_utils.test_format_task_type()

    print("Running supported types test")
    test_supported_types.test_supported_task_types()

    print("Running supported check test")
    test_supported_types.test_is_supported_task_type()

    print("Running math error test")
    test_math_error.test_math_error()

    print("Running task data test")
    test_task_data.test_run_task_data()


if __name__ == "__main__":
    run_all()