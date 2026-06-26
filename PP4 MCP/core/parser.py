import json
import logging
from typing import Dict, Any, Optional

# Настраиваем логгер для этого модуля
logger = logging.getLogger(__name__)


class Parser:
    """Класс для парсинга ответов от LLM."""

    def __init__(self):
        """Инициализация."""
        # self.schema = self._load_schema() # Эта строка больше не нужна
        logger.info("Парсер инициализирован. Валидация по схеме отключена.")

    def _load_schema(self) -> None:
        """Этот метод больше не используется."""
        return None

    def parse_and_validate(self, llm_response: str) -> Optional[Dict[str, Any]]:
        """Парсит ответ от LLM."""
        logger.info("Попытка распарсить ответ от LLM...")

        # 1. Извлекаем JSON из ответа (модель может обернуть его в ```json ...)
        if "```json" in llm_response and "```" in llm_response:
            start = llm_response.find("```json") + len("```json")
            end = llm_response.rfind("```")
            json_str = llm_response[start:end]
        else:
            json_str = llm_response.strip()

        # 2. Парсим JSON
        try:
            data = json.loads(json_str)
            logger.info("Ответ от LLM успешно распарсен как JSON.")

            # Проверяем, что данные имеют ожидаемый формат (список файлов)
            if not isinstance(data, list):
                logger.error("Ответ от LLM не является списком файлов.")
                return None

            return data

        except json.JSONDecodeError as e:
            logger.error(f"Ответ от LLM не является валидным JSON: {e}")
            return None