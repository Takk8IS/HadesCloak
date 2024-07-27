import os
import platform
import subprocess
import getpass
import time
import sys
import hashlib
import secrets
import configparser
from pathlib import Path

DEBUG = True

def debug_print(*args, **kwargs):
    if DEBUG:
        print("DEBUG:", *args, file=sys.stderr, **kwargs)

def run_command(command, shell=False):
    try:
        debug_print(f"Executing command: {command}")
        result = subprocess.run(command, capture_output=True, text=True, shell=shell, check=True)
        debug_print(f"Result: {result.stdout.strip()}")
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        debug_print(f"Error executing command: {e}")
        return None

def check_status():
    status = {'microphone': False, 'webcam': False}
    system = platform.system()

    debug_print(f"Detected operating system: {system}")

    if system == 'Darwin':
        webcam_status = run_command(['system_profiler', 'SPCameraDataType'])
        status['webcam'] = 'FaceTime' in webcam_status if webcam_status else False

        mic_status = run_command(['system_profiler', 'SPAudioDataType'])
        status['microphone'] = 'Microphone' in mic_status if mic_status else False
    elif system == 'Linux':
        webcam_status = run_command(['lsmod | grep uvcvideo'], shell=True)
        status['webcam'] = bool(webcam_status)

        mic_status = run_command(['arecord', '-l'])
        status['microphone'] = 'card' in mic_status if mic_status else False
    elif system == 'Windows':
        webcam_status = run_command(['powershell', "Get-PnpDevice | Where-Object {$_.Class -eq 'Image'} | Where-Object {$_.Status -eq 'OK'}"])
        status['webcam'] = bool(webcam_status)

        mic_status = run_command(['powershell', "Get-PnpDevice | Where-Object {$_.Class -eq 'AudioEndpoint'} | Where-Object {$_.Status -eq 'OK'}"])
        status['microphone'] = bool(mic_status)

    debug_print(f"Device status: {status}")
    return status

def set_visibility_macos(visible):
    action = "load" if visible else "unload"
    debug_print(f"Attempting to {action} devices on macOS")

    webcam_command = ['sudo', 'launchctl', action, '-w', '/System/Library/LaunchDaemons/com.apple.webcam.plist']
    mic_command = ['sudo', 'launchctl', action, '-w', '/System/Library/LaunchDaemons/com.apple.audio.coreaudiod.plist']

    run_command(webcam_command)
    run_command(mic_command)

def set_visibility_linux(visible):
    action = "modprobe" if visible else "rmmod"
    debug_print(f"Attempting to {action} devices on Linux")

    webcam_command = ['sudo', action, 'uvcvideo']
    mic_command = ['sudo', action, 'snd_usb_audio']

    run_command(webcam_command)
    run_command(mic_command)

def set_visibility_windows(visible):
    action = "Enable" if visible else "Disable"
    debug_print(f"Attempting to {action} devices on Windows")

    webcam_command = ['powershell', f"Get-PnpDevice | Where-Object {{$_.Class -eq 'Image'}} | {action}-PnpDevice -Confirm:$false"]
    mic_command = ['powershell', f"Get-PnpDevice | Where-Object {{$_.Class -eq 'AudioEndpoint'}} | {action}-PnpDevice -Confirm:$false"]

    run_command(webcam_command)
    run_command(mic_command)

def set_visibility(visible):
    system = platform.system()

    if system == 'Darwin':
        set_visibility_macos(visible)
    elif system == 'Linux':
        set_visibility_linux(visible)
    elif system == 'Windows':
        set_visibility_windows(visible)
    else:
        debug_print(f"Unsupported operating system: {system}")
        return False

    time.sleep(5)
    new_status = check_status()
    debug_print(f"New status after change: {new_status}")
    return (new_status['webcam'] == visible) and (new_status['microphone'] == visible)

def print_banner():
    banner = """
    ██╗  ██╗ █████╗ ██████╗ ███████╗███████╗     ██████╗██╗      ██████╗  █████╗ ██╗  ██╗
    ██║  ██║██╔══██╗██╔══██╗██╔════╝██╔════╝    ██╔════╝██║     ██╔═══██╗██╔══██╗██║ ██╔╝
    ███████║███████║██║  ██║█████╗  ███████╗    ██║     ██║     ██║   ██║███████║█████╔╝
    ██╔══██║██╔══██║██║  ██║██╔══╝  ╚════██║    ██║     ██║     ██║   ██║██╔══██║██╔═██╗
    ██║  ██║██║  ██║██████╔╝███████╗███████║    ╚██████╗███████╗╚██████╔╝██║  ██║██║  ██╗
    ╚═╝  ╚═╝╚═╝  ╚═╝╚═════╝ ╚══════╝╚══════╝     ╚═════╝╚══════╝ ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝
    """
    print(banner)

