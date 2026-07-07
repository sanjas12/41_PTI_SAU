#!/usr/bin/env bash
set -e
set -u

# Определяем директорию скрипта и корень проекта
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Путь к build.py
BUILD_FILE="$PROJECT_ROOT/build.py"

# Проверка наличия build.py
if [ ! -f "$BUILD_FILE" ]; then
    echo "[ERROR] build.py не найден в $PROJECT_ROOT"
    exit 1
fi

# Папка сборки
BUILD_DIR="$PROJECT_ROOT/build"

# ── Запекаем git-ревизию ────────────────────────────────────────────────────
REVISION_FILE="$PROJECT_ROOT/src/_revision.py"

if git rev-list --count HEAD > /dev/null 2>&1; then
    GIT_COUNT=$(git rev-list --count HEAD)
    echo "Git revision: rev${GIT_COUNT}"
else
    GIT_COUNT=0
    echo "Git недоступен, используется rev0"
fi

cat > "$REVISION_FILE" << EOF
# Автогенерирован скриптом toexe.sh во время сборки. Не редактировать вручную.
__revision__ = "rev${GIT_COUNT}"
EOF

echo "Записан: $REVISION_FILE"

# Чистим старую сборку
if [ -d "$BUILD_DIR" ]; then
    echo "Cleaning previous build..."
    rm -rf "$BUILD_DIR"
else
    echo "No previous build found, skipping clean."
fi

# Создаём папку для лога заранее (rm -rf её удалил)
mkdir -p "$BUILD_DIR"

# Запуск сборки
echo "Building package..."
cd "$PROJECT_ROOT"
"$PROJECT_ROOT/.venv/Scripts/python.exe" build.py build -q

if [ -f "$REVISION_FILE" ]; then
    rm "$REVISION_FILE"
    echo "Удалён временный файл: $REVISION_FILE"
fi

echo "Build completed successfully."
find "$BUILD_DIR" -type d -name "TG_NALADKA.*" -print
