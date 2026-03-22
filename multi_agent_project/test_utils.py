from utils import format_task_type


def test_format_task_type():
    result = format_task_type(" TEXT ")

    if result == "text":
        print("Utils test passed")
    else:
        print("Utils test failed")


if __name__ == "__main__":
    test_format_task_type()