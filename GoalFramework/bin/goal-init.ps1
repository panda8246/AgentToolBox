[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$OutputEncoding = [Console]::OutputEncoding
$env:PYTHONUTF8 = '1'
$script = Join-Path $PSScriptRoot 'goal-init.py'
$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) { $python = Get-Command py -ErrorAction SilentlyContinue }
if (-not $python) { throw '未找到 Python。请安装 Python 3.10+ 后重试。' }

Write-Host ''
Write-Host 'Goal Framework 初始化'
Write-Host "项目目录：$(Get-Location)"
Write-Host '请选择要使用的 Agent：'
Write-Host '  1. 自动检测（推荐）'
Write-Host '  2. Codex'
Write-Host '  3. Cursor'
Write-Host '  4. OpenCode'
Write-Host '  5. 只创建框架，稍后自行让 Agent 填写'
Write-Host '  0. 取消'

$selection = Read-Host '输入数字'
$arguments = switch ($selection) {
    '1' { @('--agent', 'auto') }
    '2' { @('--agent', 'codex') }
    '3' { @('--agent', 'cursor') }
    '4' { @('--agent', 'opencode') }
    '5' { @('--agent', 'manual', '--skip-native-init', '--no-agent-prompt') }
    '0' { Write-Host '已取消。'; exit 0 }
    default { Write-Host '无效选择，未执行任何操作。'; exit 1 }
}

if ($python.Name -eq 'py.exe') {
    & $python.Source -3 $script @arguments
} else {
    & $python.Source $script @arguments
}
exit $LASTEXITCODE


