 #!/usr/bin/env python
import sys
import os

# Добавляем корневую директорию в путь
root_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, root_dir)

from src.main import main

if __name__ == "__main__":
    main()