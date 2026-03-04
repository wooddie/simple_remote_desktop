import socket
import struct
import time
import mss
import random
import pyautogui
import threading
import platform
import numpy as np
import cv2

# Динамический импорт для Windows (DirectInput лучше работает в играх)
IS_WINDOWS = platform.system() == "Windows"
if IS_WINDOWS:
    try:
        import pydirectinput as engine
    except ImportError:
        import pyautogui as engine
else:
    import pyautogui as engine

pyautogui.PAUSE = 0

SERVER_IP = '85.198.90.118'
PORT = 9001
PACKET_VIDEO, PACKET_COMMAND, PACKET_SYSTEM = 1, 2, 0

host_id = str(random.randint(1000, 9999))
password = str(random.randint(100000, 999999))
print(f"YOUR ID: {host_id} | YOUR PASS: {password}")

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.connect((SERVER_IP, PORT))
s.sendall(b'\x01' + host_id.encode() + password.encode())
conn = s
conn.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 1024 * 1024) # Увеличили буфер до 1Мб

def send_packet(sock, ptype, payload: bytes):
    header = struct.pack('!BI', ptype, len(payload))
    sock.sendall(header + payload)

def recv_packet(sock):
    header_data = b''
    while len(header_data) < 5:
        chunk = sock.recv(5 - len(header_data))
        if not chunk: return None, None
        header_data += chunk
    ptype, length = struct.unpack('!BI', header_data)
    payload = b''
    while len(payload) < length:
        chunk = sock.recv(length - len(payload))
        if not chunk: return None, None
        payload += chunk
    return ptype, payload

# Отправляем разрешение
screen_w, screen_h = pyautogui.size()
send_packet(conn, PACKET_SYSTEM, f"RES {screen_w} {screen_h}".encode())

def handle_command(cmd):
    parts = cmd.split()
    if not parts: return
    action = parts[0]

    try:
        if action == "MOVE":
            x, y = int(parts[1]), int(parts[2])
            engine.moveTo(max(0, min(x, screen_w - 1)), max(0, min(y, screen_h - 1)))
            
        elif action == "KDOWN":
            key = parts[1].lower()
            if key in ['left', 'right']:
                engine.mouseDown(button=key)
            else:
                # Маппинг клавиш (pynput шлет 'ctrl_l', pyautogui хочет 'ctrl')
                if 'ctrl' in key: key = 'ctrl'
                if 'shift' in key: key = 'shift'
                if 'alt' in key: key = 'alt'
                engine.keyDown(key)
                
        elif action == "KUP":
            key = parts[1].lower()
            if key in ['left', 'right']:
                engine.mouseUp(button=key)
            else:
                if 'ctrl' in key: key = 'ctrl'
                if 'shift' in key: key = 'shift'
                if 'alt' in key: key = 'alt'
                engine.keyUp(key)
    except Exception as e:
        pass

def command_thread():
    try:
        while True:
            ptype, payload = recv_packet(conn)
            if ptype is None: break
            if ptype == PACKET_COMMAND:
                handle_command(payload.decode())
    finally:
        conn.close()

threading.Thread(target=command_thread, daemon=True).start()

# --- ОТПРАВКА ВИДЕО С ДЕТЕКТОРОМ ИЗМЕНЕНИЙ ---
last_frame_gray = None

with mss.mss() as sct:
    monitor = sct.monitors[1]
    while True:
        start_time = time.time()
        
        # Захват и подготовка
        img = np.array(sct.grab(monitor))
        frame = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
        frame_resized = cv2.resize(frame, (1280, 720)) # Оптимально для передачи

        # Проверка на изменения (детектор движения)
        gray = cv2.cvtColor(frame_resized, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (21, 21), 0) # Сглаживаем шумы

        if last_frame_gray is not None:
            # Считаем разницу между кадрами
            diff = cv2.absdiff(last_frame_gray, gray)
            if np.mean(diff) < 0.5: # Порог чувствительности (0.5 - очень мало изменений)
                time.sleep(0.03)
                continue
        
        last_frame_gray = gray

        # Сжатие
        _, buffer = cv2.imencode('.jpg', frame_resized, [int(cv2.IMWRITE_JPEG_QUALITY), 60])
        
        try:
            send_packet(conn, PACKET_VIDEO, buffer.tobytes())
        except:
            break

        # Ограничение FPS (30 кадров)
        elapsed = time.time() - start_time
        time.sleep(max(0, (1/30) - elapsed))