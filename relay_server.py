import socket
import threading
import struct

# Хранилище: { "host_id": {"socket": socket_obj, "password": "123"} }
waiting_hosts = {}

def bridge(source, dest):
    """Перебрасывает данные между сокетами до тех пор, пока они живы."""
    try:
        while True:
            data = source.recv(128 * 1024)
            if not data: 
                break
            dest.sendall(data)
    except: 
        pass
    finally:
        # Если один упал, закрываем обоих, чтобы завершить потоки
        try: source.close() 
        except: pass
        try: dest.close() 
        except: pass

def handle_new_connection(conn, addr):
    try:
        role = conn.recv(1)
        
        if role == b'\x01':  # РЕГИСТРАЦИЯ ХОСТА
            data = conn.recv(10).decode()
            if len(data) < 10: return
            host_id = data[:4]
            password = data[4:]
            
            # Упрощаем: просто сохраняем сокет. 
            # Не нужно запускать фоновые проверки recv(PEEK), они ведут к дисконнектам
            waiting_hosts[host_id] = {"socket": conn, "password": password, "addr": addr}
            print(f"[+] Host {host_id} registered from {addr}")
            
        elif role == b'\x02':  # ПОДКЛЮЧЕНИЕ ВЬЮЕРА
            # Очистка списка от реально закрытых сокетов
            for hid in list(waiting_hosts.keys()):
                sock = waiting_hosts[hid]["socket"]
                # Проверка на закрытый сокет (fileno -1 означает, что сокет закрыт локально)
                if sock.fileno() == -1:
                    waiting_hosts.pop(hid, None)

            hosts_list = ",".join(waiting_hosts.keys())
            conn.sendall(struct.pack('!I', len(hosts_list)) + hosts_list.encode())
            
            choice = conn.recv(10).decode()
            if len(choice) < 10: return
            target_id = choice[:4]
            target_pass = choice[4:]
            
            if target_id in waiting_hosts and waiting_hosts[target_id]["password"] == target_pass:
                # Извлекаем хост (теперь он занят)
                host_data = waiting_hosts.pop(target_id)
                host_sock = host_data["socket"]
                
                try:
                    conn.sendall(b"OK")
                    # Запускаем мосты
                    threading.Thread(target=bridge, args=(host_sock, conn), daemon=True).start()
                    threading.Thread(target=bridge, args=(conn, host_sock), daemon=True).start()
                    print(f"[*] Bridged Viewer to Host {target_id}")
                except:
                    print(f"[!] Failed to bridge {target_id}")
                    host_sock.close()
                    conn.close()
            else:
                conn.sendall(b"FAIL")
                conn.close()
    except Exception as e:
        print(f"[!] Error handling {addr}: {e}")

def start_relay():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # Позволяет перезапускать сервер без ожидания освобождения порта ОС
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(('0.0.0.0', 9001))
    server.listen(100)
    print("Relay Server Hub active on port 9001...")
    while True:
        conn, addr = server.accept()
        threading.Thread(target=handle_new_connection, args=(conn, addr)).start()

if __name__ == "__main__":
    start_relay()