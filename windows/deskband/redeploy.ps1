$ErrorActionPreference = 'Stop'

# Explorer keeps the DeskBand DLL mapped for as long as it runs, and it never
# unloads it, so a rebuilt DLL only reaches the taskbar through a shell
# restart. Hiding the band first keeps the fresh Explorer from instantiating
# the old file again before it can be replaced.

$bandRoot = $PSScriptRoot
$built = Join-Path $bandRoot 'target\release\quotabar_deskband.dll'
$live = Join-Path $bandRoot 'dist\quotabar_deskband.dll'
$controller = Join-Path $bandRoot 'dist\deskbandctl.exe'

if (-not (Test-Path -LiteralPath $built)) {
    throw "No built DLL at $built - run: cargo build --manifest-path .\windows\deskband\Cargo.toml --release --lib"
}
if (-not (Test-Path -LiteralPath $controller)) { throw "DeskBand controller not found: $controller" }

& $controller --hide | Out-Null
Stop-Process -Name explorer -Force

# Windows restarts the shell by itself; wait for the old process to let go.
$copied = $false
$deadline = (Get-Date).AddSeconds(20)
while (-not $copied -and (Get-Date) -lt $deadline) {
    try {
        Copy-Item -LiteralPath $built -Destination $live -Force
        $copied = $true
    } catch {
        Start-Sleep -Milliseconds 300
    }
}
if (-not $copied) { throw "Could not replace $live - is Explorer still holding it?" }

if (-not (Get-Process explorer -ErrorAction SilentlyContinue)) { Start-Process explorer.exe }
Start-Sleep -Seconds 6
& $controller | Out-Null

Start-Sleep -Seconds 3
$host_present = (& (Join-Path $bandRoot 'target\release\inspecthost.exe')) -match 'QuotaBarDeskBandHost'
if ($host_present) {
    Write-Output 'QuotaBar DeskBand is live with the rebuilt DLL.'
} else {
    Write-Output 'DLL replaced, but Explorer has not shown the band yet.'
    Write-Output 'Add it back through: right-click the taskbar -> Toolbars -> QuotaBar.'
}
