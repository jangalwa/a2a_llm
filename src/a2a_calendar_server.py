import re
from datetime import datetime, timedelta

import uvicorn
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.apps import A2AStarletteApplication
from a2a.server.events import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentSkill
from a2a.utils.message import new_agent_text_message
from llm import LLM


class Calendar:
    system_prompt = (
        "You resolve calendar questions into a machine-readable action.\n"
        "The user will ask about a date, day, or time.\n"
        "Use the provided local reference timestamp as ground truth.\n"
        "Respond with exactly one of:\n"
        "1. TIME\n"
        "2. DATE:YYYY-MM-DD\n"
        "3. UNSUPPORTED\n"
        "Do not add any extra words.\n"
        "Examples:\n"
        "- what date is today? -> DATE:2026-03-15\n"
        "- what time is it? -> TIME\n"
        "- what date is tomorrow? -> DATE:2026-03-16"
    )

    def __init__(self):
        self.llm = LLM()

    def _format_date(self, value):
        return value.strftime("%A, %B %d, %Y")

    def _format_time(self, value):
        return value.strftime("%I:%M:%S %p %Z").lstrip("0")

    def _fallback_resolution(self, query, now):
        lowered = query.lower()

        if "time" in lowered or "clock" in lowered:
            return "time", now

        if "tomorrow" in lowered:
            return "date", now + timedelta(days=1)

        if "yesterday" in lowered:
            return "date", now - timedelta(days=1)

        if any(token in lowered for token in ["today", "date", "day"]):
            return "date", now

        return None, None

    def resolve_datetime(self, query):
        now = datetime.now().astimezone()
        fallback_type, fallback_value = self._fallback_resolution(query, now)
        messages = [
            {"role": "system", "content": self.system_prompt},
            {
                "role": "user",
                "content": (
                    f"Local reference timestamp: {now.isoformat()}\n"
                    f"Question: {query}"
                ),
            },
        ]
        decision = self.llm.generate_response(messages).strip().upper()

        if decision == "TIME" or decision.startswith("TIME"):
            return "time", now

        match = re.search(r"DATE:(\d{4}-\d{2}-\d{2})", decision)
        if match:
            value = datetime.strptime(match.group(1), "%Y-%m-%d").replace(
                tzinfo=now.tzinfo,
                hour=now.hour,
                minute=now.minute,
                second=now.second,
                microsecond=now.microsecond,
            )
            return "date", value

        return fallback_type, fallback_value

    def run(self, query):
        result_type, value = self.resolve_datetime(query)

        if result_type == "time":
            return result_type, self._format_time(value)

        if result_type == "date":
            return result_type, self._format_date(value)

        return None, "Calendar error"


class CalendarAgentExecutor(AgentExecutor):
    def __init__(self):
        self.calendar = Calendar()

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        result_type, result = self.calendar.run(context.get_user_input())

        if result_type == "time":
            text = f"The current time is {result}"
        elif result_type == "date":
            text = f"The date is {result}"
        else:
            text = "I can help with dates, days, and time."

        await event_queue.enqueue_event(new_agent_text_message(text))

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise NotImplementedError("cancel not supported")


def build_agent_card():
    date_skill = AgentSkill(
        id="current_date",
        name="Date Lookup",
        description="Returns a date for queries like today, tomorrow, next Friday, or 10 days from now.",
        tags=["calendar", "date", "day"],
        examples=[
            "What's today's date?",
            "What day is next Friday?",
            "What is the date 10 days from now?",
        ],
    )
    time_skill = AgentSkill(
        id="current_time",
        name="Current Time",
        description="Returns the current local time.",
        tags=["calendar", "time", "clock"],
        examples=["What time is it?", "Current time please"],
    )
    return AgentCard(
        name="Calendar Agent",
        description="An A2A agent that returns dates or times using LLM-backed calendar understanding.",
        url="http://127.0.0.1:8002/",
        version="0.1.0",
        default_input_modes=["text"],
        default_output_modes=["text"],
        capabilities=AgentCapabilities(streaming=False),
        skills=[date_skill, time_skill],
    )


def build_app():
    request_handler = DefaultRequestHandler(
        agent_executor=CalendarAgentExecutor(),
        task_store=InMemoryTaskStore(),
    )
    server = A2AStarletteApplication(
        agent_card=build_agent_card(),
        http_handler=request_handler,
    )
    return server.build()


def main():
    uvicorn.run(build_app(), host="127.0.0.1", port=8002)


if __name__ == "__main__":
    main()
