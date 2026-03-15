from a2a_common import run_a2a_server


class Calculator:
    def run(self, expression):
        try:
            return str(eval(expression))
        except Exception:
            return "Calculation error"

calculator = None


def get_calculator():
    global calculator
    if calculator is None:
        calculator = Calculator()
    return calculator


def handle_message(text):
    expression = text.strip()
    return f"The answer is {get_calculator().run(expression)}"


AGENT_CARD = {
    "name": "Calculator Agent",
    "description": "An A2A agent that evaluates basic arithmetic expressions.",
    "protocolVersion": "0.3.0",
    "version": "0.1.0",
    "url": "http://127.0.0.1:8001",
    "capabilities": {
        "streaming": False,
        "pushNotifications": False,
    },
    "defaultInputModes": ["text"],
    "defaultOutputModes": ["text"],
    "skills": [
        {
            "id": "basic_math",
            "name": "Basic Math",
            "description": "Evaluates arithmetic expressions such as 12*4 or 7+3.",
            "tags": ["math", "calculator", "arithmetic"],
            "examples": ["23*19", "(12+8)/5", "144-27"],
        }
    ],
}


def main():
    run_a2a_server("127.0.0.1", 8001, AGENT_CARD, handle_message)


if __name__ == "__main__":
    main()
