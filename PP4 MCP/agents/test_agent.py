class Agent:
    """
    Базовый класс для ИИ-агентов. Принимает сообщения от оркестратора и возвращает ответ.
    """

    def __init__(self, orchestrator):
        self.orchestrator = orchestrator

    def handle_message(self, message: str) -> str:
        """
        Обрабатывает входящее сообщение.
        """
        known_facts = self.orchestrator.shared_memory.get('facts', [])

        if "привет" in message.lower():
            return "Привет! Я тестовый агент-заглушка. Я просто повторяю то, что ты мне говоришь."
        elif "факты" in message.lower():
            if known_facts:
                return "Я знаю несколько фактов: " + ", ".join(known_facts)
            else:
                return "У меня пока нет фактов в памяти."
        else:
            try:
                ollama_response = self.orchestrator.call_ollama_api(message)
                if ollama_response is None:
                    raise Exception("Ollama не ответил")
                return ollama_response
            except Exception:
                return f"[Echo] Вы сказали: '{message}'"