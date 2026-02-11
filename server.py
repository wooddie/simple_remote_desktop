import socket
import struct
import time
import mss
from PIL import Image
import io
import pyautogui
import threading

HOST = '0.0.0.0'
PORT = 9001

PACKET_VIDEO = 1
PACKET_COMMAND = 2
PACKET_SYSTEM = 0  # для служебных сообщений, например разрешение

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind((HOST, PORT))
s.listen(1)
print("Waiting for connection...")
conn, addr = s.accept()
print("Connected:", addr)

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
    if not parts:
        return

    action = parts[0]
    if action == "MOVE" and len(parts) == 3:
        x, y = int(parts[1]), int(parts[2])
        x = max(0, min(x, screen_w - 1))
        y = max(0, min(y, screen_h - 1))
        pyautogui.moveTo(x, y)
    elif action == "CLICK" and len(parts) == 2:
        button = parts[1].lower()
        pyautogui.click(button=button)
    elif action == "KEY_PRESS" and len(parts) == 2:
        key = parts[1]
        pyautogui.press(key)
    else:
        print("Unknown command:", cmd)

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
with mss.mss() as sct:
    monitor = sct.monitors[1]  # основной монитор
    while True:
        screenshot = sct.grab(monitor)
        img = Image.frombytes('RGB', screenshot.size, screenshot.rgb)

        buf = io.BytesIO()
        img.save(buf, format='JPEG', quality=50)
        data = buf.getvalue()

        try:
            send_packet(conn, PACKET_VIDEO, data)
        except BrokenPipeError:
            print("Client disconnected")
            break

        time.sleep(0.03)  # ~30 FPS