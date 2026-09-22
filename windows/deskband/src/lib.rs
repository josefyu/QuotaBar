#![allow(non_snake_case)]

use std::ffi::c_void;
use std::sync::atomic::{AtomicU32, Ordering};
use std::sync::Mutex;

use windows::core::{implement, Error, Interface, Ref, Result, BOOL, GUID, HRESULT, IUnknown, PCWSTR};
use windows::Win32::Foundation::{COLORREF, CLASS_E_CLASSNOTAVAILABLE, CLASS_E_NOAGGREGATION, E_NOINTERFACE, E_POINTER, HWND, LPARAM, LRESULT, POINTL, RECT, S_FALSE, WPARAM};
use windows::Win32::Graphics::Gdi::{
    CreateSolidBrush, DeleteObject, FillRect, InvalidateRect, HBRUSH, HDC,
};
use windows::Win32::System::Com::{IClassFactory, IClassFactory_Impl, IPersistStream, IPersistStream_Impl, IPersist_Impl, IStream};
use windows::Win32::System::LibraryLoader::GetModuleHandleW;
use windows::Win32::System::Registry::{RegGetValueW, HKEY_CURRENT_USER, RRF_RT_REG_DWORD};
use windows::Win32::System::Ole::{IObjectWithSite, IObjectWithSite_Impl, IOleWindow_Impl};
use windows::Win32::UI::Shell::{DESKBANDINFO, DBIM_ACTUAL, DBIM_INTEGRAL, DBIM_MAXSIZE, DBIM_MINSIZE, DBIM_MODEFLAGS, DBIM_TITLE, IDeskBand, IDeskBand_Impl, IDockingWindow_Impl, IInputObject, IInputObject_Impl};
use windows::Win32::UI::WindowsAndMessaging::{
    CreateWindowExW, DefWindowProcW, DestroyWindow, GetClientRect, RegisterClassW, ShowWindow,
    CS_HREDRAW, CS_VREDRAW, MSG, SW_HIDE, SW_SHOWNOACTIVATE, WINDOW_EX_STYLE, WM_ERASEBKGND,
    WM_SETTINGCHANGE, WM_THEMECHANGED, WNDCLASSW, WS_CHILD, WS_CLIPCHILDREN, WS_CLIPSIBLINGS,
    WS_VISIBLE,
};

pub const CLSID_QUOTABAR_DESKBAND: GUID = GUID::from_u128(0x09abc829_93ca_47c4_8b4c_d15e6505f92c);
const HOST_CLASS: PCWSTR = windows::core::w!("QuotaBarDeskBandHost");

#[derive(Default)]
struct BandState {
    site: Option<IUnknown>,
    hwnd: isize,
}

#[implement(IDeskBand, IObjectWithSite, IPersistStream, IInputObject)]
struct QuotaBarDeskBand {
    state: Mutex<BandState>,
}

impl QuotaBarDeskBand {
    fn new() -> Self {
        Self { state: Mutex::new(BandState::default()) }
    }

    fn destroy_window(&self) {
        let hwnd = {
            let mut state = self.state.lock().unwrap();
            let hwnd = state.hwnd;
            state.hwnd = 0;
            hwnd
        };
        if hwnd != 0 {
            unsafe { let _ = DestroyWindow(HWND(hwnd as *mut c_void)); }
        }
    }
}

impl Drop for QuotaBarDeskBand {
    fn drop(&mut self) {
        self.destroy_window();
    }
}

impl IOleWindow_Impl for QuotaBarDeskBand_Impl {
    fn GetWindow(&self) -> Result<HWND> {
        let hwnd = self.state.lock().unwrap().hwnd;
        if hwnd == 0 { Err(Error::from(E_FAIL)) } else { Ok(HWND(hwnd as *mut c_void)) }
    }

    fn ContextSensitiveHelp(&self, _fenter: BOOL) -> Result<()> { Ok(()) }
}

impl IDockingWindow_Impl for QuotaBarDeskBand_Impl {
    fn ShowDW(&self, fshow: BOOL) -> Result<()> {
        let hwnd = self.state.lock().unwrap().hwnd;
        if hwnd != 0 {
            unsafe { let _ = ShowWindow(HWND(hwnd as *mut c_void), if fshow.as_bool() { SW_SHOWNOACTIVATE } else { SW_HIDE }); }
        }
        Ok(())
    }

    fn CloseDW(&self, _reserved: u32) -> Result<()> { self.destroy_window(); Ok(()) }
    fn ResizeBorderDW(&self, _border: *const RECT, _site: Ref<IUnknown>, _reserved: BOOL) -> Result<()> { Ok(()) }
}

