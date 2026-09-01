param(
    [string]$Repo = ".\demo\sample_project",
    [ValidateSet("mock", "rules", "api")]
    [string]$Mode = "mock",
    [string]$Question = "请全面评审这个项目，重点关注安全性、可维护性和架构问题"
)

$ErrorActionPreference = "Stop"
$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
    $python = "python"
}
& $python -m ai_reviewer.demo --repo $Repo --mode $Mode --question $Question --output-dir ".\demo\output"
