$ErrorActionPreference = 'Stop'
function Check-Exit { if ($LASTEXITCODE -ne 0) { throw "Verification failed" } }
uv run ruff check apps/api scripts
Check-Exit
uv run ruff format --check apps/api scripts
Check-Exit
uv run mypy apps/api/app scripts/deploy.py
Check-Exit
uv run pytest -q
Check-Exit
npm run web:check
Check-Exit
npm run web:build
Check-Exit
forge test --root contracts --chain-id 31337
Check-Exit
