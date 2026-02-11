import socket
import struct
import cv2
import numpy as np
import time

HOST = '127.0.0.1'
PORT = 9001

PACKET_VIDEO = 1
PACKET_COMMAND = 2

remote_w = 1920   # временно, потом сервер пришлёт
remote_h = 1080

window_w = 0
window_h = 0

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.connect((HOST, PORT))

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

# ограничение частоты MOVE для стабильности
last_move = 0
def mouse_callback(event, x, y, flags, param):
    global window_w, window_h, last_move

    if window_w == 0 or window_h == 0:
        return

    rx = int(x * remote_w / window_w)
    ry = int(y * remote_h / window_h)

    now = time.time()
    if event == cv2.EVENT_MOUSEMOVE and now - last_move > 0.02:  # max ~50 FPS
        cmd = f"MOVE {rx} {ry}"
        send_packet(s, PACKET_COMMAND, cmd.encode())
        last_move = now
    elif event == cv2.EVENT_LBUTTONDOWN:
        send_packet(s, PACKET_COMMAND, b"CLICK LEFT")
    elif event == cv2.EVENT_RBUTTONDOWN:
        send_packet(s, PACKET_COMMAND, b"CLICK RIGHT")

cv2.namedWindow("Remote Screen")
cv2.setMouseCallback("Remote Screen", mouse_callback)

# Получаем разрешение от сервера
ptype, payload = recv_packet(s)
if ptype == 0 and payload:
    _, remote_w, remote_h = payload.decode().split()
    remote_w = int(remote_w)
    remote_h = int(remote_h)
    print(f"Remote resolution: {remote_w}x{remote_h}")

try:
    while True:
        ptype, payload = recv_packet(s)
        if ptype is None:
            print("Connection closed by server")
            break
        if ptype == PACKET_VIDEO:
            img_array = np.frombuffer(payload, dtype=np.uint8)
            frame = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
            cv2.imshow("Remote Screen", frame)
            window_h, window_w = frame.shape[:2]

        if cv2.waitKey(1) == 27:  # ESC для выхода
            break
finally:
    s.close()
    cv2.destroyAllWindows()