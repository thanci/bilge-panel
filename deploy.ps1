# ================================================================
#  Bilge Yolcu — Auto-Deploy v1
#  Cift tikla veya PowerShell'de calistir: .\deploy.ps1
# ================================================================
Set-Location "C:\Users\EXCALIBUR\bilge-panel"

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Bilge Yolcu Auto-Deploy" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 1) Degisiklik var mi kontrol et
$env:GIT_REDIRECT_STDERR = '2>&1'
$status = git status --porcelain 2>$null
$unpushed = git log deploy/main..HEAD --oneline 2>$null
if ([string]::IsNullOrWhiteSpace($status) -and [string]::IsNullOrWhiteSpace($unpushed)) {
    Write-Host "Degisiklik yok, deploy edilecek bir sey bulunamadi." -ForegroundColor Yellow
    Read-Host "Cikis icin Enter'a basin"
    exit 0
}

# 2) Mevcut versiyonu bul (health.py icinden)
$healthFile = "backend\app\routes\health.py"
$healthContent = Get-Content $healthFile -Raw
if ($healthContent -match '"version":\s*"(\d+)\.(\d+)\.(\d+)"') {
    $major = [int]$Matches[1]
    $minor = [int]$Matches[2]
    $patch = [int]$Matches[3]
    $oldVer = "$major.$minor.$patch"
} else {
    Write-Host "HATA: Versiyon bulunamadi!" -ForegroundColor Red
    Read-Host "Cikis icin Enter'a basin"
    exit 1
}

# 3) Patch numarasini artir
$patch++
$newVer = "$major.$minor.$patch"
Write-Host "[1/5] Versiyon: $oldVer -> $newVer" -ForegroundColor Yellow

# 4) health.py icindeki versiyonu guncelle
$healthContent = $healthContent.Replace("`"version`":   `"$oldVer`"", "`"version`":   `"$newVer`"")
Set-Content -Path $healthFile -Value $healthContent -NoNewline
Write-Host "[2/5] health.py guncellendi" -ForegroundColor Green

# 5) Git add + commit
$ErrorActionPreference = "SilentlyContinue"
$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm"
$commitMsg = "v$newVer deploy ($timestamp)"

Write-Host "[3/5] Commit: $commitMsg" -ForegroundColor Yellow
git add -A 2>$null
git commit -m $commitMsg 2>$null

# 6) GitHub'a push (yedekleme)
$ErrorActionPreference = "Continue"
Write-Host "[4/5] GitHub'a yedekleniyor..." -ForegroundColor Yellow
git push origin main 2>$null

# 7) Sunucuya deploy push
Write-Host "[5/5] Sunucuya deploy ediliyor..." -ForegroundColor Yellow
Write-Host ""
git push deploy main

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "  DEPLOY BASARILI!  v$newVer" -ForegroundColor Green
    Write-Host "  bilgeyolcu.com/yonetim  (CTRL+F5)" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Red
    Write-Host "  HATA: Deploy basarisiz!" -ForegroundColor Red
    Write-Host "========================================" -ForegroundColor Red
}

Write-Host ""
Read-Host "Cikis icin Enter'a basin"
