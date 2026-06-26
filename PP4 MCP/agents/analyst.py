import os
import json
import logging

logger = logging.getLogger(__name__)


class Agent:
    """Агент-аналитик, который преобразует запросы на разработку в структурированное ТЗ."""
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
                system_prompt = f"{prompt_template}{message}"
            except FileNotFoundError as e:
                logger.error(f"Файл промпта не найден: {e}")
                return "Ошибка: не удалось найти файл с инструкциями для аналитика."

            llm_response = self.orchestrator.ask_llm(system_prompt)
            if not llm_response or not llm_response.strip():
                return "Ошибка: Не удалось получить ответ от языковой модели при генерации ТЗ."

            import json5

            # --- ОЧИСТКА ОТ MARKDOWN ---
            cleaned_response = llm_response
            if "```json" in llm_response and "```" in llm_response:
                start_mark = llm_response.find("```json") + len("```json")
                end_mark = llm_response.rfind("```")
                cleaned_response = llm_response[start_mark:end_mark]

            # --- СТРОГАЯ ЛОГИКА: ПАРСИНГ JSON ---
            try:
                # Пробуем распарсить уже очищенный ответ как JSON
                parsed_json = json5.loads(cleaned_response)

                # Проверяем формат: список или объект с ключом "files"
                if isinstance(parsed_json, list):
                    files_list = parsed_json
                elif isinstance(parsed_json, dict) and 'files' in parsed_json:
                    files_list = parsed_json['files']
                else:
                    raise ValueError("Ответ LLM не содержит списка файлов.")

                self.orchestrator.shared_memory['analyst_result_raw'] = cleaned_response
                return "Техническое задание успешно сгенерировано и передано агенту-разработчику."

            except Exception as e:
                # Логируем ошибку парсинга
                logger.warning(f"Проблема с форматом ответа от LLM: {e}. Попытка очистки или неверный тип данных.")

                self.orchestrator.shared_memory['analyst_result_raw'] = cleaned_response

                # Сообщаем пользователю о проблеме, но продолжаем работу конвейера
                return ("Техническое задание сгенерировано, но имеет ошибки формата.\n"
                        "Агент-разработчик попытается использовать полученный результат.")

        # --- ЭТО ОБЫЧНЫЙ ВОПРОС ---
        else:
            logger.info("Запрос не является задачей на разработку.")
            return self.orchestrator.ask_llm(message) or "Я пока не знаю, что на это ответить."