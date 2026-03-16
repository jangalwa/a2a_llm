import asyncio
import json

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


class RootAgent:
    system_prompt = (
        "You are the root assistant in a small A2A demo.\n"
        "Answer general user questions directly in plain English.\n"
        "Be concise and helpful.\n"
        "Do not claim to have used tools unless tool results were already provided."
    )
    router_prompt = (
        "You are a routing controller for a small A2A demo.\n"
        "Decide whether the user's request should be delegated to one or more remote agents.\n"
        "Return JSON only. No markdown. No explanation.\n"
        "The JSON schema is:\n"
        '{\n'
        '  "routes": [\n'
        '    {"agent": "calculator" | "calendar", "input": "text to send to that agent"}\n'
        "  ]\n"
        "}\n"
        "If no remote agent is needed, return {\"routes\": []}.\n"
        "Delegate only when the request clearly matches an advertised skill.\n"
        "For mixed questions, return multiple routes.\n"
        "For calculator routes, send only the arithmetic expression.\n"
        "For calendar routes, send the calendar-related portion of the request.\n"
        "Never invent agent names."
    )

    def __init__(self, agent_cards):
        self.llm = LLM()
        self.history = []
        self.agent_cards = agent_cards

    def route_query(self, user_input):
        agent_summaries = []
        for agent_name, card in self.agent_cards.items():
            skills = ", ".join(
                f"{skill['id']}: {skill['description']}" for skill in card.get("skills", [])
            )
            agent_summaries.append(f"- {agent_name}: {card['name']} | skills: {skills}")

        messages = [
            {"role": "system", "content": self.router_prompt},
            {
                "role": "user",
                "content": (
                    "Available agents:\n"
                    f"{chr(10).join(agent_summaries)}\n\n"
                    f"User request: {user_input}"
                ),
            },
        ]
        response = self.llm.generate_response(messages)

        try:
            parsed = json.loads(response)
        except json.JSONDecodeError:
            return []

        routes = []
        for item in parsed.get("routes", []):
            agent_name = item.get("agent")
            route_input = item.get("input", "").strip()
            if agent_name in self.agent_cards and route_input:
                routes.append((agent_name, route_input))
        return routes

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
    root_agent = RootAgent(
        {
            agent_name: entry["card"]
            for agent_name, entry in clients.items()
        }
    )
    print("\n\nDiscovered agents:")
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

        routes = root_agent.route_query(user_input)
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
