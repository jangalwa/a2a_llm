import re

from a2a_common import fetch_agent_card, send_message
from llm import LLM


CALCULATOR_URL = "http://127.0.0.1:8001"
CALENDAR_URL = "http://127.0.0.1:8002"


def discover_agents():
    calculator_card = fetch_agent_card(CALCULATOR_URL)
    calendar_card = fetch_agent_card(CALENDAR_URL)
    return {
        "calculator": calculator_card,
        "calendar": calendar_card,
    }


def is_math_query(text):
    return bool(re.search(r"\d\s*[-+/*()]\s*\d", text))


def is_calendar_query(text):
    lowered = text.lower()
    return any(
        token in lowered
        for token in [
            "date",
            "day",
            "time",
            "clock",
            "today",
            "tomorrow",
            "yesterday",
            "monday",
            "tuesday",
            "wednesday",
            "thursday",
            "friday",
            "saturday",
            "sunday",
            "next ",
            "last ",
            "this ",
            "from now",
            "ago",
        ]
    )


def route_query(text):
    routes = []

    if is_calendar_query(text):
        routes.append(("calendar", text))

    if is_math_query(text):
        match = re.search(r"([0-9][0-9\s+\-*/().]*)", text)
        if match:
            routes.append(("calculator", match.group(1).strip()))

    return routes


class RootAgent:
    system_prompt = (
        "You are the root assistant in a small A2A demo.\n"
        "Answer general user questions directly in plain English.\n"
        "Be concise and helpful.\n"
        "Do not claim to have used tools unless tool results were already provided."
    )

    def __init__(self):
        self.llm = LLM()
        self.history = []

    def answer_directly(self, user_input):
        messages = [
            {"role": "system", "content": self.system_prompt},
            *self.history,
            {"role": "user", "content": user_input},
        ]
        response = self.llm.generate_response(messages)
        self.history.append({"role": "user", "content": user_input})
        self.history.append({"role": "assistant", "content": response})
        return response


def run_demo():
    cards = discover_agents()
    root_agent = RootAgent()
    print("Discovered agents:")
    for card in cards.values():
        print(f"- {card['name']}: {card['url']}")
        for skill in card.get("skills", []):
            print(f"  skill={skill['id']} tags={','.join(skill.get('tags', []))}")
    print()

    print("A2A root demo started")
    print("Commands: exit\n")

    while True:
        user_input = input("You: ").strip()
        if user_input.lower() == "exit":
            print("Demo exiting.")
            break

        routes = route_query(user_input)
        if not routes:
            answer = root_agent.answer_directly(user_input)
            print(f"Root: {answer}\n")
            continue

        responses = []
        for agent_name, agent_input in routes:
            card = cards[agent_name]
            print(f"Root: delegating to {card['name']} -> {agent_input}")
            response = send_message(card["url"], agent_input)
            responses.append(response)

        print(f"Root: {' '.join(responses)}\n")


if __name__ == "__main__":
    run_demo()
