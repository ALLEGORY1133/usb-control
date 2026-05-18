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
import tkinter as tk

# ──────────────────────────────────────────────
# SOZLAMALAR — SERVER_URL ni o'zgartiring
# ──────────────────────────────────────────────
SERVER_URL = "https://usb-control.onrender.com/api/check-usb/"
PC_NAME    = platform.node()

BLOCKED_DEVICES = {}   # pnp_id -> caption
ALLOWED_DEVICES = {}   # pnp_id -> caption
lock = threading.Lock()


# ──────────────────────────────────────────────
# ADMIN HUQUQI
# ──────────────────────────────────────────────
def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False


# ──────────────────────────────────────────────
# XABARNOMA — 5 soniyada g'oyib bo'ladi
# ──────────────────────────────────────────────
def show_notification(title, message):
    def _run():
        try:
            root = tk.Tk()
            root.overrideredirect(True)
            root.attributes('-topmost', True)
            root.attributes('-alpha', 0.95)
            sw = root.winfo_screenwidth()
            sh = root.winfo_screenheight()
            w, h = 360, 90
            root.geometry(f"{w}x{h}+{sw-w-10}+{sh-h-60}")
            root.configure(bg='#1e1e2e')
            tk.Label(root, text=title, bg='#1e1e2e', fg='#cdd6f4',
                     font=('Segoe UI', 10, 'bold')).pack(anchor='w', padx=12, pady=(10, 2))
            tk.Label(root, text=message, bg='#1e1e2e', fg='#a6adc8',
                     font=('Segoe UI', 9), wraplength=336).pack(anchor='w', padx=12)
            root.after(5000, root.destroy)
            root.mainloop()
        except Exception:
            pass
    threading.Thread(target=_run, daemon=True).start()


# ──────────────────────────────────────────────
# USB PARENT ID TOPISH (USBSTOR → USB\VID_...)
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

    # USBSTOR bo'lsa parent USB ID ni topamiz
    target_id = pnp_id
    if pnp_id.upper().startswith("USBSTOR"):
        parent = find_usb_parent_id(pnp_id)
        if parent:
            target_id = parent

    # cfgmgr32 orqali
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

    # Zaxira: pnputil orqali
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
        return res.json().get("status", "pending")
    except Exception as e:
        print(f"   Server xato: {e}")
        return "pending"


# ──────────────────────────────────────────────
# YANGI USB UCHUN UMUMIY HANDLER
# ──────────────────────────────────────────────
def handle_new_usb(pnp_id, caption):
    with lock:
        if pnp_id in ALLOWED_DEVICES:
            return  # Allaqachon ruxsat berilgan

    print(f"🔌 Yangi USB: {caption}")
    status = query_server(pnp_id, caption)
    print(f"📡 Server: {status}")

    if status == "allowed":
        with lock:
            ALLOWED_DEVICES[pnp_id] = caption
            BLOCKED_DEVICES.pop(pnp_id, None)
        set_usb_state(pnp_id, "enable")
        show_notification("USB Ulandi ✅", f"'{caption}' xavfsiz va ishlatishga tayyor!")
    else:
        ok = set_usb_state(pnp_id, "disable")
        if ok:
            with lock:
                BLOCKED_DEVICES[pnp_id] = caption
                ALLOWED_DEVICES.pop(pnp_id, None)
            show_notification(
                "BLOKLANDI ⚠️",
                f"'{caption}' bloklandi! Admin ruxsati kutilmoqda."
            )


# ──────────────────────────────────────────────
# THREAD 1: Bloklangan → admin ruxsatini kutish
# ──────────────────────────────────────────────
def check_admin_approval():
    pythoncom.CoInitialize()
    while True:
        with lock:
            items = list(BLOCKED_DEVICES.items())

        for pnp_id, caption in items:
            status = query_server(pnp_id, caption)
            print(f"🔄 {caption[:25]} | {status}")

            if status == "allowed":
                with lock:
                    BLOCKED_DEVICES.pop(pnp_id, None)
                    ALLOWED_DEVICES[pnp_id] = caption
                set_usb_state(pnp_id, "enable")
                show_notification(
                    "USB: Ruxsat berildi ✅",
                    f"'{caption}' yoqildi! Agar ishlamasa — qayta tiqing."
                )

        time.sleep(5)


# ──────────────────────────────────────────────
# THREAD 2: Allowed → admin bekor qilsa bloklash
# (jismoniy ulab-uzmasdan real vaqtda)
# ──────────────────────────────────────────────
def watch_whitelist_changes():
    pythoncom.CoInitialize()
    while True:
        time.sleep(5)
        with lock:
            items = list(ALLOWED_DEVICES.items())

        for pnp_id, caption in items:
            status = query_server(pnp_id, caption)
            if status in ("blocked", "pending"):
                with lock:
                    ALLOWED_DEVICES.pop(pnp_id, None)
                    BLOCKED_DEVICES[pnp_id] = caption
                set_usb_state(pnp_id, "disable")
                show_notification(
                    "USB: Bloklandi 🚫",
                    f"'{caption}' ga ruxsat bekor qilindi!"
                )


# ──────────────────────────────────────────────
# THREAD 3: Bloklangan USB qayta tiqilsa
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

            print(f"🔁 Qayta ulandi: {caption}")
            status = query_server(pnp_id, caption)

            if status == "allowed":
                with lock:
                    BLOCKED_DEVICES.pop(pnp_id, None)
                    ALLOWED_DEVICES[pnp_id] = caption
                set_usb_state(pnp_id, "enable")
                show_notification("USB: Ruxsat berildi ✅", f"'{caption}' yoqildi.")
            else:
                set_usb_state(pnp_id, "disable")
                show_notification("Taqiqlangan USB! 🚫", f"'{caption}' hali bloklangan!")

        except wmi.x_wmi_timed_out:
            continue
        except Exception:
            continue


# ──────────────────────────────────────────────
# THREAD 4: Win32_DiskDrive — standart USB disklar
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
# ASOSIY OQIM: USBSTOR — ba'zi flesh kartalar
# ──────────────────────────────────────────────
def monitor_usbstor():
    pythoncom.CoInitialize()
    c = wmi.WMI()
    watcher = c.watch_for(notification_type="Creation", wmi_class="Win32_PnPEntity")
    print(f"🚀 Agent ({PC_NAME}) ishga tushdi. USB kutilmoqda...")

    while True:
        try:
            entity = watcher(timeout_ms=1000)
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

    # Threadlar
    threading.Thread(target=check_admin_approval,   daemon=True).start()
    threading.Thread(target=watch_whitelist_changes, daemon=True).start()
    threading.Thread(target=monitor_pnp_reconnects,  daemon=True).start()
    threading.Thread(target=monitor_diskdrive,        daemon=True).start()

    # Asosiy oqim
    monitor_usbstor()
