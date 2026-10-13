# Controlled Autonomy — Local Startup Guide

Project:

```powershell
cd D:\autonomous-blockchain-agent
```

## Things you normally DO NOT need to repeat

Do not rerun these unless dependencies/contracts changed:

```powershell
uv sync --frozen
npm ci --ignore-scripts
npm run contracts:build
```

PostgreSQL, Python, Node.js and the project dependencies are already installed.

---

## 1. Make sure PostgreSQL is running

Your PostgreSQL service should normally start automatically with Windows.

Your database should already exist, for example:

```text
autonomy
```

---

## 2. Set environment variables

Open PowerShell in the project folder.

Set a new local owner token:

```powershell
$env:AUTONOMY_OWNER_TOKEN = [guid]::NewGuid().ToString('N')
$env:AUTONOMY_OWNER_TOKEN | Set-Clipboard
```

Set the PostgreSQL connection:

```powershell
$env:AUTONOMY_DATABASE_URL = "postgresql+psycopg://postgres:YOUR_PASSWORD@localhost:5432/autonomy"
```

The owner token is now copied to your clipboard for the web application.

These variables disappear when you close PowerShell.

---

## 3. Start Anvil

Open a separate PowerShell:

```powershell
cd D:\autonomous-blockchain-agent
```

Run:

```powershell
.\node_modules\@foundry-rs\anvil-win32-amd64\bin\anvil.exe --chain-id 31337 --host 127.0.0.1 --silent
```

Keep this terminal running.

Anvil is now available at:

```text
http://127.0.0.1:8545
```

---

## 4. Deploy the fake blockchain environment

Whenever you start a **fresh Anvil blockchain**, deploy the contracts again:

```powershell
cd D:\autonomous-blockchain-agent

uv run python scripts/deploy.py
```

This creates the local smart account, MockUSDC, MockDex and fake assets.

Important: Anvil is temporary. If Anvil is restarted, its previous contracts and transactions disappear. Do not keep old application blockchain state while using a completely fresh Anvil chain; use a clean development database/state when doing a full reset.

---

## 5. Run database migrations

Normally this is safe to run whenever starting the project:

```powershell
uv run alembic upgrade head
```

It only applies migrations that have not already been applied.

---

## 6. Start FastAPI

In the PowerShell where your environment variables are set:

```powershell
uv run uvicorn app.main:app --app-dir apps/api --reload
```

Backend:

```text
http://localhost:8000
```

API documentation:

```text
http://localhost:8000/docs
```

Keep this terminal running.

---

## 7. Start React

Open another terminal:

```powershell
cd D:\autonomous-blockchain-agent

npm run web:dev
```

Frontend:

```text
http://localhost:5173
```

Open it in your browser and paste the `AUTONOMY_OWNER_TOKEN` copied earlier.

---

# Normal startup order

```text
PostgreSQL
    ↓
Set environment variables
    ↓
Anvil
    ↓
deploy.py
    ↓
alembic upgrade head
    ↓
FastAPI
    ↓
React
    ↓
localhost:5173
```

## Commands you will use most often

**Terminal 1 — Blockchain**

```powershell
.\node_modules\@foundry-rs\anvil-win32-amd64\bin\anvil.exe --chain-id 31337 --host 127.0.0.1 --silent
```

**Terminal 2 — Backend**

```powershell
$env:AUTONOMY_OWNER_TOKEN = [guid]::NewGuid().ToString('N')
$env:AUTONOMY_OWNER_TOKEN | Set-Clipboard
$env:AUTONOMY_DATABASE_URL = "postgresql+psycopg://postgres:YOUR_PASSWORD@localhost:5432/autonomy"

uv run python scripts/deploy.py
uv run alembic upgrade head
uv run uvicorn app.main:app --app-dir apps/api --reload
```

**Terminal 3 — Frontend**

```powershell
npm run web:dev
```

Then visit:

```text
http://localhost:5173
```
