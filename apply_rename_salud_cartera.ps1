# apply_rename_salud_cartera.ps1
# Renombra "Salud del agente" a "Salud de la Cartera"
# en 5 archivos (7 apariciones totales).

$ErrorActionPreference = "Stop"

$root      = "C:\Users\manue\Downloads\senties-demo"
$timestamp = Get-Date -Format "yyyyMMdd-HHmm"

$OLD = "Salud del agente"
$NEW = "Salud de la Cartera"

$targets = @(
    @{ path = "$root\app\services\chat.py";               expected = 1 },
    @{ path = "$root\app\services\queries.py";            expected = 1 },
    @{ path = "$root\app\templates\base.html";            expected = 1 },
    @{ path = "$root\app\templates\dashboard_hub.html";   expected = 1 },
    @{ path = "$root\app\templates\dashboard_salud.html"; expected = 3 }
)

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  RENAME: Salud del agente -> Salud de la Cartera" -ForegroundColor Cyan
Write-Host "  Timestamp: $timestamp" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# PASO 1: Verificar archivos
Write-Host "[1/5] Verificando archivos..." -ForegroundColor Yellow

$anyMissing = $false
foreach ($t in $targets) {
    if (Test-Path $t.path) {
        Write-Host "  OK  $($t.path)" -ForegroundColor Green
    } else {
        Write-Host "  NO  $($t.path)" -ForegroundColor Red
        $anyMissing = $true
    }
}

if ($anyMissing) {
    Write-Host ""
    Write-Host "ERROR: Faltan archivos. Aborto." -ForegroundColor Red
    exit 1
}

# PASO 2: Backups
Write-Host ""
Write-Host "[2/5] Creando backups..." -ForegroundColor Yellow

foreach ($t in $targets) {
    $bak = "$($t.path).bak.$timestamp"
    Copy-Item $t.path $bak -Force
    Write-Host "  OK  $bak" -ForegroundColor Green
}

# PASO 3: Reemplazos
Write-Host ""
Write-Host "[3/5] Aplicando reemplazos..." -ForegroundColor Yellow

$totalReplaced = 0
$errors = 0

foreach ($t in $targets) {
    $content = Get-Content -Path $t.path -Raw -Encoding UTF8
    $countBefore = ([regex]::Matches($content, [regex]::Escape($OLD))).Count

    if ($countBefore -eq 0) {
        Write-Host "  WARN: $($t.path) - 0 apariciones" -ForegroundColor Yellow
        continue
    }

    if ($countBefore -ne $t.expected) {
        Write-Host "  WARN: $($t.path) - $countBefore apariciones (esperaba $($t.expected))" -ForegroundColor Yellow
    }

    $newContent = $content -replace [regex]::Escape($OLD), $NEW
    $countAfter = ([regex]::Matches($newContent, [regex]::Escape($OLD))).Count

    if ($countAfter -ne 0) {
        Write-Host "  ERROR: $($t.path) - quedan $countAfter apariciones" -ForegroundColor Red
        $errors++
        continue
    }

    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($t.path, $newContent, $utf8NoBom)

    $fname = Split-Path $t.path -Leaf
    Write-Host "  OK  $fname - $countBefore reemplazos" -ForegroundColor Green
    $totalReplaced += $countBefore
}

if ($errors -gt 0) {
    Write-Host ""
    Write-Host "ERROR: $errors archivos fallaron. Revirtiendo..." -ForegroundColor Red
    foreach ($t in $targets) {
        $bak = "$($t.path).bak.$timestamp"
        if (Test-Path $bak) { Copy-Item $bak $t.path -Force }
    }
    exit 1
}

Write-Host ""
Write-Host "  Total: $totalReplaced reemplazos" -ForegroundColor Cyan

# PASO 4: py_compile
Write-Host ""
Write-Host "[4/5] Validando sintaxis Python..." -ForegroundColor Yellow

Push-Location $root
try {
    python -m py_compile app\services\chat.py
    Write-Host "  OK  chat.py compila" -ForegroundColor Green
    python -m py_compile app\services\queries.py
    Write-Host "  OK  queries.py compila" -ForegroundColor Green
} catch {
    Write-Host "  ERROR de compilacion. Revirtiendo..." -ForegroundColor Red
    foreach ($t in $targets) {
        $bak = "$($t.path).bak.$timestamp"
        if (Test-Path $bak) { Copy-Item $bak $t.path -Force }
    }
    Pop-Location
    exit 1
}
Pop-Location

# PASO 5: Verificacion final
Write-Host ""
Write-Host "[5/5] Verificando resultado..." -ForegroundColor Yellow

$oldMatches = Get-ChildItem "$root\app" -Recurse -Include *.html,*.py -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -notmatch "\.bak\." } |
    Select-String -Pattern "Salud del agente" -SimpleMatch

if ($oldMatches) {
    $c = ($oldMatches | Measure-Object).Count
    Write-Host "  WARN: aun hay $c apariciones del texto viejo" -ForegroundColor Yellow
} else {
    Write-Host "  OK  Ninguna aparicion de texto viejo" -ForegroundColor Green
}

$newMatches = Get-ChildItem "$root\app" -Recurse -Include *.html,*.py -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -notmatch "\.bak\." } |
    Select-String -Pattern "Salud de la Cartera" -SimpleMatch

$newCount = ($newMatches | Measure-Object).Count
Write-Host "  OK  $newCount apariciones del texto nuevo" -ForegroundColor Green

# Cierre
Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  RENAME APLICADO" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Siguiente paso - probar local:" -ForegroundColor White
Write-Host "  cd $root" -ForegroundColor Gray
Write-Host "  python -m uvicorn app.main:app --reload --port 8000" -ForegroundColor Gray
Write-Host ""
Write-Host "Si local se ve bien, deploy a Railway:" -ForegroundColor White
Write-Host "  git add -A" -ForegroundColor Gray
Write-Host "  git commit -m 'rename Salud del agente to Salud de la Cartera'" -ForegroundColor Gray
Write-Host "  git push origin main" -ForegroundColor Gray
Write-Host "  railway up" -ForegroundColor Gray
Write-Host ""
