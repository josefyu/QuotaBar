# QuotaBar Windows 10 DeskBand

This in-process COM DeskBand gives QuotaBar a shell-reserved taskbar area. The
main QuotaBar process continues to render the selected theme and attaches its
surface to the `QuotaBarDeskBandHost` window.

Build both components:

```powershell
cargo build --release
cargo build --manifest-path .\windows\deskband\Cargo.toml --release
```

Copy `quotabar_deskband.dll` and `deskbandctl.exe` into the local `dist`
directory before installing. The installed COM registration points there so a
normal Cargo clean does not invalidate the live DeskBand.

Register and show the band for the current Windows user:

```powershell
.\windows\deskband\install.ps1
```

Remove it with `uninstall.ps1`. DeskBands are supported by the classic Windows
10 taskbar, not the redesigned Windows 11 taskbar.
