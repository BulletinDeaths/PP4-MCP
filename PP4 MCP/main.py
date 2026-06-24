import os
import sys
from pathlib import Path

# Добавляем корень проекта в PYTHONPATH, чтобы импортировать модули из подпапок
project_root = Path(__file__).parent
sys.path.append(str(project_root))

from core.orchestrator import Orchestrator


def main():
    """
    Точка входа в приложение.
    Создает оркестратор и запускает цикл обработки команд.
    """
    # Инициализируем ядро системы. Передаем пути к рабочим директориям.
    orchestrator = Orchestrator(
        agents_dir="agents",
        workspace_dir="workspace",
        logs_dir="logs"
    )

    print("ИИ-Фабрика запущена. Введите сообщение для агента (введите 'exit' для выхода).")

    # Главный цикл взаимодействия с пользователем
    while True:
        user_input = input("Вы: ")
        if user_input.lower() == 'exit':
            print("Завершение работы...")
            break

        # Передаем ввод пользователя оркестратору для обработки первым агентом
        response = orchestrator.process_user_input(user_input)
        print(f"Агент: {response}")


if __name__ == "__main__":
    main()