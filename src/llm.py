class LLM:
    def __init__(self):
        from mlx_lm import generate, load
        from mlx_lm.sample_utils import make_sampler

        self._generate = generate
        self.model, self.tokenizer = load("mlx-community/Qwen2.5-1.5B-Instruct-4bit")

        # Greedy sampler -> deterministic output
        self.sampler = make_sampler(temp=0)

    def generate_response(self, messages):
        prompt = self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )

        response = self._generate(
            self.model,
            self.tokenizer,
            prompt=prompt,
            max_tokens=80,
            sampler=self.sampler,
        )

        return response.strip()
