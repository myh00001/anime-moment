"""Install autostart and a desktop launcher for the current desktop user."""
from pathlib import Path
import argparse,os,subprocess,sys

def quoted(value):
    return '"'+str(value).replace('\\','\\\\').replace('"','\\"').replace('%','%%')+'"'

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--start', action='store_true', help='Also start the application now')
    args = parser.parse_args()
    if sys.platform != 'linux' or os.geteuid() == 0:
        raise SystemExit('Run as the normal S100 desktop user on Linux, not root.')
    root = Path(__file__).resolve().parents[1]/'service'
    config = Path(os.environ.get('XDG_CONFIG_HOME', Path.home()/'.config'))
    units = config/'systemd/user';auto = config/'autostart'
    units.mkdir(parents=True, exist_ok=True);auto.mkdir(parents=True, exist_ok=True)
    launcher = root/'start-local-display.sh'
    launcher.write_text('#!/bin/sh\nsystemctl --user import-environment DISPLAY WAYLAND_DISPLAY XAUTHORITY DBUS_SESSION_BUS_ADDRESS\nexec systemctl --user start anime-local-display.service\n',encoding='utf-8')
    launcher.chmod(0o755)
    unit = f'''[Unit]
Description=S100 USB anime camera fullscreen player
After=graphical-session.target
PartOf=graphical-session.target
[Service]
Type=simple
WorkingDirectory={root}
Environment=OMP_NUM_THREADS=2
Environment=OPENBLAS_NUM_THREADS=2
ExecStart=/usr/bin/python3 {quoted(root/'local_display.py')}
Restart=no
[Install]
WantedBy=graphical-session.target
'''
    (units/'anime-local-display.service').write_text(unit,encoding='utf-8')
    entry = f'''[Desktop Entry]
Type=Application
Name=实时动漫相机
Name[en]=Anime Camera
Exec={quoted(launcher)}
Icon=camera-video
Terminal=false
X-GNOME-Autostart-enabled=true
'''
    (auto/'anime-local-display.desktop').write_text(entry,encoding='utf-8')
    desktop = Path(subprocess.check_output(['xdg-user-dir','DESKTOP'],text=True).strip()).resolve()
    if not desktop.is_relative_to(Path.home().resolve()):
        raise SystemExit('Desktop directory must be inside your home directory.')
    desktop.mkdir(parents=True, exist_ok=True)
    icon = desktop/'anime-camera.desktop';icon.write_text(entry,encoding='utf-8');icon.chmod(0o755)
    subprocess.run(['gio','set',str(icon),'metadata::trusted','true'],check=False)
    subprocess.run(['systemctl','--user','daemon-reload'],check=True)
    subprocess.run(['systemctl','--user','enable','anime-local-display.service'],check=True)
    if args.start:
        subprocess.run([str(launcher)],check=True)
    print('Installed:', icon, '\nManual close will remain closed (Restart=no).')

if __name__ == '__main__':
    main()
