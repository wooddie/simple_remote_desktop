import socket
import struct
import time
import mss
#from PIL import Image
import random
import pyautogui
import threading
import platform
import numpy as np
import cv2

# Динамический импорт pydirectinput только для Windows
IS_WINDOWS = platform.system() == "Windows"
if IS_WINDOWS:
    try:
        import pydirectinput
    except ImportError:
        IS_WINDOWS = False
        print("pydirectinput not found, falling back to pyautogui")

pyautogui.PAUSE = 0

SERVER_IP = '85.198.90.118'
PORT = 9001

PACKET_VIDEO = 1
PACKET_COMMAND = 2
PACKET_SYSTEM = 0  # для служебных сообщений, например разрешение
pyautogui.PAUSE = 0

host_id = str(random.randint(1000, 9999))
password = str(random.randint(100000, 999999))

print(f"YOUR ID: {host_id}")
print(f"YOUR PASS: {password}")

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.connect((SERVER_IP, PORT))
s.sendall(b'\x01' + host_id.encode() + password.encode()) # Сообщаем серверу, что мы - ХОСТ
conn = s # Теперь используем s как основное соединение
conn.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 65536)

def send_packet(sock, ptype, payload: bytes):
    header = struct.pack('!BI', ptype, len(payload))
    sock.sendall(header + payload)

def recv_all(sock, size):
    data = b''
    while len(data) < size:
        part = sock.recv(size - len(data))
        if not part:
            return None
        data += part
    return data

def recv_packet(sock):
    header = recv_all(sock, 5)
    if not header:
        return None, None
    ptype, length = struct.unpack('!BI', header)
    payload = recv_all(sock, length)
    return ptype, payload

# Получаем реальное разрешение экрана и отправляем клиенту
screen_w, screen_h = pyautogui.size()
msg = f"RES {screen_w} {screen_h}".encode()
send_packet(conn, PACKET_SYSTEM, msg)
print(f"Sent screen resolution to client: {screen_w}x{screen_h}")

def handle_command(cmd):
    parts = cmd.split()
    if not parts: return

    action = parts[0]
    
    # Выбор исполнителя (pydirectinput для Windows, pyautogui для остальных)
    engine = pydirectinput if IS_WINDOWS else pyautogui

    try:
        if action == "MOVE" and len(parts) == 3:
            x, y = int(parts[1]), int(parts[2])
            x = max(0, min(x, screen_w - 1))
            y = max(0, min(y, screen_h - 1))
            engine.moveTo(x, y)
            
        elif action == "CLICK" and len(parts) == 2:
            button = parts[1].lower()
            engine.click(button=button)
            
        elif action == "KEY_PRESS" and len(parts) == 2:
            key = parts[1]
            engine.press(key)
            
    except Exception as e:
        print(f"Error executing {action}: {e}")

def command_thread():
    try:
        while True:
            ptype, payload = recv_packet(conn)
            if ptype is None:
                print("Client disconnected")
                break
            if ptype == PACKET_COMMAND:
                handle_command(payload.decode())
    finally:
        conn.close()

# поток приёма команд
threading.Thread(target=command_thread, daemon=True).start()

# поток отправки экрана
target_fps = 30
frame_time = 1 / target_fps

with mss.mss() as sct:
    monitor = sct.monitors[1]

    while True:
        start = time.time()

        screenshot = sct.grab(monitor)
        frame = np.array(screenshot)
        frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)

        # 🔥 уменьшить размер (очень важно)
        frame = cv2.resize(frame, (1280, 720))

        _, buffer = cv2.imencode(
            '.jpg',
            frame,
            [int(cv2.IMWRITE_JPEG_QUALITY), 70]
        )
        data = buffer.tobytes()

        try:
            send_packet(conn, PACKET_VIDEO, data)
        except BrokenPipeError:
            break

        elapsed = time.time() - start
        sleep_time = frame_time - elapsed
        if sleep_time > 0:
            time.sleep(sleep_time)