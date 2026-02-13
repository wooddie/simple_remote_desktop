import socket
import threading

def bridge(source, dest):
    """Пересылает данные из одного сокета в другой до упора"""
    try:
        while True:
            data = source.recv(128 * 1024) # Буфер 128КБ
            if not data: break
            dest.sendall(data)
    except:
        pass
    finally:
        source.close()
        dest.close()

def start_relay():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(('0.0.0.0', 9001))
    server.listen(5)
    print("Relay Server active on port 9001...")

    connections = {}

    while True:
        conn, addr = server.accept()
        try:
            # Ждем первый байт роли
            role_byte = conn.recv(1)
            
            if role_byte == b'\x01':
                connections['host'] = conn
                print(f"Host connected from {addr}")
            elif role_byte == b'\x02':
                connections['viewer'] = conn
                print(f"Viewer connected from {addr}")

            # Если пара собралась — запускаем мост
            if 'host' in connections and 'viewer' in connections:
                h = connections.pop('host')
                v = connections.pop('viewer')
                
                # Поток: Хост -> Вьюер (видео)
                threading.Thread(target=bridge, args=(h, v), daemon=True).start()
                # Поток: Вьюер -> Хост (команды)
                threading.Thread(target=bridge, args=(v, h), daemon=True).start()
                
                print("Connection bridged successfully!")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    start_relay()