import json
import jsonschema
import logging
from typing import Dict, Any, Optional

# Настраиваем логгер для этого модуля
logger = logging.getLogger(__name__)

class Parser:
    """
    Класс для парсинга и валидации ответов от LLM.
    """

    def __init__(self):
        """Инициализация: загружаем JSON-схему для валидации."""
        self.schema = self._load_schema()

    def _load_schema(self) -> Optional[Dict]:
        """Загружает JSON-схему из файла."""
        schema_path = "schemas/project_schema.json"
        try:
            with open(schema_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.error(f"Файл схемы не найден по пути {schema_path}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Ошибка декодирования JSON-схемы: {e}")
            return None

    def parse_and_validate(self, llm_response: str) -> Optional[Dict[str, Any]]:
        """
        Парсит ответ от LLM и валидирует его по схеме.
        :param llm_response: Сырой ответ от языковой модели.
        :return: Валидный словарь с данными или None в случае ошибки.
        """
        if not self.schema:
            logger.error("Схема для валидации не загружена. Валидация невозможна.")
            return None

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
        except json.JSONDecodeError as e:
            logger.error(f"Ответ от LLM не является валидным JSON: {e}")
            return None

        # 3. Валидируем данные по схеме
        try:
            jsonschema.validate(instance=data, schema=self.schema)
            logger.info("Ответ от LLM успешно прошел валидацию.")
            return data
        except jsonschema.ValidationError as ve:
            logger.error(f"Невалидный ответ от LLM: {ve.message}")
            return None