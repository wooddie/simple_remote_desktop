import socket
import struct
import cv2
import numpy as np
from pynput import keyboard

SERVER_IP = '85.198.90.118'
PORT = 9001

PACKET_VIDEO = 1
PACKET_COMMAND = 2

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.connect((SERVER_IP, PORT))
s.sendall(b'\x02') 

# Авторизация
len_data = struct.unpack('!I', s.recv(4))[0]
hosts = s.recv(len_data).decode()
print(f"Доступные хосты: {hosts}")
target_id = input("Введите ID: ")
target_pass = input("Введите пароль: ")
s.sendall(target_id.encode() + target_pass.encode())

if s.recv(2) != b"OK":
    print("Ошибка авторизации"); exit()

def send_packet(ptype, payload: bytes):
    try:
        header = struct.pack('!BI', ptype, len(payload))
        s.sendall(header + payload)
    except: pass

# --- КЛАВИАТУРА (Глобальный перехват) ---
def on_press(key):
    try:
        # Пытаемся получить символ, если нет - берем имя спецклавиши
        k = key.char if hasattr(key, 'char') and key.char else str(key).replace('Key.', '')
        send_packet(PACKET_COMMAND, f"KDOWN {k}".encode())
    except: pass

def on_release(key):
    try:
        k = key.char if hasattr(key, 'char') and key.char else str(key).replace('Key.', '')
        send_packet(PACKET_COMMAND, f"KUP {k}".encode())
    except: pass

listener = keyboard.Listener(on_press=on_press, on_release=on_release)
listener.start()

# --- МЫШЬ ---
remote_w, remote_h = 1280, 720
window_w, window_h = 1280, 720

def mouse_callback(event, x, y, flags, param):
    global window_w, window_h
    # Расчет относительно реального размера ОКНА
    rx = int(x * remote_w / window_w)
    ry = int(y * remote_h / window_h)
    
    if event == cv2.EVENT_MOUSEMOVE:
        send_packet(PACKET_COMMAND, f"MOVE {rx} {ry}".encode())
    elif event == cv2.EVENT_LBUTTONDOWN:
        send_packet(PACKET_COMMAND, b"KDOWN left")
    elif event == cv2.EVENT_LBUTTONUP:
        send_packet(PACKET_COMMAND, b"KUP left")
    elif event == cv2.EVENT_RBUTTONDOWN:
        send_packet(PACKET_COMMAND, b"KDOWN right")
    elif event == cv2.EVENT_RBUTTONUP:
        send_packet(PACKET_COMMAND, b"KUP right")

# Читаем первый пакет (разрешение)
header = s.recv(5)
if header:
    ptype, length = struct.unpack('!BI', header)
    res_msg = s.recv(length).decode().split()
    remote_w, remote_h = int(res_msg[1]), int(res_msg[2])
    print(f"Resolution: {remote_w}x{remote_h}")

win_name = "Remote Screen"
cv2.namedWindow(win_name, cv2.WINDOW_NORMAL)
cv2.setMouseCallback(win_name, mouse_callback)

def recv_all(size):
    data = b''
    while len(data) < size:
        part = s.recv(size - len(data))
        if not part: return None
        data += part
    return data

# --- ЦИКЛ ВИДЕО ---
try:
    while True:
        header = recv_all(5)
        if not header: break
        ptype, length = struct.unpack('!BI', header)
        payload = recv_all(length)
        
        if ptype == PACKET_VIDEO:
            nparr = np.frombuffer(payload, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if frame is not None:
                cv2.imshow(win_name, frame)
                # Получаем актуальный размер окна (если его растянули)
                rect = cv2.getWindowImageRect(win_name)
                window_w, window_h = rect[2], rect[3]

        if cv2.waitKey(1) == 27: # ESC в окне OpenCV для выхода
            break
finally:
    s.close()
    cv2.destroyAllWindows()