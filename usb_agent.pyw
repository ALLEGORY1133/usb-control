"""
USB Xavfsizlik Agenti
Faqat Windows PC da ishlaydi.
Server: https://usb-control.onrender.com
"""

import wmi
import requests
import platform
import subprocess
import time
import threading
import pythoncom
import ctypes
import sys
import winreg
import webbrowser

import pystray
import logging
from PIL import Image, ImageDraw

# ──────────────────────────────────────────────
# SOZLAMALAR
# ──────────────────────────────────────────────
SERVER_URL = "https://usb-control.onrender.com/api/check-usb/"
ADMIN_URL  = "https://usb-control.onrender.com/admin/"
PC_NAME    = platform.node()

logging.basicConfig(
    filename=r"C:\usb_agent.log",
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    datefmt="%d.%m.%Y %H:%M:%S",
    encoding="utf-8",
)
log = logging.getLogger("usb_agent")

BLOCKED_DEVICES = {}   # pnp_id -> caption
ALLOWED_DEVICES = {}   # pnp_id -> caption
lock = threading.Lock()

tray_icon = None


# ──────────────────────────────────────────────
# TRAY IKONKASI
# ──────────────────────────────────────────────
def _make_icon(bg, dot):
    img  = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    # Fon doira
    draw.ellipse([2, 2, 62, 62], fill=bg)
    # USB belgisi — shtok
    draw.rectangle([30, 10, 34, 38], fill='white')
    # USB belgisi — konnektyor
    draw.rectangle([22, 38, 42, 46], fill='white')
    draw.rectangle([22, 46, 26, 54], fill='white')
    draw.rectangle([38, 46, 42, 54], fill='white')
    # Holat nuqtasi
    draw.ellipse([42, 2, 62, 22], fill=dot)
    return img

ICON_IDLE    = _make_icon('#2c3e50', '#2ecc71')   # yashil — tayyor
ICON_BLOCKED = _make_icon('#2c3e50', '#e74c3c')   # qizil  — bloklangan bor
ICON_PENDING = _make_icon('#2c3e50', '#f39c12')   # sariq  — kutilmoqda


def _refresh_tray():
    if tray_icon is None:
        return
    with lock:
        n_blocked = len(BLOCKED_DEVICES)
        n_allowed = len(ALLOWED_DEVICES)

    if n_blocked > 0:
        tray_icon.icon  = ICON_BLOCKED
        tray_icon.title = f"USB Nazorat | {n_blocked} ta bloklangan"
    elif n_allowed > 0:
        tray_icon.icon  = ICON_IDLE
        tray_icon.title = f"USB Nazorat | {n_allowed} ta qurilma ruxsat berilgan"
    else:
        tray_icon.icon  = ICON_IDLE
        tray_icon.title = f"USB Nazorat | {PC_NAME}"

    tray_icon.update_menu()


def _build_menu():
    with lock:
        n_blocked = len(BLOCKED_DEVICES)
        n_allowed = len(ALLOWED_DEVICES)
        blocked_list = list(BLOCKED_DEVICES.values())
        allowed_list = list(ALLOWED_DEVICES.values())

    items = [
        pystray.MenuItem(f"Kompyuter: {PC_NAME}", None, enabled=False),
        pystray.Menu.SEPARATOR,
    ]

    if n_blocked:
        items.append(pystray.MenuItem(f"Bloklangan ({n_blocked}):", None, enabled=False))
        for cap in blocked_list[:5]:
            items.append(pystray.MenuItem(f"  - {cap[:30]}", None, enabled=False))
        if n_blocked > 5:
            items.append(pystray.MenuItem(f"  ... va yana {n_blocked - 5} ta", None, enabled=False))
        items.append(pystray.Menu.SEPARATOR)

    if n_allowed:
        items.append(pystray.MenuItem(f"Ruxsat berilgan ({n_allowed}):", None, enabled=False))
        for cap in allowed_list[:5]:
            items.append(pystray.MenuItem(f"  - {cap[:30]}", None, enabled=False))
        if n_allowed > 5:
            items.append(pystray.MenuItem(f"  ... va yana {n_allowed - 5} ta", None, enabled=False))
        items.append(pystray.Menu.SEPARATOR)

    if not n_blocked and not n_allowed:
        items.append(pystray.MenuItem("USB qurilma ulangan emas", None, enabled=False))
        items.append(pystray.Menu.SEPARATOR)

    items += [
        pystray.MenuItem("Admin panelni ochish", lambda _icon, _item: webbrowser.open(ADMIN_URL)),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Chiqish", lambda _icon, _item: _icon.stop()),
    ]

    return pystray.Menu(*items)


# ──────────────────────────────────────────────
# ADMIN HUQUQI
# ──────────────────────────────────────────────
def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False


