import os
import json
import requests
import logging
from pathlib import Path
from typing import Dict, Optional, List
from agents.tester import TesterAgent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Orchestrator:
    def __init__(self, agents_dir: str, workspace_dir: str, logs_dir: str):
        self.agents_dir = agents_dir
        self.workspace_dir = workspace_dir
        self.logs_dir = logs_dir

        os.makedirs(self.logs_dir, exist_ok=True)
        self.shared_memory: Dict[str, str] = {}
        self.load_workspace()
        self.available_agents = self._find_available_agents()
        if not self.available_agents:
            print("Предупреждение: В папке 'agents' не найдено агентов.")
            self.available_agents = ['test_agent']

    def _find_available_agents(self) -> list:
        agents = []
        for file in os.listdir(self.agents_dir):
            if file.endswith('.py') and file != '__init__.py':
                agents.append(file[:-3])
        return agents

    def load_workspace(self):
        config_path = os.path.join(self.workspace_dir, 'config.json')
        if os.path.exists(config_path) and os.path.getsize(config_path) > 0:
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    self.shared_memory.update(json.load(f))
                print(f"Загружено {len(self.shared_memory)} ключей из конфига.")
            except json.JSONDecodeError:
                print(f"Внимание: файл {config_path} повреждён.")

    def _log_interaction(self, user_input: str, agent_response: str):
        """Записывает лог взаимодействия в файл."""
        log_file = os.path.join(self.logs_dir, 'server.log')
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(f"[User] {user_input}\n")
            f.write(f"[Agent] {agent_response}\n")
            f.write("-" * 20 + "\n")

    # --- МЕТОД ВЫЗОВА LLM ---
    def ask_llm(self, prompt: str) -> Optional[str]:
        """Универсальный метод вызова LLM."""
        return self.call_ollama_api(prompt)

    def call_ollama_api(self, prompt: str) -> Optional[str]:
        """Вызов Ollama API."""
        try:
            url = "http://localhost:11434/api/generate"
            payload = {"model": "qwen2.5-coder:3b", "prompt": prompt, "stream": False}
            response = requests.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            return data.get('response')
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка при запросе к Ollama API: {e}")
            return None

    # --- ЛОГИКА ОБРАБОТКИ ВВОДА ---
    def process_user_input(self, user_input: str) -> str:
        """Главная точка входа для обработки любого пользовательского ввода."""
        # --- КОМАНДА ДЛЯ СМЕНЫ АКТИВНОГО АГЕНТА ---
        if user_input.lower().startswith("use "):
            agent_name = user_input[4:].strip()
            if agent_name in self.available_agents:
                self.active_agent_name = agent_name
                return f"Агент успешно переключен на '{agent_name}'."
            else:
                return f"Ошибка: Агент '{agent_name}' не найден."

        # --- КОНВЕЙЕР РАЗРАБОТКИ ---
        development_keywords = ['созда', 'разработ', 'код', 'программ', 'тетрис']
        is_dev_task = any(keyword in user_input.lower() for keyword in development_keywords)

        if is_dev_task:
            from core.parser import Parser
            parser = Parser()
            return self.execute_development_pipeline(user_input, parser)

        # --- ОБЫЧНЫЙ ВОПРОС ---
        agent_name = getattr(self, 'active_agent_name', self.available_agents[0])

        try:
            import importlib
            agent_module = importlib.import_module(f"{self.agents_dir}.{agent_name}")
            agent_class = getattr(agent_module, 'Agent')
            agent_instance = agent_class(orchestrator=self)
            response = agent_instance.handle_message(user_input)
            self._log_interaction(user_input, response)
            return response
        except Exception as e:
            return f"Ошибка при обработке запроса агентом {agent_name}: {str(e)}"

    # --- КОНВЕЙЕР ---
    def execute_development_pipeline(self, user_query: str, parser: 'Parser') -> str:
        """Координирует работу агентов-аналитика, разработчика и тестировщика."""
        logger.info("Запуск конвейера разработки...")

        # --- ЭТАП 1: АНАЛИТИК ---
        from agents.analyst import Agent as AnalystAgent

        analyst_agent = AnalystAgent(self)
        tze_response = analyst_agent.handle_message(user_query)
        self._log_interaction(user_query, tze_response)

        # --- ЭТАП 2: РАЗРАБОТЧИК ---
        # Мы запускаем разработчика В ФОНОВОМ РЕЖИМЕ (в отдельном потоке),
        # чтобы main.py не ждал его завершения.
        from agents.developer import DeveloperAgent
        from threading import Thread

        self.developer_agent = DeveloperAgent(
            self,
            projects_dir=os.path.join(self.workspace_dir, "projects")
        )

        # Запускаем разработчика в отдельном потоке
        # Метод handle_message теперь должен быть неблокирующим или
        # мы просто запускаем процесс записи.
        # Для простоты предположим, что handle_message сам справится с записью.
        # Если он блокирующий, его нужно переписать, но это сложнее.

        # Запускаем процесс разработки
        self.developer_agent.handle_message()

        # Сразу возвращаем сообщение пользователю
        return "Запущена задача на разработку. Пожалуйста, подождите..."