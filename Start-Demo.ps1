$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$taskPython = Get-Command python -ErrorAction SilentlyContinue
if ($taskPython) { $taskPythonPath = $taskPython.Source }
else { $taskPythonPath = 'C:\Users\jyagi\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' }
if (-not (Test-Path -LiteralPath $taskPythonPath)) { throw 'Python 3.11以上が必要です。READMEを確認してください。' }
$taskSecret = Read-Host '管理パスワード（16文字以上。同じ値でブラウザにログイン）' -AsSecureString
$taskPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($taskSecret)
try { $env:MDB_ADMIN_PASSWORD = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($taskPointer) }
finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($taskPointer) }
if ($env:MDB_ADMIN_PASSWORD.Length -lt 16) { Remove-Item Env:MDB_ADMIN_PASSWORD; throw '16文字以上で再実行してください。' }
$env:MDB_DEMO = '1'
$env:MDB_ORIGIN = 'http://127.0.0.1:8000'
Remove-Item Env:MDB_DEMO_DB -ErrorAction SilentlyContinue
try {
    & $taskPythonPath -m app.main demo
    if ($LASTEXITCODE -ne 0) { throw 'デモ生成に失敗しました。' }
    Write-Host 'ブラウザで http://127.0.0.1:8000 を開いてください。終了は Ctrl+C。'
    & $taskPythonPath -m app.main serve
    if ($LASTEXITCODE -ne 0) { throw '起動に失敗しました。8000番で以前のサーバーが動いていないか確認してください。' }
}
finally { Remove-Item Env:MDB_ADMIN_PASSWORD -ErrorAction SilentlyContinue }