def get_user_input(prompt):
    while True:
        try:
            debug_print("Waiting for user input")
            user_input = input(prompt).strip().lower()
            debug_print(f"User input: '{user_input}'")
            if user_input in ['y', 'n', 'r', '']:
                return user_input
            else:
                print("Invalid response. Please answer with 'Y', 'N', or 'R' to reset the password.")
        except EOFError:
            debug_print("EOFError caught")
            print("\nInput interrupted. Exiting the programme.")
            sys.exit(0)
        except KeyboardInterrupt:
            debug_print("KeyboardInterrupt caught")
            print("\nOperation cancelled by user. Exiting the programme.")
            sys.exit(0)
        except Exception as e:
            debug_print(f"Unexpected error in get_user_input: {e}")
            print(f"An unexpected error occurred: {e}. Please try again.")

def hash_password(password):
    salt = secrets.token_bytes(32)
    key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
    return salt + key

def verify_password(stored_password, provided_password):
    salt = stored_password[:32]
    key = stored_password[32:]
    new_key = hashlib.pbkdf2_hmac('sha256', provided_password.encode('utf-8'), salt, 100000)
    return key == new_key

def load_or_create_config():
    config = configparser.ConfigParser()
    config_file = Path.home() / '.hadescloak.ini'

    if config_file.exists():
        config.read(config_file)
    else:
        config['Security'] = {'password': ''}

    return config, config_file

def save_config(config, config_file):
    with open(config_file, 'w') as f:
        config.write(f)

def set_password(config, config_file):
    while True:
        try:
            password = getpass.getpass("Set a password for the Helm of Hades: ")
            if len(password) < 8:
                print("\nThe password must be at least 8 characters long.")
                continue
            confirm_password = getpass.getpass("Confirm the password: ")
            if password != confirm_password:
                print("\nThe passwords do not match. Please try again.")
                continue
            hashed_password = hash_password(password)
            config['Security']['password'] = hashed_password.hex()
            save_config(config, config_file)
            print("\nPassword set successfully.")
            break
        except Exception as e:
            debug_print(f"Error during password setting: {e}")
            print(f"An error occurred: {e}. Please try again.")

def main():
    print_banner()

    if os.geteuid() != 0:
        print("This script needs to be run as root (sudo).")
        print("Please run again with 'sudo python3 HadesCloak.py'")
        return

    config, config_file = load_or_create_config()

    while True:
        if not config['Security']['password']:
            print("No password set. Let's set up a new password.")
            set_password(config, config_file)
        else:
            stored_password = bytes.fromhex(config['Security']['password'])
            password = getpass.getpass("Enter the password to invoke the power of the Helm of Hades (or 'R' to reset): ")
            if password.lower() == 'r':
                print("\nResetting password...")
                set_password(config, config_file)
                continue
            if verify_password(stored_password, password):
                break
            print("Incorrect password. The power of the Helm of Hades remains inaccessible.")

    status = check_status()
    if status['microphone'] or status['webcam']:
        current_status = "visible to mortals"
    else:
        current_status = "hidden in the shadows"

    print(f"Your current status: {current_status}")

    while True:
        answer = get_user_input("Do you wish to invoke the power of the Helm of Hades and conceal yourself? (Y/N/R to reset password): ")

        if answer == 'y':
            print("Invoking the power of the Helm of Hades...")
            success = set_visibility(False)
            if success:
                print("You are now hidden in the shadows, invisible to the eyes and ears of mortals.")
            else:
                print("Failed to invoke the power of the Helm. Check the status of your devices and try again.")
            break
        elif answer == 'n':
            print("Removing the Helm of Hades...")
            success = set_visibility(True)
            if success:
                print("You are now visible to mortals.")
            else:
                print("Failed to remove the Helm. Check the status of your devices and try again.")
            break
        elif answer == 'r':
            print("Resetting password...")
            set_password(config, config_file)
        elif answer == '':
            debug_print("Empty input detected")
            print("No response provided. Please answer with 'Y', 'N', or 'R' to reset the password.")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        debug_print(f"Unexpected error in main: {e}")
        print(f"An unexpected error occurred: {e}")
        sys.exit(1)
