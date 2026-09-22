use windows::core::BOOL;
use windows::Win32::Foundation::{HWND, LPARAM, RECT};
use windows::Win32::UI::WindowsAndMessaging::{EnumChildWindows, EnumWindows, GetClassNameW, GetWindowRect};

unsafe extern "system" fn child_proc(hwnd: HWND, _param: LPARAM) -> BOOL {
    let mut name = [0u16; 256];
    let len = unsafe { GetClassNameW(hwnd, &mut name) };
    if len > 0 {
        let class = String::from_utf16_lossy(&name[..len as usize]);
        if class.contains("QuotaBar") || class.contains("ClaudeCodeUsageMonitor") || class == "MSTaskListWClass" || class == "TrayNotifyWnd" {
            let mut rect = RECT::default();
            let _ = unsafe { GetWindowRect(hwnd, &mut rect) };
            println!("{class}: {},{}-{},{}", rect.left, rect.top, rect.right, rect.bottom);
        }
    }
    BOOL(1)
}

unsafe extern "system" fn top_proc(hwnd: HWND, _param: LPARAM) -> BOOL {
    let mut name = [0u16; 128];
    let len = unsafe { GetClassNameW(hwnd, &mut name) };
    if len > 0 {
        let class = String::from_utf16_lossy(&name[..len as usize]);
        if class == "Shell_TrayWnd" || class == "Shell_SecondaryTrayWnd" {
            let mut rect = RECT::default();
            let _ = unsafe { GetWindowRect(hwnd, &mut rect) };
            println!("TASKBAR {class}: {},{}-{},{}", rect.left, rect.top, rect.right, rect.bottom);
            let _ = unsafe { EnumChildWindows(Some(hwnd), Some(child_proc), LPARAM(0)) };
        }
    }
    BOOL(1)
}

fn main() {
    unsafe { let _ = EnumWindows(Some(top_proc), LPARAM(0)); }
}