# ──────────────────────────────────────────────
# USB PARENT ID TOPISH
# ──────────────────────────────────────────────
def find_usb_parent_id(disk_pnp_id):
    try:
        parts = disk_pnp_id.split("\\")
        if len(parts) < 3:
            return None
        serial = parts[-1].split("&")[0]
        c = wmi.WMI()
        for dev in c.Win32_PnPEntity():
            pid = dev.PNPDeviceID or ""
            if pid.upper().startswith("USB\\") and serial and serial in pid:
                return pid
    except Exception:
        pass
    return None


# ──────────────────────────────────────────────
# BLOKLASH / YOQISH
# ──────────────────────────────────────────────
def set_usb_state(pnp_id, state="disable"):
    pythoncom.CoInitialize()

    target_id = pnp_id
    if pnp_id.upper().startswith("USBSTOR"):
        parent = find_usb_parent_id(pnp_id)
        if parent:
            target_id = parent

    cfgmgr  = ctypes.windll.cfgmgr32
    devinst = ctypes.c_ulong()
    ret = cfgmgr.CM_Locate_DevNodeW(ctypes.byref(devinst), target_id, 0)

    if ret == 0:
        if state == "disable":
            ret = cfgmgr.CM_Disable_DevNode(devinst, 0)
        else:
            ret = cfgmgr.CM_Enable_DevNode(devinst, 0)

        if ret == 0:
            if state == "enable":
                time.sleep(1)
                subprocess.run("pnputil /scan-devices", shell=True,
                               capture_output=True,
                               creationflags=subprocess.CREATE_NO_WINDOW)
            return True

    action = "disable" if state == "disable" else "enable"
    result = subprocess.run(
        f'pnputil /{action}-device "{target_id}"',
        shell=True, capture_output=True, text=True,
        creationflags=subprocess.CREATE_NO_WINDOW
    )
    if state == "enable" and result.returncode == 0:
        time.sleep(1)
        subprocess.run("pnputil /scan-devices", shell=True,
                       capture_output=True,
                       creationflags=subprocess.CREATE_NO_WINDOW)
    return result.returncode == 0


# ──────────────────────────────────────────────
# SERVERGA SO'ROV
# ──────────────────────────────────────────────
def query_server(pnp_id, caption):
    try:
        res = requests.post(
            SERVER_URL,
            json={"pnp_id": pnp_id, "pc_name": PC_NAME, "caption": caption},
            timeout=15,
        )
        res.raise_for_status()
        status = res.json().get("status", "pending")
        log.info("SERVER  %s  ->  %s", caption[:40], status)
        return status
    except requests.exceptions.ConnectionError as e:
        log.warning("OFFLINE  %s  |  %s", caption[:40], e)
        return "offline"
    except requests.exceptions.Timeout:
        log.warning("TIMEOUT  %s  (15s)", caption[:40])
        return "offline"
    except requests.exceptions.HTTPError as e:
        log.error("HTTP_ERR  %s  |  %s", caption[:40], e)
        return "pending"
    except Exception as e:
        log.error("XATO  %s  |  %s", caption[:40], e)
        return "offline"


# ──────────────────────────────────────────────
# YANGI USB HANDLER
# ──────────────────────────────────────────────
def handle_new_usb(pnp_id, caption):
    with lock:
        if pnp_id in ALLOWED_DEVICES:
            return

    log.info("ULANDI   %s  [%s]", caption[:40], pnp_id[:60])
    status = query_server(pnp_id, caption)

    if status == "allowed":
        with lock:
            ALLOWED_DEVICES[pnp_id] = caption
            BLOCKED_DEVICES.pop(pnp_id, None)
        set_usb_state(pnp_id, "enable")
        log.info("YOQILDI  %s", caption[:40])
        _refresh_tray()

    elif status == "offline":
        log.warning("OFFLINE  %s  — o'zgarishsiz qoldi", caption[:40])

    else:
        ok = set_usb_state(pnp_id, "disable")
        if ok:
            with lock:
                BLOCKED_DEVICES[pnp_id] = caption
                ALLOWED_DEVICES.pop(pnp_id, None)
            log.info("BLOKLANDI  %s  (status=%s)", caption[:40], status)
            _refresh_tray()


# ──────────────────────────────────────────────
# THREAD 1: Bloklangan — ruxsat kutish
# ──────────────────────────────────────────────
def check_admin_approval():
    pythoncom.CoInitialize()
    while True:
        with lock:
            items = list(BLOCKED_DEVICES.items())

        changed = False
        for pnp_id, caption in items:
            status = query_server(pnp_id, caption)
            if status == "allowed":
                with lock:
                    BLOCKED_DEVICES.pop(pnp_id, None)
                    ALLOWED_DEVICES[pnp_id] = caption
                set_usb_state(pnp_id, "enable")
                changed = True

        if changed:
            _refresh_tray()

        time.sleep(5)


