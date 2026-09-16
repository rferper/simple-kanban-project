<#
.SYNOPSIS
  NextLane task runner for Windows PowerShell.

.DESCRIPTION
  The same targets as the Makefile, for people not in WSL.

      .\make.ps1              list the targets
      .\make.ps1 install      install backend dependencies
      .\make.ps1 run          run the whole app, API and frontend
      .\make.ps1 test         run the test suite

  Why this exists as well as the Makefile: GNU make on Windows hands recipes to
  cmd.exe, and the Makefile's recipes are POSIX shell — `trap`, `&`, `wait`.
  Those work in WSL, macOS and CI, and would break under cmd.

  The two files are two front doors onto the same commands. Change one, change
  the other.

.PARAMETER Target
  Which task to run. Defaults to listing them.
#>

[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet('help', 'install', 'run', 'api', 'web', 'test', 'test-one', 'lint', 'types', 'check', 'open', 'clean', 'docker-build', 'docker-run', 'compose-up', 'compose-down',
        'postgres', 'postgres-stop', 'test-postgres', 'test-integration')]
    [string]$Target = 'help',

    [int]$ApiPort = 8001,
    [int]$WebPort = 8000,

    # The container is one process serving both, so it has one port of its own.
    [int]$AppPort = 8000,
    [string]$Image = 'nextlane',

    # The local Postgres is the `db` service in docker-compose.yaml, and there
    # is deliberately only one of it, so `run` and `compose-up` look at the same
    # board. Two databases on it: `nextlane` for the app, `nextlane_test` for
    # the store contract. Not 5432, so it cannot collide with a Postgres
    # somebody already runs.
    [int]$DbPort = 55432,

    # For test-one:  .\make.ps1 test-one -T test_auth
    [string]$T = ''
)

$ErrorActionPreference = 'Stop'

$Root     = $PSScriptRoot
$Backend  = Join-Path $Root 'backend'
$Frontend = Join-Path $Root 'frontend'
$DevDsn   = "postgresql://nextlane:nextlane@localhost:${DbPort}/nextlane"
$TestDsn  = "postgresql://nextlane:nextlane@localhost:${DbPort}/nextlane_test"

<#
  Run an external program.

  Windows PowerShell turns anything a native command writes to stderr into an
  ErrorRecord, and under `ErrorActionPreference = 'Stop'` that aborts the script
  even when the command succeeded — `uv` printing "Using CPython 3.12" was enough
  to kill this script before this helper existed. So: relax the preference around
  the call, and judge success by the exit code, which is the thing that means it.
#>
function Invoke-Native {
    param(
        [Parameter(Mandatory)][string]$File,
        [string[]]$Arguments = @(),
        [string]$WorkingDirectory,
        [switch]$IgnoreExitCode
    )

    $previous = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    if ($WorkingDirectory) { Push-Location $WorkingDirectory }

    try {
        & $File @Arguments
        $code = $LASTEXITCODE
        if (-not $IgnoreExitCode -and $code -ne 0) {
            throw "$File exited with code $code"
        }
    }
    finally {
        if ($WorkingDirectory) { Pop-Location }
        $ErrorActionPreference = $previous
    }
}

function Find-Python {
    foreach ($candidate in 'python', 'python3') {
        $found = Get-Command $candidate -ErrorAction SilentlyContinue
        if ($found) { return $found.Source }
    }
    if (Get-Command 'py' -ErrorAction SilentlyContinue) { return 'py' }

    throw 'No Python found on PATH (looked for python, python3, py).'
}

function Assert-Uv {
    if (-not (Get-Command 'uv' -ErrorAction SilentlyContinue)) {
        throw 'uv is not on PATH. See https://docs.astral.sh/uv/'
    }
}

function Show-Help {
    Write-Host ''
    Write-Host '  NextLane'
    Write-Host ''
    Write-Host '  .\make.ps1 install    install backend dependencies'
    Write-Host '  .\make.ps1 run        run the whole app, API and frontend'
    Write-Host '  .\make.ps1 api        run just the API'
    Write-Host '  .\make.ps1 web        run just the frontend'
    Write-Host '  .\make.ps1 test       run the test suite'
    Write-Host '  .\make.ps1 postgres   start the local Postgres (before run)'
    Write-Host '  .\make.ps1 test-postgres  run the suite against Postgres as well'
    Write-Host '  .\make.ps1 test-integration  run the compose stack and test against it'
    Write-Host '  .\make.ps1 lint       lint the backend and check the frontend'
    Write-Host '  .\make.ps1 types      type-check the backend'
    Write-Host '  .\make.ps1 check      lint + types + tests'
    Write-Host '  .\make.ps1 test-one -T test_auth'
    Write-Host '  .\make.ps1 open       open the app in a browser'
    Write-Host '  .\make.ps1 clean      remove caches'
    Write-Host ''
    Write-Host '  .\make.ps1 docker-build   build the container image'
    Write-Host '  .\make.ps1 docker-run     run it - the whole app on one port'
    Write-Host '  .\make.ps1 compose-up     run it with Postgres, through docker compose'
    Write-Host '  .\make.ps1 compose-down   stop those (docker compose down -v drops the data)'
    Write-Host ''
    Write-Host "  frontend  http://localhost:$WebPort"
    Write-Host "  API       http://localhost:$ApiPort   docs at /docs"
    Write-Host '  sign in   researcher@example.com / nextlane'
    Write-Host ''
}

