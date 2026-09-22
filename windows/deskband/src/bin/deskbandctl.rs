use windows::core::{GUID, Result};
use windows::Win32::System::Com::{CoCreateInstance, CoInitializeEx, CoUninitialize, CLSCTX_LOCAL_SERVER, COINIT_APARTMENTTHREADED};
use windows::Win32::UI::Shell::{ITrayDeskBand, TrayDeskBand};

const CLSID_QUOTABAR_DESKBAND: GUID = GUID::from_u128(0x09abc829_93ca_47c4_8b4c_d15e6505f92c);

fn main() -> Result<()> {
    unsafe {
        CoInitializeEx(None, COINIT_APARTMENTTHREADED).ok()?;
        let tray: ITrayDeskBand = CoCreateInstance(&TrayDeskBand, None, CLSCTX_LOCAL_SERVER)?;
        tray.DeskBandRegistrationChanged()?;
        if std::env::args().any(|arg| arg == "--status") {
            let shown = tray.IsDeskBandShown(&CLSID_QUOTABAR_DESKBAND);
            println!("IsDeskBandShown: {shown:?}");
            drop(tray);
            CoUninitialize();
            return Ok(());
        }
        let hide = std::env::args().any(|arg| arg == "--hide");
        let result = if hide { tray.HideDeskBand(&CLSID_QUOTABAR_DESKBAND) } else { tray.ShowDeskBand(&CLSID_QUOTABAR_DESKBAND) };
        drop(tray);
        CoUninitialize();
        result
    }
}
