import os

# Listado de carpetas a excluir
EXCLUDE_DIRS = {'venv', '__pycache__', '.git', 'build', '.pytest_cache'}

def print_tree(start_path='.', indent=''):
    """Imprime un árbol de archivos y carpetas a partir de la ruta indicada, excluyendo carpetas específicas."""
    files_and_dirs = sorted(
        [name for name in os.listdir(start_path) if name not in EXCLUDE_DIRS]
    )
    for i, name in enumerate(files_and_dirs):
        path = os.path.join(start_path, name)
        connector = '└── ' if i == len(files_and_dirs) - 1 else '├── '
        print(indent + connector + name)
        if os.path.isdir(path):
            new_indent = indent + ('    ' if i == len(files_and_dirs) - 1 else '│   ')
            print_tree(path, new_indent)

if __name__ == '__main__':
    print_tree()