function Invoke-Install {
    Assert-Uv
    Invoke-Native -File 'uv' -Arguments @('sync') -WorkingDirectory $Backend
}

function Invoke-Api {
    Assert-Uv
    Invoke-Native -File 'uv' -WorkingDirectory $Backend -IgnoreExitCode -Arguments @(
        'run', 'uvicorn', 'app.main:app', '--reload', '--port', "$ApiPort"
    )
}

function Invoke-Web {
    $py = Find-Python
    Invoke-Native -File $py -IgnoreExitCode -Arguments @(
        '-m', 'http.server', "$WebPort", '--directory', $Frontend
    )
}

function Invoke-Run {
    Assert-Uv
    $py = Find-Python

    Write-Host 'NextLane'
    Write-Host "  database  $DevDsn"
    Write-Host "  frontend  http://localhost:$WebPort"
    Write-Host "  API       http://localhost:$ApiPort  (docs at /docs)"
    Write-Host '  sign in   researcher@example.com / nextlane'
    Write-Host ''
    Write-Host '  Ctrl-C stops both.'
    Write-Host ''

    # The API goes in the background; the frontend holds the foreground so that
    # Ctrl-C lands here and the finally block can take the API down with it.
    $api = Start-Process -FilePath 'uv' `
        -ArgumentList @('run', 'uvicorn', 'app.main:app', '--reload', '--port', "$ApiPort") `
        -WorkingDirectory $Backend -PassThru -NoNewWindow

    try {
        Invoke-Web
    }
    finally {
        if ($api -and -not $api.HasExited) {
            # /T because uvicorn --reload spawns a worker child, and killing only
            # the parent leaves the child holding the port.
            & taskkill /PID $api.Id /T /F 2>&1 | Out-Null
        }
        Write-Host ''
        Write-Host 'Stopped.'
    }
}

function Invoke-Test {
    Assert-Uv
    Invoke-Native -File 'uv' -Arguments @('run', 'pytest') -WorkingDirectory $Backend
}

function Invoke-TestOne {
    if (-not $T) { throw 'Give it a pattern:  .\make.ps1 test-one -T test_auth' }
    Assert-Uv
    Invoke-Native -File 'uv' -WorkingDirectory $Backend -Arguments @(
        'run', 'pytest', '-k', $T
    )
}

function Invoke-ComposeUp {
    Assert-Docker
    Invoke-Native -File 'docker' -WorkingDirectory $Root -Arguments @(
        'compose', 'up', '--build', '-d'
    )
    Write-Host ''
    Write-Host "NextLane  http://localhost:$AppPort  (docs at /docs)"
    Write-Host '  sign in   researcher@example.com / nextlane'
    Write-Host '  logs      docker compose logs -f'
}

function Invoke-ComposeDown {
    Assert-Docker
    # Keeps the volume. `docker compose down -v` is how you throw the data away,
    # and it is deliberately not a target - that should be typed on purpose.
    Invoke-Native -File 'docker' -WorkingDirectory $Root -Arguments @('compose', 'down')
}

