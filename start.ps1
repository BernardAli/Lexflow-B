$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if (Test-Path '.env') {
  Get-Content .env | ForEach-Object {
    $line = $_.Trim()
    if ($line -and -not $line.StartsWith('#')) {
      $kv = $line -split '=', 2
      if ($kv.Length -eq 2) { [Environment]::SetEnvironmentVariable($kv[0].Trim(), $kv[1].Trim(' ', '"', "'"), 'Process') }
    }
  }
}
$lexflowPython = if ($env:LEXFLOW_PYTHON) { $env:LEXFLOW_PYTHON } elseif (Get-Command py -ErrorAction SilentlyContinue) { 'py' } else { 'python' }
$lexflowPythonArgs = if ($lexflowPython -eq 'py') { @('-3.12') } else { @() }
$lexflowVersion = & $lexflowPython @lexflowPythonArgs -c 'import sys; print("%s.%s" % sys.version_info[:2])'
if ($LASTEXITCODE -ne 0 -or $lexflowVersion -ne '3.12') { throw 'Use Python 3.12 for this demo. Set LEXFLOW_PYTHON to its executable path.' }
$lexflowEnvDir = if ($env:LEXFLOW_VENV_DIR) { $env:LEXFLOW_VENV_DIR } else { '.venv-demo' }
$lexflowEnvPython = Join-Path $lexflowEnvDir 'Scripts\python.exe'
if (-not (Test-Path $lexflowEnvPython)) {
  & $lexflowPython @lexflowPythonArgs -m venv $lexflowEnvDir
  if ($LASTEXITCODE -ne 0) { throw 'Could not create the demo environment.' }
}
$lexflowEnvVersion = & $lexflowEnvPython -c 'import sys; print("%s.%s" % sys.version_info[:2])'
if ($LASTEXITCODE -ne 0 -or $lexflowEnvVersion -ne '3.12') { throw 'The demo environment uses another Python. Set LEXFLOW_VENV_DIR to a new directory.' }
$lexflowFingerprint = (Get-FileHash requirements.txt -Algorithm SHA256).Hash + (Get-FileHash constraints.txt -Algorithm SHA256).Hash
$lexflowMarker = Join-Path $lexflowEnvDir '.requirements-hash'
$lexflowInstalled = if (Test-Path $lexflowMarker) { (Get-Content $lexflowMarker -Raw).Trim() } else { '' }
if ($lexflowInstalled -ne $lexflowFingerprint) {
  & $lexflowEnvPython -m pip install --disable-pip-version-check -r requirements.txt
  if ($LASTEXITCODE -ne 0) { throw 'Could not install demo dependencies.' }
  Set-Content $lexflowMarker $lexflowFingerprint -NoNewline
}
$lexflowPort = if ($env:LEXFLOW_PORT) { $env:LEXFLOW_PORT } else { '8000' }
Write-Host "[LexFlow] Visit http://127.0.0.1:$lexflowPort — use synthetic documents only."
& $lexflowEnvPython -m uvicorn lexflow.main:app --host 127.0.0.1 --port $lexflowPort
