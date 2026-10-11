# AXON
Human Capital Intelligence Platform

## Backend quick start

The backend requires Python 3.14 or newer. From the repository root, create and
activate a project-local virtual environment, then install the app and test
dependencies:

```powershell
$python314 = "$env:LOCALAPPDATA\Programs\Python\Python314-32\python.exe"
& $python314 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[test]"
```

Set the optional, non-secret environment name and start the development server:

```powershell
$env:AXON_ENV = "development"
python -m uvicorn axon.main:app --reload
```

The health endpoint is available at <http://127.0.0.1:8000/health>. Interactive
API documentation is available at <http://127.0.0.1:8000/docs>.

Run the automated tests from the repository root:

```powershell
python -m pytest
```

`AXON_ENV` accepts `development`, `test`, or `production` and defaults to
`development`. The current app reads it from the process environment and does
not load `.env` files. Never commit credentials.

The health route checks only that the API process responds. It does not connect
to a database, Ollama, or an external service.

## Market scanner

The first market scanner searches Remotive's public remote-jobs feed. It needs
no API key. Start the API as above, then request a keyword (two or more
characters) to receive up to five readable JSON results:

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/market/jobs?keyword=python&limit=5" |
    ConvertTo-Json -Depth 5
```

The result includes the title, company, category, eligible location, salary
when supplied, publication date, original Remotive job URL, and source
attribution. The API links each job back to Remotive as required by its
[public API terms](https://remotive.com/remote-jobs/api). Remotive states that
public API listings may be delayed by 24 hours and advises no more than four
feed requests per day. AXON caches a successful feed in memory for six hours;
the cache resets when the server process restarts. Search is applied locally
because provider-side query parameters did not filter reliably in the live
check.

The scanner test suite uses mocked responses and does not call Remotive:

```powershell
python -m pytest
```

### Try the scanner in Python IDLE

The IDLE workflow runs the same scanner code used by the API. In PowerShell,
open IDLE with the installed Python 3.14.8 interpreter:

```powershell
& "$env:LOCALAPPDATA\Programs\Python\Python314-32\python.exe" -m idlelib
```

In IDLE, choose **File → Open**, select `run_market_scan.py` in the AXON
repository, then press **F5**. Enter a keyword such as `Python` in the Shell.
The script uses the existing `axon.market_scanner` module and needs no FastAPI
or third-party packages.

IDLE is useful for trying the scanner, but it is not the web server. To run the
FastAPI endpoint, activate the project's `.venv` in PowerShell and run:

```powershell
python -m uvicorn axon.main:app --reload
```

If `py -3.14` does not find this 32-bit interpreter, create the project
environment with its full path:

```powershell
& "$env:LOCALAPPDATA\Programs\Python\Python314-32\python.exe" -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[test]"
```