function Invoke-Postgres {
    Assert-Docker

    Invoke-Native -File 'docker' -WorkingDirectory $Root -Arguments @(
        'compose', 'up', '-d', '--wait', 'db'
    )

    # POSTGRES_DB creates the app's database, but only the first time the volume
    # is built, and this has to be right for an existing one too. Asking which
    # are there beats creating and ignoring the failure: `createdb` on an
    # existing database exits non-zero, and that would be the last exit code
    # this task leaves behind.
    $existing = & docker compose exec -T db psql -U nextlane -d nextlane -tAc `
        'SELECT datname FROM pg_database'
    if ($existing -notcontains 'nextlane_test') {
        Invoke-Native -File 'docker' -WorkingDirectory $Root -Arguments @(
            'compose', 'exec', '-T', 'db', 'createdb', '-U', 'nextlane', 'nextlane_test'
        ) | Out-Null
    }

    Write-Host ''
    Write-Host 'Postgres is up.'
    Write-Host "  app    $DevDsn"
    Write-Host "  tests  $TestDsn"
}

function Invoke-PostgresStop {
    Assert-Docker
    # Keeps the board. `docker compose down -v` is how you throw it away.
    Invoke-Native -File 'docker' -WorkingDirectory $Root -Arguments @(
        'compose', 'stop', 'db'
    )
}

function Invoke-TestIntegration {
    Assert-Uv
    Assert-Docker
    # Its own compose project and its own ports, so this cannot touch - or be
    # confused with - a development stack that is already running.
    Invoke-Native -File 'uv' -WorkingDirectory $Backend -Arguments @(
        'run', 'pytest', '-m', 'integration'
    )
}

function Invoke-TestPostgres {
    Assert-Uv
    $env:NEXTLANE_TEST_POSTGRES = $TestDsn
    try {
        Invoke-Native -File 'uv' -Arguments @('run', 'pytest') -WorkingDirectory $Backend
    }
    finally {
        Remove-Item Env:NEXTLANE_TEST_POSTGRES -ErrorAction SilentlyContinue
    }
}

function Invoke-Lint {
    Assert-Uv
    Invoke-Native -File 'uv' -Arguments @('run', 'ruff', 'check', '.') -WorkingDirectory $Backend
    Invoke-Native -File 'uv' -Arguments @('run', 'ruff', 'format', '--check', '.') -WorkingDirectory $Backend

    # No ESLint: that means npm and a node_modules, which decisions #3 avoided.
    # This is dependency-free and catches what actually breaks a no-build
    # frontend - a typo'd import path or a renamed export.
    if (Get-Command 'node' -ErrorAction SilentlyContinue) {
        Invoke-Native -File 'node' -Arguments @((Join-Path $Frontend 'check.mjs'))
    }
    else {
        Write-Host 'frontend: skipped (node not on PATH)'
    }
}

function Invoke-Types {
    Assert-Uv
    Invoke-Native -File 'uv' -Arguments @('run', 'ty', 'check') -WorkingDirectory $Backend
}

function Invoke-Check {
    Invoke-Lint
    Invoke-Types
    Invoke-Test
    Write-Host ''
    Write-Host 'lint, types and tests all pass.'
}

function Invoke-Open {
    Start-Process "http://localhost:$WebPort"
}

function Assert-Docker {
    if (-not (Get-Command 'docker' -ErrorAction SilentlyContinue)) {
        throw 'docker is not on PATH. See https://docs.docker.com/get-started/'
    }
}

function Invoke-DockerBuild {
    Assert-Docker
    Invoke-Native -File 'docker' -WorkingDirectory $Root -Arguments @(
        'build', '-t', $Image, '.'
    )
}

function Invoke-DockerRun {
    Assert-Docker

    Write-Host "NextLane  http://localhost:$AppPort  (docs at /docs)"
    Write-Host '  sign in   researcher@example.com / nextlane'
    Write-Host ''

    # -e with no value passes the key through when it is set in this shell and
    # leaves it unset when it is not, which is the arrangement the app wants:
    # the advert reader is optional and the app is fully usable without it.
    Invoke-Native -File 'docker' -IgnoreExitCode -Arguments @(
        'run', '--rm', '-it',
        '-p', "${AppPort}:8000",
        '-v', 'nextlane-data:/data',
        '-e', 'ANTHROPIC_API_KEY',
        $Image
    )
}

function Invoke-Clean {
    foreach ($name in '__pycache__', '.pytest_cache') {
        Get-ChildItem -Path $Root -Filter $name -Recurse -Directory -ErrorAction SilentlyContinue |
            Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
    }
    Write-Host 'cleaned'
}

switch ($Target) {
    'help'     { Show-Help }
    'install'  { Invoke-Install }
    'run'      { Invoke-Run }
    'api'      { Invoke-Api }
    'web'      { Invoke-Web }
    'test'     { Invoke-Test }
    'test-one' { Invoke-TestOne }
    'lint'     { Invoke-Lint }
    'types'    { Invoke-Types }
    'check'    { Invoke-Check }
    'open'     { Invoke-Open }
    'clean'    { Invoke-Clean }
    'docker-build' { Invoke-DockerBuild }
    'docker-run'   { Invoke-DockerRun }
    'compose-up'    { Invoke-ComposeUp }
    'compose-down'  { Invoke-ComposeDown }
    'postgres'      { Invoke-Postgres }
    'postgres-stop' { Invoke-PostgresStop }
    'test-postgres' { Invoke-TestPostgres }
    'test-integration' { Invoke-TestIntegration }
}
