poetry run black ./
poetry run flake8
poetry run mypy --ignore-missing-import --explicit-package-bases --check-untyped-defs ./