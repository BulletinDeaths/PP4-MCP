import os
import json
import logging

logger = logging.getLogger(__name__)


class Agent:
    """
    Агент-аналитик, который преобразует запросы на разработку в структурированное ТЗ.
    Для обычных вопросов и сообщений использует стандартный LLM.
    """

    def __init__(self, orchestrator):
        self.orchestrator = orchestrator
        self.prompt_path = os.path.join("workspace", "prompts", "analyst.md")

    def _is_development_request(self, message: str) -> bool:
        """Определяет, является ли сообщение запросом на разработку."""
        keywords = [
            'созда', 'разработ', 'сайт', 'программ', 'приложен', 'код',
            'сервис', 'система', 'бот', 'алгоритм'
        ]
        return any(keyword in message.lower() for keyword in keywords)

    def handle_message(self, message: str) -> str:
        """Обрабатывает входящее сообщение."""

        # --- ЭТО ЗАПРОС НА РАЗРАБОТКУ ---
        if self._is_development_request(message):
            logger.info("Запрос распознан как задача на разработку. Формирую ТЗ.")

            try:
                with open(self.prompt_path, 'r', encoding='utf-8') as f:
                    prompt_template = f.read()

                # Используем f-строку, чтобы избежать конфликта с { } из JSON
                system_prompt = f"{prompt_template}{message}"

            except FileNotFoundError as e:
                logger.error(f"Файл промпта не найден: {e}")
                return "Ошибка: не удалось найти файл с инструкциями для аналитика."

            # Вызываем LLM для генерации ТЗ
            llm_response = self.orchestrator.ask_llm(system_prompt, provider="ollama")
            if not llm_response or not llm_response.strip():
                return "Ошибка: Не удалось получить ответ от языковой модели при генерации ТЗ."

            # --- НОВАЯ ЛОГИКА ПРОВЕРКИ ОТВЕТА (ИСПРАВЛЕНИЕ) ---
            import json5  # Импортируем здесь для локального использования

            try:
                # Пробуем распарсить ответ как JSON с помощью json5 (терпит \n в коде)
                parsed_json = json5.loads(llm_response)

                # Если успешно - сохраняем ИСХОДНЫЙ текст в общую память для разработчика
                self.orchestrator.shared_memory['analyst_result_raw'] = llm_response

                # Возвращаем исходный JSON-текст (сырой), чтобы разработчик его получил как есть.
                return llm_response

            except Exception as e:
                # Логируем ошибку, но НЕ прерываем цепочку!
                logger.warning(f"Ответ от LLM не является валидным JSON. Обработка как обычного ответа. Ошибка: {e}")

                # Даже если JSON плохой, кладем то, что вернула модель, в общую память.
                # Разработчик попробует это обработать.
                self.orchestrator.shared_memory['analyst_result_raw'] = llm_response

                # Сообщаем пользователю о проблеме, но продолжаем работу конвейера
                return ("Техническое задание сгенерировано, но имеет ошибки формата.\n"
                        "Агент-разработчик попытается использовать полученный результат.")

        # --- ЭТО ОБЫЧНЫЙ ВОПРОС ---
        else:
            logger.info("Запрос не является задачей на разработку.")
            provider = self.orchestrator.shared_memory.get('llm_provider', 'ollama')
            return self.orchestrator.ask_llm(message, provider=provider) or "Я пока не знаю, что на это ответить."