import logging

import uvicorn
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.apps import A2AStarletteApplication
from a2a.server.events import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentSkill
from a2a.utils.message import new_agent_text_message


logger = logging.getLogger("a2a.calculator")


class Calculator:
    def run(self, expression):
        logger.info("Evaluating expression: %s", expression)
        try:
            result = str(eval(expression))
            logger.info("Evaluation result: %s", result)
            return result
        except Exception:
            logger.exception("Evaluation failed for expression: %s", expression)
            return "Calculation error"

class CalculatorAgentExecutor(AgentExecutor):
    def __init__(self):
        self.calculator = Calculator()

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        expression = context.get_user_input().strip()
        logger.info("Received calculator request: %s", expression)
        result = self.calculator.run(expression)
        response_text = f"The answer is {result}"
        logger.info("Sending calculator response: %s", response_text)
        await event_queue.enqueue_event(new_agent_text_message(response_text))

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise NotImplementedError("cancel not supported")


def build_agent_card():
    skill = AgentSkill(
        id="basic_math",
        name="Basic Math",
        description="Evaluates arithmetic expressions such as 12*4 or 7+3.",
        tags=["math", "calculator", "arithmetic"],
        examples=["23*19", "(12+8)/5", "144-27"],
    )
    return AgentCard(
        name="Calculator Agent",
        description="An A2A agent that evaluates basic arithmetic expressions.",
        url="http://127.0.0.1:8001/",
        version="0.1.0",
        default_input_modes=["text"],
        default_output_modes=["text"],
        capabilities=AgentCapabilities(streaming=False),
        skills=[skill],
    )


def build_app():
    request_handler = DefaultRequestHandler(
        agent_executor=CalculatorAgentExecutor(),
        task_store=InMemoryTaskStore(),
    )
    server = A2AStarletteApplication(
        agent_card=build_agent_card(),
        http_handler=request_handler,
    )
    return server.build()


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    logger.info("Starting Calculator Agent on http://127.0.0.1:8001/")
    uvicorn.run(build_app(), host="127.0.0.1", port=8001)


if __name__ == "__main__":
    main()
