$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    python -m pip install -r requirements-build.txt
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
    python -m unittest discover -s tests -v
    if ($LASTEXITCODE -ne 0) { throw 'Tests failed.' }
    $taskIcon = Join-Path $PSScriptRoot 'assets\app.ico'
    $taskTarget = Join-Path $PSScriptRoot 'assets\default_target.png'
    python -m PyInstaller --noconfirm --clean --onefile --windowed --name '讲解石生成器' --icon $taskIcon --add-data "$taskIcon;assets" --add-data "$taskTarget;assets" --distpath . --workpath build/work --specpath build app.py
    if ($LASTEXITCODE -ne 0) { throw 'Executable build failed.' }
    Write-Host 'Build complete.'
} finally {
    Pop-Location
}