impl IDeskBand_Impl for QuotaBarDeskBand_Impl {
    fn GetBandInfo(&self, _id: u32, _view_mode: u32, info: *mut DESKBANDINFO) -> Result<()> {
        if info.is_null() { return Err(Error::from(E_POINTER)); }
        unsafe {
            let info = &mut *info;
            if info.dwMask & DBIM_MINSIZE != 0 { info.ptMinSize = POINTL { x: 285, y: 40 }; }
            if info.dwMask & DBIM_MAXSIZE != 0 { info.ptMaxSize = POINTL { x: 285, y: -1 }; }
            if info.dwMask & DBIM_INTEGRAL != 0 { info.ptIntegral = POINTL { x: 1, y: 1 }; }
            if info.dwMask & DBIM_ACTUAL != 0 { info.ptActual = POINTL { x: 285, y: 40 }; }
            if info.dwMask & DBIM_TITLE != 0 {
                // Explorer lays out the gripper together with the title, and
                // an empty title collapsed both - leaving no handle to drag
                // the band by.
                let title = windows::core::w!("QuotaBar");
                let mut index = 0;
                while index < info.wszTitle.len() - 1 {
                    let character = *title.as_ptr().add(index);
                    info.wszTitle[index] = character;
                    if character == 0 {
                        break;
                    }
                    index += 1;
                }
                info.wszTitle[info.wszTitle.len() - 1] = 0;
            }
            // A gripper is what lets the user slide the band left and right
            // along the taskbar, so the band must not be fixed, and it must
            // keep the margin the gripper is drawn in. The width stays pinned
            // through ptMinSize/ptMaxSize above.
            if info.dwMask & DBIM_MODEFLAGS != 0 { info.dwModeFlags = 0; }
        }
        Ok(())
    }
}

impl IObjectWithSite_Impl for QuotaBarDeskBand_Impl {
    fn SetSite(&self, site: Ref<IUnknown>) -> Result<()> {
        self.destroy_window();
        let Some(site) = site.cloned() else {
            self.state.lock().unwrap().site = None;
            return Ok(());
        };
        let ole: windows::Win32::System::Ole::IOleWindow = site.cast()?;
        let parent = unsafe { ole.GetWindow()? };
        let module = unsafe { GetModuleHandleW(None)? };
        let class = WNDCLASSW {
            style: CS_HREDRAW | CS_VREDRAW,
            lpfnWndProc: Some(host_wnd_proc),
            hInstance: module.into(),
            hbrBackground: HBRUSH::default(),
            lpszClassName: HOST_CLASS,
            ..Default::default()
        };
        unsafe { let _ = RegisterClassW(&class); }
        let hwnd = unsafe {
            CreateWindowExW(
                WINDOW_EX_STYLE::default(), HOST_CLASS, windows::core::w!("QuotaBar"),
                WS_CHILD | WS_VISIBLE | WS_CLIPSIBLINGS | WS_CLIPCHILDREN,
                0, 0, 285, 40, Some(parent), None, Some(module.into()), None,
            )?
        };
        let mut state = self.state.lock().unwrap();
        state.site = Some(site);
        state.hwnd = hwnd.0 as isize;
        Ok(())
    }

    fn GetSite(&self, riid: *const GUID, ppv: *mut *mut c_void) -> Result<()> {
        if riid.is_null() || ppv.is_null() { return Err(Error::from(E_POINTER)); }
        unsafe { *ppv = std::ptr::null_mut(); }
        let state = self.state.lock().unwrap();
        let Some(site) = state.site.as_ref() else { return Err(Error::from(E_NOINTERFACE)); };
        unsafe { site.query(riid, ppv).ok() }
    }
}

impl IPersist_Impl for QuotaBarDeskBand_Impl {
    fn GetClassID(&self) -> Result<GUID> { Ok(CLSID_QUOTABAR_DESKBAND) }
}

impl IPersistStream_Impl for QuotaBarDeskBand_Impl {
    fn IsDirty(&self) -> HRESULT { S_FALSE }
    fn Load(&self, _stream: Ref<IStream>) -> Result<()> { Ok(()) }
    fn Save(&self, _stream: Ref<IStream>, _clear_dirty: BOOL) -> Result<()> { Ok(()) }
    fn GetSizeMax(&self) -> Result<u64> { Ok(0) }
}

impl IInputObject_Impl for QuotaBarDeskBand_Impl {
    fn UIActivateIO(&self, _activate: BOOL, _message: *const MSG) -> Result<()> { Ok(()) }
    fn HasFocusIO(&self) -> Result<()> { Err(Error::from(S_FALSE)) }
    fn TranslateAcceleratorIO(&self, _message: *const MSG) -> Result<()> { Err(Error::from(S_FALSE)) }
}

