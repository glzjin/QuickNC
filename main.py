import os
import sys
import socket
import threading
import random
import base64
import secrets
import hashlib
from datetime import datetime, timedelta
from collections import defaultdict

# Constants
DEFAULT_PASSWORD = "114514"
PORT = int(os.environ.get('MAIN_PORT', 19999))
TIMEOUT = 600  # 10 minutes in seconds
RECV_TIMEOUT = 60  # 1 minute in seconds for recv operations
VERSION = 's'
MODULUS = 2**1279 - 1
CHALSIZE = 2**128
SOLVER_URL = os.environ.get('SOLVER_URL', 'https://buuoj.cn/files/312e52f8ec473c9d4f4f18581aa3c37c/pow.py')

# DDoS Protection
CONNECTION_LIMIT = 10  # Max connections per IP per minute
BLACKLIST_DURATION = 600  # 10 minutes
connection_counts = defaultdict(int)
blacklist = {}

try:
    import gmpy2
    HAVE_GMP = True
except ImportError:
    HAVE_GMP = False
    sys.stderr.write("[NOTICE] Running 10x slower, gotta go fast? pip3 install gmpy2\n")

def log_message(level, message):
    """
    Log a message with a specific level.
    Levels:
    + : Information
    ? : Inquiry
    - : Error
    * : Important
    """
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[QuickNC][{current_time}][{level}] {message}")

def format_message(level, message):
    """
    Format a message with a specific level.
    Levels:
    + : Information
    ? : Inquiry
    - : Error
    * : Important
    """
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return f"[QuickNC][{current_time}][{level}] {message}"

# POW Functions
def python_sloth_root(x, diff, p):
    exponent = (p + 1) // 4
    for i in range(diff):
        x = pow(x, exponent, p) ^ 1
    return x

def python_sloth_square(y, diff, p):
    for i in range(diff):
        y = pow(y ^ 1, 2, p)
    return y

def gmpy_sloth_root(x, diff, p):
    exponent = (p + 1) // 4
    for i in range(diff):
        x = gmpy2.powmod(x, exponent, p).bit_flip(0)
    return int(x)

def gmpy_sloth_square(y, diff, p):
    y = gmpy2.mpz(y)
    for i in range(diff):
        y = gmpy2.powmod(y.bit_flip(0), 2, p)
    return int(y)

def sloth_root(x, diff, p):
    if HAVE_GMP:
        return gmpy_sloth_root(x, diff, p)
    else:
        return python_sloth_root(x, diff, p)

def sloth_square(x, diff, p):
    if HAVE_GMP:
        return gmpy_sloth_square(x, diff, p)
    else:
        return python_sloth_square(x, diff, p)