# ──────────────────────────────────────────────
# THREAD 2: Ruxsat berilgan — bekor qilinishini kuzatish
# ──────────────────────────────────────────────
def watch_whitelist_changes():
    pythoncom.CoInitialize()
    while True:
        time.sleep(5)
        with lock:
            items = list(ALLOWED_DEVICES.items())

        changed = False
        for pnp_id, caption in items:
            status = query_server(pnp_id, caption)
            if status in ("blocked", "pending"):
                with lock:
                    ALLOWED_DEVICES.pop(pnp_id, None)
                    BLOCKED_DEVICES[pnp_id] = caption
                set_usb_state(pnp_id, "disable")
                changed = True

        if changed:
            _refresh_tray()


# ──────────────────────────────────────────────
# THREAD 3: Bloklangan USB qayta ulanishi
# ──────────────────────────────────────────────
def monitor_pnp_reconnects():
    pythoncom.CoInitialize()
    c = wmi.WMI()
    watcher = c.watch_for(notification_type="Creation", wmi_class="Win32_PnPEntity")

    while True:
        try:
            entity = watcher(timeout_ms=1000)
            pnp_id = entity.PNPDeviceID or ""

            if not pnp_id.upper().startswith("USB"):
                continue

            with lock:
                is_blocked = pnp_id in BLOCKED_DEVICES
                caption    = BLOCKED_DEVICES.get(pnp_id, entity.Caption or pnp_id)

            if not is_blocked:
                continue

            status = query_server(pnp_id, caption)

            if status == "allowed":
                with lock:
                    BLOCKED_DEVICES.pop(pnp_id, None)
                    ALLOWED_DEVICES[pnp_id] = caption
                set_usb_state(pnp_id, "enable")
                _refresh_tray()
            else:
                set_usb_state(pnp_id, "disable")

        except wmi.x_wmi_timed_out:
            continue
        except Exception:
            continue


# ──────────────────────────────────────────────
# THREAD 4: Win32_DiskDrive
# ──────────────────────────────────────────────
def monitor_diskdrive():
    pythoncom.CoInitialize()
    c = wmi.WMI()
    watcher = c.watch_for(notification_type="Creation", wmi_class="Win32_DiskDrive")

    while True:
        try:
            usb = watcher(timeout_ms=1000)
            if usb.InterfaceType != "USB":
                continue
            handle_new_usb(usb.PNPDeviceID, usb.Caption)
        except wmi.x_wmi_timed_out:
            continue
        except Exception as e:
            print(f"DiskDrive xato: {e}")
            continue


# ──────────────────────────────────────────────
# THREAD 5: USBSTOR
# ──────────────────────────────────────────────
def monitor_usbstor():
    pythoncom.CoInitialize()
    c = wmi.WMI()
    watcher = c.watch_for(notification_type="Creation", wmi_class="Win32_PnPEntity")
    print(f"Agent ({PC_NAME}) ishga tushdi. USB kutilmoqda...")

    while True:
        try:
            entity  = watcher(timeout_ms=1000)
            pnp_id  = entity.PNPDeviceID or ""
            caption = entity.Caption or pnp_id

            if not pnp_id.upper().startswith("USBSTOR\\DISK"):
                continue

            handle_new_usb(pnp_id, caption)

        except wmi.x_wmi_timed_out:
            continue
        except Exception as e:
            print(f"USBSTOR xato: {e}")
            continue


# ──────────────────────────────────────────────
# STARTUP SKAN — mavjud USB larni tekshirish
# ──────────────────────────────────────────────
def startup_scan():
    pythoncom.CoInitialize()
    try:
        c = wmi.WMI()
        for disk in c.Win32_DiskDrive():
            if disk.InterfaceType == "USB" and disk.PNPDeviceID:
                handle_new_usb(disk.PNPDeviceID, disk.Caption or disk.PNPDeviceID)
    except Exception as e:
        print(f"Startup skan xato: {e}")


# ──────────────────────────────────────────────
# AUTORUN O'CHIRISH
# ──────────────────────────────────────────────
def disable_autorun():
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Policies\Explorer",
            0, winreg.KEY_SET_VALUE,
        )
        winreg.SetValueEx(key, "NoDriveTypeAutoRun", 0, winreg.REG_DWORD, 0xFF)
        winreg.CloseKey(key)
    except Exception:
        pass


# ──────────────────────────────────────────────
# ISHGA TUSHIRISH
# ──────────────────────────────────────────────
if __name__ == "__main__":
    if not is_admin():
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable,
            " ".join(f'"{a}"' for a in sys.argv), None, 1,
        )
        sys.exit()

    disable_autorun()

    log.info("=== Agent ishga tushdi | PC: %s ===", PC_NAME)
    threading.Thread(target=startup_scan, daemon=True).start()

    for target in (
        check_admin_approval,
        watch_whitelist_changes,
        monitor_pnp_reconnects,
        monitor_diskdrive,
        monitor_usbstor,
    ):
        threading.Thread(target=target, daemon=True).start()

    # Tray ikonkasi — asosiy thread
    tray_icon = pystray.Icon(
        name="usb_agent",
        icon=ICON_IDLE,
        title=f"USB Nazorat | {PC_NAME}",
        menu=pystray.Menu(lambda: _build_menu().items),
    )
    tray_icon.run()
