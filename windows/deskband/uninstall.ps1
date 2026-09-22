$ErrorActionPreference = 'Stop'

$clsid = '{09ABC829-93CA-47C4-8B4C-D15E6505F92C}'
$project = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$controller = Join-Path $project 'windows\deskband\dist\deskbandctl.exe'
$profile = (Resolve-Path (Join-Path $env:SystemDrive 'Users\fujitsu')).Path
$profileEntry = Get-ChildItem 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\ProfileList' |
    Where-Object { (Get-ItemProperty $_.PSPath).ProfileImagePath -eq $profile } |
    Select-Object -First 1
if (-not $profileEntry) { throw "Could not resolve the Windows profile SID for $profile" }
$userHive = "Registry::HKEY_USERS\$($profileEntry.PSChildName)"
$classKey = "$userHive\Software\Classes\CLSID\$clsid"
$approvedKey = "$userHive\Software\Microsoft\Windows\CurrentVersion\Shell Extensions\Approved"

if (Test-Path -LiteralPath $controller) { & $controller --hide }
if (Test-Path -LiteralPath $classKey) { Remove-Item -LiteralPath $classKey -Recurse -Force }
if (Test-Path -LiteralPath $approvedKey) {
    Remove-ItemProperty -LiteralPath $approvedKey -Name $clsid -ErrorAction SilentlyContinue
}
Write-Output 'QuotaBar DeskBand removed.'