def encode_number(num):
    size = (num.bit_length() // 24) * 3 + 3
    return str(base64.b64encode(num.to_bytes(size, 'big')), 'utf-8')

def decode_number(enc):
    return int.from_bytes(base64.b64decode(bytes(enc, 'utf-8')), 'big')

def decode_challenge(enc):
    dec = enc.split('.')
    if dec[0] != VERSION:
        raise Exception('Unknown challenge version')
    return list(map(decode_number, dec[1:]))

def encode_challenge(arr):
    return '.'.join([VERSION] + list(map(encode_number, arr)))

def get_challenge(diff):
    x = secrets.randbelow(CHALSIZE)
    return encode_challenge([diff, x])

def solve_challenge(chal):
    [diff, x] = decode_challenge(chal)
    y = sloth_root(x, diff, MODULUS)
    return encode_challenge([y])

def verify_challenge(chal, sol):
    [diff, x] = decode_challenge(chal)
    [y] = decode_challenge(sol)
    res = sloth_square(y, diff, MODULUS)
    return (x == res) or (MODULUS - x == res)

# Function to handle the connection
def handle_connection(client_socket, client_address):
    try:
        ip = client_address[0]

        # Check if IP is blacklisted
        if ip in blacklist:
            if datetime.now() < blacklist[ip]:
                client_socket.sendall(format_message("-", "You are blacklisted. Try again later.\n").encode())
                log_message("-", f"Blacklisted IP {ip} tried to connect.")
                client_socket.close()
                return
            else:
                del blacklist[ip]  # Remove from blacklist if time has passed
                log_message("+", f"IP {ip} removed from blacklist.")

        # Rate limiting
        connection_counts[ip] += 1
        if connection_counts[ip] > CONNECTION_LIMIT:
            blacklist[ip] = datetime.now() + timedelta(seconds=BLACKLIST_DURATION)
            client_socket.sendall(format_message("-", "Too many connections. You are now blacklisted.\n").encode())
            log_message("-", f"IP {ip} is now blacklisted due to too many connections.")
            client_socket.close()
            return

        # Set recv timeout
        client_socket.settimeout(RECV_TIMEOUT)

        # Step 1: Generate POW challenge
        difficulty = int(os.environ.get('CHALLENGE_DIFFICULTY', 5000))
        challenge = get_challenge(difficulty)
        client_socket.sendall(format_message("+", "Now please run this command to solve pow: \n").encode())
        client_socket.sendall(format_message("+", f"python3 <(curl -sSL {SOLVER_URL}) solve {challenge}\n").encode())
        log_message("+", f"Sent POW challenge to {ip}.")

        # Receive solution from client
        try:
            solution = client_socket.recv(1024).decode().strip()
        except socket.timeout:
            client_socket.sendall(format_message("-", "Recv timeout.\n").encode())
            log_message("-", f"Recv timeout from {ip}.")
            client_socket.close()
            return

        # Step 2: Verify POW solution
        if not verify_challenge(challenge, solution):
            client_socket.sendall(format_message("-", "POW solution incorrect.\n").encode())
            log_message("-", f"Incorrect POW solution from {ip}.")
            client_socket.close()
            return

        # Step 3: Verify password
        client_socket.sendall(format_message("?", "Enter password: ").encode())
        try:
            received_password = client_socket.recv(1024).decode().strip()
        except socket.timeout:
            client_socket.sendall(format_message("-", "Recv timeout.\n").encode())
            log_message("-", f"Recv timeout while waiting for password from {ip}.")
            client_socket.close()
            return

        password = os.environ.get('PASSWORD', DEFAULT_PASSWORD)
        if received_password != password:
            client_socket.sendall(format_message("-", "Password incorrect.\n").encode())
            log_message("-", f"Incorrect password attempt from {ip}.")
            client_socket.close()
            return

        # Step 4: Find an available port
        port_min = int(os.environ.get('PORT_MIN', 10000))
        port_max = int(os.environ.get('PORT_MAX', 20000))
        available_port = None
        for _ in range(100):
            port = random.randint(port_min, port_max)
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                if s.connect_ex(('0.0.0.0', port)) != 0:
                    available_port = port
                    break
        if available_port is None:
            client_socket.sendall(format_message("-", "No available port found.\n").encode())
            log_message("-", "No available port found.")
            client_socket.close()
            return

        # Step 5: Notify client of the new port
        client_socket.sendall(format_message("+", f"Connect to port {available_port}\n").encode())
        log_message("+", f"Notified {ip} to connect to port {available_port}.")

        # Step 6: Listen on the new port
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
            server_socket.bind(('0.0.0.0', available_port))
            server_socket.listen(1)
            server_socket.settimeout(TIMEOUT)

            log_message("+", f"Listening on port {available_port} for 10 minutes.")
            try:
                conn, addr = server_socket.accept()
                log_message("+", f"Connection from {addr}.")
                client_socket.sendall(format_message("+", f"Connection from {addr}\n").encode())

                # Start bidirectional communication
                def forward(source, destination):
                    try:
                        source.settimeout(RECV_TIMEOUT)
                        while True:
                            data = source.recv(1024)
                            if not data:
                                break
                            destination.sendall(data)
                    except socket.timeout:
                        log_message("-", "Recv timeout in forwarding.")
                    except Exception as e:
                        log_message("-", f"Exception in forwarding: {e}")
                    finally:
                        source.close()
                        destination.close()

                # Create threads for bidirectional communication
                client_to_server = threading.Thread(target=forward, args=(client_socket, conn))
                server_to_client = threading.Thread(target=forward, args=(conn, client_socket))

                client_to_server.start()
                server_to_client.start()

                client_to_server.join()
                server_to_client.join()

            except socket.timeout:
                log_message("-", "Timeout, closing connection.")
            finally:
                server_socket.close()
                client_socket.close()

    except Exception as e:
        log_message("-", f"Exception: {e}")
    finally:
        client_socket.close()
        # Reset connection count after handling
        connection_counts[ip] -= 1

# Main function to start the server
def main():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
        server_socket.bind(('0.0.0.0', PORT))
        server_socket.listen(5)
        log_message("+", f"Server listening on port {PORT}")

        while True:
            client_socket, addr = server_socket.accept()
            log_message("+", f"Accepted connection from {addr}")
            client_handler = threading.Thread(target=handle_connection, args=(client_socket, addr))
            client_handler.start()

if __name__ == "__main__":
    main()