/// The band sits inside the taskbar, so it has to carry the taskbar's own
/// backdrop. Painting the classic 3D face colour instead put a light plate
/// behind a widget whose colours follow the Windows mode, which made dark-mode
/// text and progress fills disappear.
const WM_DWMCOLORIZATIONCOLORCHANGED: u32 = 0x0320;
const PERSONALIZE_KEY: PCWSTR =
    windows::core::w!(r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize");
const DWM_KEY: PCWSTR = windows::core::w!(r"Software\Microsoft\Windows\DWM");
const BACKDROP_UNRESOLVED: u32 = u32::MAX;

static BACKDROP: AtomicU32 = AtomicU32::new(BACKDROP_UNRESOLVED);

fn registry_dword(key: PCWSTR, value: PCWSTR) -> Option<u32> {
    let mut data = 0u32;
    let mut size = std::mem::size_of::<u32>() as u32;
    let status = unsafe {
        RegGetValueW(
            HKEY_CURRENT_USER,
            key,
            value,
            RRF_RT_REG_DWORD,
            None,
            Some(&mut data as *mut u32 as *mut c_void),
            Some(&mut size),
        )
    };
    status.is_ok().then_some(data)
}

fn resolve_backdrop() -> COLORREF {
    // Accent-coloured taskbars win over the plain dark/light shades.
    if registry_dword(PERSONALIZE_KEY, windows::core::w!("ColorPrevalence")) == Some(1) {
        if let Some(accent) = registry_dword(DWM_KEY, windows::core::w!("AccentColor")) {
            // Stored as 0xAABBGGRR, and COLORREF is the same 0x00BBGGRR layout.
            return COLORREF(accent & 0x00FF_FFFF);
        }
    }
    // The taskbar follows "Windows mode", not the separate app mode.
    let light = registry_dword(PERSONALIZE_KEY, windows::core::w!("SystemUsesLightTheme")) == Some(1);
    if light {
        COLORREF(0x00F3_F3F3)
    } else {
        COLORREF(0x001C_1C1C)
    }
}

/// What the band paints to clear its area.
///
/// A translucent taskbar is composited from a surface with premultiplied
/// alpha, and GDI leaves that alpha at zero, so whatever is filled here is
/// *added* to the blurred backdrop: a solid taskbar colour came out twice as
/// light as its surroundings. Black adds nothing, which clears stale pixels
/// while leaving the blur intact. An opaque taskbar does no such blending, so
/// there the band has to carry the taskbar colour itself.
fn erase_colour() -> COLORREF {
    if registry_dword(PERSONALIZE_KEY, windows::core::w!("EnableTransparency")) != Some(0) {
        return COLORREF(0);
    }
    backdrop()
}

fn backdrop() -> COLORREF {
    let cached = BACKDROP.load(Ordering::Relaxed);
    if cached != BACKDROP_UNRESOLVED {
        return COLORREF(cached);
    }
    let resolved = resolve_backdrop();
    BACKDROP.store(resolved.0, Ordering::Relaxed);
    resolved
}

unsafe extern "system" fn host_wnd_proc(hwnd: HWND, msg: u32, wparam: WPARAM, lparam: LPARAM) -> LRESULT {
    match msg {
        WM_ERASEBKGND => {
            let hdc = HDC(wparam.0 as *mut c_void);
            let mut client = RECT::default();
            unsafe {
                if GetClientRect(hwnd, &mut client).is_ok() {
                    let brush = CreateSolidBrush(erase_colour());
                    if !brush.is_invalid() {
                        FillRect(hdc, &client, brush);
                        let _ = DeleteObject(brush.into());
                    }
                }
            }
            LRESULT(1)
        }
        WM_SETTINGCHANGE | WM_THEMECHANGED | WM_DWMCOLORIZATIONCOLORCHANGED => {
            BACKDROP.store(BACKDROP_UNRESOLVED, Ordering::Relaxed);
            unsafe {
                let _ = InvalidateRect(Some(hwnd), None, true);
                DefWindowProcW(hwnd, msg, wparam, lparam)
            }
        }
        _ => unsafe { DefWindowProcW(hwnd, msg, wparam, lparam) },
    }
}

#[implement(IClassFactory)]
struct ClassFactory;

impl IClassFactory_Impl for ClassFactory_Impl {
    fn CreateInstance(&self, outer: Ref<IUnknown>, riid: *const GUID, object: *mut *mut c_void) -> Result<()> {
        if !outer.is_null() { return Err(Error::from(CLASS_E_NOAGGREGATION)); }
        if riid.is_null() || object.is_null() { return Err(Error::from(E_POINTER)); }
        unsafe { *object = std::ptr::null_mut(); }
        let unknown: IUnknown = QuotaBarDeskBand::new().into();
        unsafe { unknown.query(riid, object).ok() }
    }

    fn LockServer(&self, _lock: BOOL) -> Result<()> { Ok(()) }
}

#[no_mangle]
pub unsafe extern "system" fn DllGetClassObject(clsid: *const GUID, riid: *const GUID, object: *mut *mut c_void) -> HRESULT {
    if clsid.is_null() || riid.is_null() || object.is_null() { return E_POINTER; }
    unsafe { *object = std::ptr::null_mut(); }
    if unsafe { *clsid } != CLSID_QUOTABAR_DESKBAND { return CLASS_E_CLASSNOTAVAILABLE; }
    let factory: IClassFactory = ClassFactory.into();
    unsafe { factory.query(riid, object) }
}

#[no_mangle]
pub extern "system" fn DllCanUnloadNow() -> HRESULT { S_FALSE }

const E_FAIL: HRESULT = HRESULT(0x80004005u32 as i32);
