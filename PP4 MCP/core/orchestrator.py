import os
import json
import subprocess
import requests
import logging

from typing import Dict, Optional, List


class Orchestrator:
    """
    Ядро MCP сервера. Управляет запуском агентов, хранит общую память и взаимодействует с LLM.
    """

    def __init__(self, agents_dir: str, workspace_dir: str, logs_dir: str):
        """
        Инициализация
        """
        self.agents_dir = agents_dir
        self.workspace_dir = workspace_dir
        self.logs_dir = logs_dir

        # Создаем директорию логов, если её нет
        os.makedirs(self.logs_dir, exist_ok=True)

        # Общая память агентов (словарь)
        self.shared_memory: Dict[str, str] = {}

        # Загрузка конфигов из workspace
        self.load_workspace()

        # Поиск доступных агентов в папке agents (для динамической загрузки)
        self.available_agents = self._find_available_agents()

        if not self.available_agents:
            print("Предупреждение: В папке 'agents' не найдено ни одного файла агента.")
            self.available_agents = ['test_agent']  # Заглушка для теста

    def _find_available_agents(self) -> list:
        """Вспомогательный метод для поиска файлов агентов в директории."""
        agents = []
        for file in os.listdir(self.agents_dir):
            if file.endswith('.py') and file != '__init__.py':
                agents.append(file[:-3])
        return agents

    def load_workspace(self):
        """Загрузка данных из рабочей директории"""
        config_path = os.path.join(self.workspace_dir, 'config.json')
        if os.path.exists(config_path) and os.path.getsize(config_path) > 0:
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    self.shared_memory.update(json.load(f))
                print(f"Загружено {len(self.shared_memory)} ключей из конфига.")
            except json.JSONDecodeError:
                print(f"Внимание: файл {config_path} повреждён или содержит некорректный JSON. Пропускаю загрузку.")
        else:
            print(f"Файл {config_path} не найден или пустой. Используется память по умолчанию.")

    def process_user_input(self, user_input: str) -> str:
        """
        Принимает ввод от пользователя.
        Если запрос на разработку - запускает полный конвейер.
        Если команда 'use <agent>' - переключает активного агента.
        В остальных случаях использует текущего активного агента.
        """
        # --- КОМАНДА ДЛЯ СМЕНЫ АКТИВНОГО АГЕНТА ---
        if user_input.lower().startswith("use "):
            agent_name = user_input[4:].strip()  # Убираем "use "

            if agent_name in self.available_agents:
                self.active_agent_name = agent_name
                return f"Агент успешно переключен на '{agent_name}'."
            else:
                return f"Ошибка: Агент '{agent_name}' не найден. Доступные агенты: {', '.join(self.available_agents)}"

        elif user_input.lower() in self.available_agents:
            self.active_agent_name = user_input.lower()
            return f"Агент успешно переключен на '{self.active_agent_name}'."

        # --- НОВАЯ ЛОГИКА: ПРОВЕРКА НА ЗАПРОС РАЗРАБОТКИ ---
        # Эта проверка теперь выполняется ВСЕГДА, если это не была команда 'use'.
        development_keywords = ['созда', 'разработ', 'код', 'программ']
        is_dev_task = any(keyword in user_input.lower() for keyword in development_keywords)

        if is_dev_task:
            from core.parser import Parser
            parser = Parser()
            result = self.execute_development_pipeline(user_input, parser)
            return result

        # --- ОБРАБОТКА ОБЫЧНОГО ЗАПРОСА ТЕКУЩИМ АКТИВНЫМ АГЕНТОМ ---
        # Логика для обычных вопросов (как 'привет', 'как дела?')
        agent_name = getattr(self, 'active_agent_name', self.available_agents[0])

        try:
            agent_module = __import__(f"{self.agents_dir}.{agent_name}", fromlist=['Agent'])
            agent_instance = agent_module.Agent(orchestrator=self)
            response = agent_instance.handle_message(user_input)
            self._log_interaction(user_input, response)
            return response
        except Exception as e:
            return f"Ошибка при обработке запроса агентом {agent_name}: {str(e)}"

    def execute_development_pipeline(self, user_query: str, parser: 'Parser') -> str:
        """
        Координирует работу агентов-аналитика и разработчика.
        :param user_query: Исходный запрос пользователя.
        :param parser: Экземпляр класса Parser для валидации.
        :return: Финальное сообщение для пользователя.
        """
        # Получаем логгер для текущего модуля (__name__ будет 'core.orchestrator')
        logger = logging.getLogger(__name__)

        logger.info("Запуск конвейера разработки...")

        # --- ЭТАП 1: АНАЛИТИК ---
        from agents.analyst import Agent as AnalystAgent
        analyst_agent = AnalystAgent(self)
        tze_response = analyst_agent.handle_message(user_query)

        # Логируем ответ аналитика
        self._log_interaction(user_query, tze_response)

        # Проверяем, нет ли в ответе ошибки
        if "Ошибка:" in tze_response:
            return tze_response

        # Парсим и валидируем ответ аналитика
        parsed_tz = parser.parse_and_validate(tze_response)
        if not parsed_tz:
            return "Ошибка: Агент-аналитик сгенерировал некорректное техническое задание."

        # Сохраняем валидированное ТЗ в общую память для следующего агента
        self.shared_memory['analyst_result'] = json.dumps(parsed_tz)
        # Или можно сохранить исходный текст, если DeveloperAgent сам будет его парсить
        # self.shared_memory['analyst_result_raw'] = tze_response

        # --- ЭТАП 2: РАЗРАБОТЧИК ---
        from agents.developer import DeveloperAgent
        developer_agent = DeveloperAgent(self)
        code_generation_result = developer_agent.handle_message()

        # Логируем результат работы разработчика
        self._log_interaction("Разработчику передано ТЗ", code_generation_result)

        return code_generation_result

    def _log_interaction(self, user_input: str, agent_response: str):
        """Записывает лог взаимодействия в файл."""
        log_file = os.path.join(self.logs_dir, 'server.log')
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(f"[User] {user_input}\n")
            f.write(f"[Agent] {agent_response}\n")
            f.write("-" * 20 + "\n")

    def call_ollama_api(self, prompt: str, model: str = "qwen2.5-coder:3b") -> Optional[str]:
        try:
            url = "http://localhost:11434/api/generate"
            payload = {"model": model, "prompt": prompt, "stream": False}
            response = requests.post(url, json=payload)
            response.raise_for_status()

            data = response.json()
            return data.get('response')

        except requests.exceptions.RequestException as e:
            print(f"Ошибка при запросе к Ollama API: {e}")
            return None

    def call_gigachat_api(
        self,
        messages: List[Dict[str, str]],
        model: str = "GigaChat",
        temperature: float = 0.7,
        max_tokens: int = 1024
    ) -> Optional[str]:
        """
        Вызов GigaChat API (Сбер).
        Требуется OAuth-токен в config.json: "gigachat_token".
        """
        token = self.shared_memory.get('gigachat_token')
        if not token:
            print("Ошибка: gigachat_token не задан в config.json")
            return None

        url = self.shared_memory.get(
            'gigachat_api_url',
            'https://gigachat.devices.sberbank.ru/api/v1/chat/completions'
        )

        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }

        try:
            response = requests.post(url, headers=headers, json=payload)
            response.raise_for_status()

            data = response.json()
            return data['choices'][0]['message']['content']

        except requests.exceptions.RequestException as e:
            print(f"Ошибка при запросе к GigaChat API: {e}")
            return None
        except (KeyError, IndexError) as e:
            print(f"Ошибка парсинга ответа GigaChat: {e}")
            return None

    def ask_llm(self, prompt: str, provider: str = "ollama") -> Optional[str]:
        """
        Универсальный метод вызова LLM через указанный провайдер.
        provider: "ollama" | "gigachat"
        """
        if provider == "gigachat":
            messages = [{"role": "user", "content": prompt}]
            return self.call_gigachat_api(messages)
        else:
            return self.call_ollama_api(prompt)

def fake_llm(prompt):
    return f"[FakeLLM Echo] Вы сказали: '{prompt}'"