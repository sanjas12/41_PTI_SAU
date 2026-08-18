# Title


## Установка (из репозитория)

### 1. Требования

| Параметр | Значение |
|---|---|
| Python | 3.8.10 |
| ОС | Windows 7 и выше |
| [uv](https://github.com/astral-sh/uv) | 0.11.7 |

### 2. Настройка окружения

#### 2.1 Создание виртуального окружения (VSCode)

```bash
bash scripts/init_env.sh
```

#### 2.2 Установка зависимостей (если скрипт из пункта 2.1 не сработал)

Рекомендуется — через [uv](https://github.com/astral-sh/uv):

```bash
uv sync
```

Без uv:

```bash
pip install -r requirements.txt
```

> `requirements.txt` генерируется из `pyproject.toml` — не редактировать вручную.

### 3. Запуск

#### 3.1 C uv

```bash
uv run python src/main.py     - скрипт для инициализации БД
```

#### 3.2 Без uv

```bash
source .venv/Scripts/activate
python src/main.py
```

---

## Использование (Windows — exe)

### Требования

- [Visual C++ Redistributable 2015–2022](https://aka.ms/vs/17/release/vc_redist.x64.exe)
- ОС: Windows 7 и выше

## help

TODO
1. Узнать сколько памяти использует программа


IP для компа -> 192.168.0.99
IP для ETY -> 192.168.0.20
IP для PLC-CPU -> 192.168.0.1
