import socket
import struct
import cv2
import numpy as np
import time

SERVER_IP = '85.198.90.118'
PORT = 9001

PACKET_VIDEO = 1
PACKET_COMMAND = 2

# Начальные значения (обновятся сервером)
remote_w, remote_h = 1920, 1080
window_w, window_h = 0, 0
last_move = 0

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.connect((SERVER_IP, PORT))
s.sendall(b'\x02') # Сообщаем серверу, что мы - ВЬЮЕР

def send_packet(sock, ptype, payload: bytes):
    header = struct.pack('!BI', ptype, len(payload))
    sock.sendall(header + payload)

def recv_all(sock, size):
    data = b''
    while len(data) < size:
        part = sock.recv(size - len(data))
        if not part: return None
        data += part
    return data

def recv_packet(sock):
    header = recv_all(sock, 5)
    if not header: return None, None
    ptype, length = struct.unpack('!BI', header)
    payload = recv_all(sock, length)
    return ptype, payload

def mouse_callback(event, x, y, flags, param):
    global window_w, window_h, last_move
    if window_w == 0 or window_h == 0: return

    # Пропорциональный пересчет координат
    rx = int(x * remote_w / window_w)
    ry = int(y * remote_h / window_h)

    now = time.time()
    if event == cv2.EVENT_MOUSEMOVE and now - last_move > 0.02:
        send_packet(s, PACKET_COMMAND, f"MOVE {rx} {ry}".encode())
        last_move = now
    elif event == cv2.EVENT_LBUTTONDOWN:
        send_packet(s, PACKET_COMMAND, b"CLICK LEFT")
    elif event == cv2.EVENT_RBUTTONDOWN:
        send_packet(s, PACKET_COMMAND, b"CLICK RIGHT")

# 1. Сначала получаем разрешение (первый пакет от сервера)
ptype, payload = recv_packet(s)
if ptype == 0 and payload:
    parts = payload.decode().split()
    # Обработка случая, если сервер шлет "RES 1920 1080" или просто "1920 1080"
    if len(parts) == 3:
        _, remote_w, remote_h = parts
    else:
        remote_w, remote_h = parts
    remote_w, remote_h = int(remote_w), int(remote_h)
    print(f"Remote resolution: {remote_w}x{remote_h}")

# 2. Создаем окно OpenCV
win_name = "KM Remote Screen v0.01 (ESC to exit)"
cv2.namedWindow(win_name, cv2.WINDOW_NORMAL) # WINDOW_NORMAL позволяет менять размер
cv2.resizeWindow(win_name, 1280, 720)        # Начальный размер окна на клиенте
cv2.setMouseCallback(win_name, mouse_callback)

# 3. Основной цикл видео
try:
    while True:
        ptype, payload = recv_packet(s)
        if ptype is None:
            print("Disconnected")
            break
        
        if ptype == PACKET_VIDEO:
            img_array = np.frombuffer(payload, dtype=np.uint8)
            frame = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
            
            if frame is not None:
                cv2.imshow(win_name, frame)
                # Обновляем текущие размеры окна для корректных координат мыши
                window_h, window_w = frame.shape[:2]

        if cv2.waitKey(1) == 27: # ESC
            break
finally:
    s.close()
    cv2.destroyAllWindows()

# допилить интерфейс