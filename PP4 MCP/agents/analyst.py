import os
import logging
import json
from typing import Dict, Any, Optional

# Настройка логгера для модуля
logger = logging.getLogger(__name__)

class Agent:
    """
    Агент-аналитик, который преобразует запросы на разработку в структурированное ТЗ.
    Для обычных вопросов и сообщений использует стандартный LLM.
    """

    def __init__(self, orchestrator):
        """
        Инициализация агента.
        :param orchestrator: Ссылка на главный оркестратор.
        """
        self.orchestrator = orchestrator
        self.prompt_path = os.path.join("workspace", "prompts", "analyst.md")

    def _is_development_request(self, message: str) -> bool:
        """
        Определяет, является ли сообщение запросом на разработку.
        :param message: Сообщение пользователя.
        :return: True, если это запрос на разработку, иначе False.
        """
        # Список ключевых слов, которые указывают на запрос на разработку
        keywords = [
            'созда', 'разработ', 'сайт', 'программ', 'приложен', 'код',
            'сервис', 'система', 'бот', 'алгоритм'
        ]
        # Проверяем наличие ключевых слов в сообщении (регистронезависимо)
        return any(keyword in message.lower() for keyword in keywords)

    def handle_message(self, message: str) -> str:
        """
        Обрабатывает входящее сообщение.
        Если это запрос на разработку — формирует ТЗ.
        Иначе — просто отвечает на вопрос через LLM.
        """
        # 1. Проверяем тип запроса
        if self._is_development_request(message):
            # --- Это запрос на РАЗРАБОТКУ ---
            logger.info("Запрос распознан как задача на разработку. Формирую ТЗ.")
            try:
                with open(self.prompt_path, 'r', encoding='utf-8') as f:
                    prompt_template = f.read()
                system_prompt = prompt_template.format(user_query=message)
            except FileNotFoundError as e:
                logger.error(f"Файл промпта не найден: {e}")
                return "Ошибка: не удалось найти файл с инструкциями для аналитика."

            # Вызываем LLM для генерации ТЗ
            llm_response = self.orchestrator.ask_llm(system_prompt, provider="ollama")
            if llm_response is None:
                return "Ошибка: Не удалось получить ответ от языковой модели при генерации ТЗ."
            return llm_response

        else:
            # --- Это ОБЫЧНЫЙ вопрос или сообщение ---
            logger.info("Запрос не является задачей на разработку.")
            # Просто отправляем сообщение в LLM и возвращаем ответ
            provider = self.orchestrator.shared_memory.get('llm_provider', 'ollama')
            return self.orchestrator.ask_llm(message, provider=provider) or "Я пока не знаю, что на это ответить."