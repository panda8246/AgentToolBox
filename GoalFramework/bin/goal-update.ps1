[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$OutputEncoding = [Console]::OutputEncoding
$env:PYTHONUTF8 = '1'
$script = Join-Path $PSScriptRoot 'goal-update.py'
$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) { $python = Get-Command py -ErrorAction SilentlyContinue }
if (-not $python) { throw '未找到 Python。请安装 Python 3.10+ 后重试。' }

Write-Host ''
Write-Host 'Goal Framework 更新'
Write-Host "项目目录：$(Get-Location)"
Write-Host '将先显示跨版本变更说明，再由你确认是否应用。'
Read-Host '按回车继续，输入 0 取消' | ForEach-Object { if ($_ -eq '0') { exit 0 } }
if ($python.Name -eq 'py.exe') { & $python.Source -3 $script } else { & $python.Source $script }
exit $LASTEXITCODE
