from orchestrator import Orchestrator


def test_math_task():
    orchestrator = Orchestrator()
    result = orchestrator.run_task("math", "add 3 5")

    if result == "MathAgent result: 3 + 5 = 8":
        print("Math test passed")
    else:
        print("Math test failed")

def test_math_words_task():
    orchestrator = Orchestrator()
    result = orchestrator.run_task("math", "add two numbers")

    if result == "MathAgent result: 2 + 2 = 4":
        print("Math words test passed")
    else:
        print("Math words test failed")



def test_text_task():
    orchestrator = Orchestrator()
    result = orchestrator.run_task("text", "write a sentence")

    if result == "TextAgent result: This is a sentence.":
        print("Text test passed")
    else:
        print("Text test failed")


def test_image_task():
    orchestrator = Orchestrator()
    result = orchestrator.run_task("image", "create a picture")

    if result == "ImageAgent result: Picture created.":
        print("Image test passed")
    else:
        print("Image test failed")


def test_greeting_task():
    orchestrator = Orchestrator()
    result = orchestrator.run_task("greeting", "say hello")

    if result == "GreetingAgent result: Hello.":
        print("Greeting test passed")
    else:
        print("Greeting test failed")


def test_echo_task():
    orchestrator = Orchestrator()
    result = orchestrator.run_task("echo", "repeat this text")

    if result == "EchoAgent result: repeat this text":
        print("Echo test passed")
    else:
        print("Echo test failed")


def run_tests():
    test_math_task()
    test_math_words_task()
    test_text_task()
    test_image_task()
    test_greeting_task()
    test_echo_task()


if __name__ == "__main__":
    run_tests()