param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]] $IdfArgs
)

$ErrorActionPreference = 'Stop'

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$EspIdfPath = 'E:\project\ESP_IDF_support\v5.3.2\esp-idf'
$ToolsPath = 'E:\project\ESP_IDF_support\tools'
$PythonEnvPath = 'E:\project\ESP_IDF_support\tools\python_env\idf5.3_py3.14_env'

if ($IdfArgs.Count -eq 0) {
    $IdfArgs = @('build')
}

$ExportScript = Join-Path $EspIdfPath 'export.ps1'
if (-not (Test-Path -LiteralPath $ExportScript)) {
    throw "ESP-IDF export script not found: $ExportScript"
}
if (-not (Test-Path -LiteralPath $ToolsPath)) {
    throw "ESP-IDF tools path not found: $ToolsPath"
}
if (-not (Test-Path -LiteralPath $PythonEnvPath)) {
    throw "ESP-IDF Python environment not found: $PythonEnvPath"
}

$env:IDF_PATH = $EspIdfPath
$env:IDF_TOOLS_PATH = $ToolsPath
$env:IDF_PYTHON_ENV_PATH = $PythonEnvPath

Push-Location $ProjectRoot
try {
    & $ExportScript
    if ($LASTEXITCODE -ne 0) {
        throw "ESP-IDF export failed with exit code $LASTEXITCODE"
    }

    & idf.py @IdfArgs
    if ($LASTEXITCODE -ne 0) {
        throw "idf.py $($IdfArgs -join ' ') failed with exit code $LASTEXITCODE"
    }
}
finally {
    Pop-Location
}
