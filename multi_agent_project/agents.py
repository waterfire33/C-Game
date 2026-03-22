class MathAgent:
    def run(self, task):
        if task == "add two numbers":
            return "MathAgent result: 2 + 2 = 4"

        parts = task.split()

        if len(parts) == 3 and parts[0] == "add":
            try:
                number_1 = int(parts[1])
                number_2 = int(parts[2])
                total = number_1 + number_2
                return f"MathAgent result: {number_1} + {number_2} = {total}"
            except ValueError:
                return "MathAgent error: please use numbers like 'add 3 5'"

        return f"MathAgent handled: {task}"

        parts = task.split()

        if len(parts) == 3 and parts[0] == "add":
            number_1 = int(parts[1])
            number_2 = int(parts[2])
            total = number_1 + number_2
            return f"MathAgent result: {number_1} + {number_2} = {total}"

        return f"MathAgent handled: {task}"


class TextAgent:
    def run(self, task):
        if task == "write a sentence":
            return "TextAgent result: This is a sentence."
        return f"TextAgent handled: {task}"


class ImageAgent:
    def run(self, task):
        if task == "create a picture":
            return "ImageAgent result: Picture created."
        return f"ImageAgent handled: {task}"


class GreetingAgent:
    def run(self, task):
        if task == "say hello":
            return "GreetingAgent result: Hello."
        return f"GreetingAgent handled: {task}"
    

class EchoAgent:
    def run(self, task):
        return f"EchoAgent result: {task}"