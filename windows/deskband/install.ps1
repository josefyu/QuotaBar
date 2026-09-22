$ErrorActionPreference = 'Stop'

$clsid = '{09ABC829-93CA-47C4-8B4C-D15E6505F92C}'
$category = '{00021492-0000-0000-C000-000000000046}'
$project = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$bandRoot = Join-Path $project 'windows\deskband'
$dll = Join-Path $bandRoot 'dist\quotabar_deskband.dll'
$controller = Join-Path $bandRoot 'dist\deskbandctl.exe'

if (-not (Test-Path -LiteralPath $dll)) { throw "DeskBand DLL not found: $dll" }
if (-not (Test-Path -LiteralPath $controller)) { throw "DeskBand controller not found: $controller" }

$profile = (Resolve-Path (Join-Path $env:SystemDrive 'Users\fujitsu')).Path
$profileEntry = Get-ChildItem 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\ProfileList' |
    Where-Object { (Get-ItemProperty $_.PSPath).ProfileImagePath -eq $profile } |
    Select-Object -First 1
if (-not $profileEntry) { throw "Could not resolve the Windows profile SID for $profile" }
$userHive = "Registry::HKEY_USERS\$($profileEntry.PSChildName)"
$classKey = "$userHive\Software\Classes\CLSID\$clsid"
$serverKey = Join-Path $classKey 'InprocServer32'
$categoryKey = Join-Path $classKey "Implemented Categories\$category"
$approvedKey = "$userHive\Software\Microsoft\Windows\CurrentVersion\Shell Extensions\Approved"

New-Item -Path $serverKey -Force | Out-Null
New-Item -Path $categoryKey -Force | Out-Null
New-Item -Path $approvedKey -Force | Out-Null
Set-Item -LiteralPath $classKey -Value 'QuotaBar' -Force
Set-Item -LiteralPath $serverKey -Value $dll -Force
New-ItemProperty -LiteralPath $serverKey -Name 'ThreadingModel' -Value 'Apartment' -PropertyType String -Force | Out-Null
New-ItemProperty -LiteralPath $approvedKey -Name $clsid -Value 'QuotaBar' -PropertyType String -Force | Out-Null

& $controller
if ($LASTEXITCODE -ne 0) { throw "Explorer could not show the QuotaBar DeskBand (exit $LASTEXITCODE)." }

Write-Output 'QuotaBar DeskBand registered and shown.'
