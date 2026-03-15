import asyncio
import re

from a2a.client import ClientConfig, ClientFactory, create_text_message_object
from a2a.types import Message
from a2a.utils.message import get_message_text
from llm import LLM


CALCULATOR_URL = "http://127.0.0.1:8001"
CALENDAR_URL = "http://127.0.0.1:8002"


async def discover_agents():
    calculator_client = await ClientFactory.connect(
        CALCULATOR_URL,
        client_config=ClientConfig(streaming=False),
    )
    calendar_client = await ClientFactory.connect(
        CALENDAR_URL,
        client_config=ClientConfig(streaming=False),
    )
    return {
        "calculator": {
            "client": calculator_client,
            "card": to_mapping(await calculator_client.get_card()),
        },
        "calendar": {
            "client": calendar_client,
            "card": to_mapping(await calendar_client.get_card()),
        },
    }


def to_mapping(value):
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json", exclude_none=True)
    return value


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


async def send_remote_message(client, text):
    last_item = None

    async for item in client.send_message(create_text_message_object(content=text)):
        last_item = item

    if isinstance(last_item, Message):
        return get_message_text(last_item)

    if last_item is None:
        raise RuntimeError("No response returned from remote agent")

    return str(last_item)


async def run_demo():
    clients = await discover_agents()
    root_agent = RootAgent()
    print("Discovered agents:")
    for entry in clients.values():
        card = entry["card"]
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
            client = clients[agent_name]["client"]
            card = clients[agent_name]["card"]
            print(f"Root: delegating to {card['name']} -> {agent_input}")
            response = await send_remote_message(client, agent_input)
            responses.append(response)

        print(f"Root: {' '.join(responses)}\n")

    for entry in clients.values():
        client = entry["client"]
        close = getattr(client, "close", None)
        if close is not None:
            await close()


def main():
    asyncio.run(run_demo())


if __name__ == "__main__":
    main()
