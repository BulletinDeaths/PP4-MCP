import os
import json
import subprocess
import requests
from typing import Dict, Optional


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
        Принимает ввод от пользователя и передает его первому доступному агенту.
        """
        # Для теста используем первого агента из списка (или заглушку)
        agent_name = self.available_agents[0] if self.available_agents else 'test_agent'

        try:
            # Динамическая загрузка модуля агента по имени файла/папки
            agent_module = __import__(f"{self.agents_dir}.{agent_name}", fromlist=['Agent'])
            agent_instance = agent_module.Agent(orchestrator=self)

            # Передаем ввод агенту и получаем ответ
            response = agent_instance.handle_message(user_input)

            # Логируем взаимодействие
            self._log_interaction(user_input, response)

            return response

        except Exception as e:
            return f"Ошибка при обработке запроса агентом {agent_name}: {str(e)}"

    def _log_interaction(self, user_input: str, agent_response: str):
        """Записывает лог взаимодействия в файл."""
        log_file = os.path.join(self.logs_dir, 'server.log')
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(f"[User] {user_input}\n")
            f.write(f"[Agent] {agent_response}\n")
            f.write("-" * 20 + "\n")

    def call_ollama_api(self, prompt: str, model: str = "llama3") -> Optional[str]:
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

def fake_llm(prompt):
    return f"[FakeLLM Echo] Вы сказали: '{prompt}'"