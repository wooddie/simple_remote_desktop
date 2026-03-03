import socket
import threading
import struct

# Хранилище: { "host_id": {"socket": socket_obj, "password": "123"} }
waiting_hosts = {}

def bridge(source, dest):
    try:
        while True:
            data = source.recv(128 * 1024)
            if not data: break
            dest.sendall(data)
    except: pass
    finally:
        source.close()
        dest.close()

def handle_new_connection(conn, addr):
    try:
        # 1. Читаем роль: 1 - Хост, 2 - Вьюер
        role = conn.recv(1)
        
        if role == b'\x01':  # РЕГИСТРАЦИЯ ХОСТА
            # Формат: ID(4 байта) + PASS(6 байт)
            data = conn.recv(10).decode()
            host_id = data[:4]
            password = data[4:]
            waiting_hosts[host_id] = {"socket": conn, "password": password}
            print(f"Host {host_id} registered (Pass: {password})")
            
        elif role == b'\x02':  # ПОДКЛЮЧЕНИЕ ВЬЮЕРА
            # Отправляем список доступных ID (просто строкой через запятую)
            hosts_list = ",".join(waiting_hosts.keys())
            conn.sendall(struct.pack('!I', len(hosts_list)) + hosts_list.encode())
            
            # Ждем выбор: ID(4) + PASS(6)
            choice = conn.recv(10).decode()
            target_id = choice[:4]
            target_pass = choice[4:]
            
            if target_id in waiting_hosts and waiting_hosts[target_id]["password"] == target_pass:
                host_data = waiting_hosts.pop(target_id)
                host_sock = host_data["socket"]
                
                conn.sendall(b"OK") # Подтверждаем вьюеру успех
                
                # Запускаем мосты
                threading.Thread(target=bridge, args=(host_sock, conn), daemon=True).start()
                threading.Thread(target=bridge, args=(conn, host_sock), daemon=True).start()
                print(f"Bridged Viewer to Host {target_id}")
            else:
                conn.sendall(b"FAIL")
                conn.close()
    except Exception as e:
        print(f"Error handling {addr}: {e}")

def start_relay():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(('0.0.0.0', 9001))
    server.listen(100)
    print("Relay Server Hub active...")
    while True:
        conn, addr = server.accept()
        threading.Thread(target=handle_new_connection, args=(conn, addr)).start()

if __name__ == "__main__":
    start_relay()