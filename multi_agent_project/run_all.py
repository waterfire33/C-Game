from orchestrator import Orchestrator
from tasks import tasks
import test_task
import test_unsupported_task
import test_utils
import test_supported_types
import test_math_error
import test_task_data
import test_route


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

    print("Running unsupported task test")
    test_unsupported_task.test_unsupported_task()

    print("Running utils test")
    test_utils.test_format_task_type()

    print("Running supported types test")
    test_supported_types.test_supported_task_types()

    print("Running supported check test")
    test_supported_types.test_supported_task_type_check()

    print("Running unsupported check test")
    test_supported_types.test_unsupported_task_type_check()

    print("Running supported count test")
    test_supported_types.test_count_supported_task_types()

    print("Running math error test")
    test_math_error.test_math_error()

    print("Running supported task data test")
    test_task_data.test_run_supported_task_data()

    print("Running unsupported task data test")
    test_task_data.test_run_unsupported_task_data()

    print("Running supported route test")
    test_route.test_supported_route()

    print("Running unsupported route test")
    test_route.test_unsupported_route()


if __name__ == "__main__":
    run_all()