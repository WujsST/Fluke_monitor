import socket
import time
import tkinter as tk
from tkinter import font
from tkinter import messagebox
import threading

# --- DOMYŚLNE USTAWIENIA MIERNIKA ---
DEFAULT_MIERNIK_IP = "192.168.0.188"  # Domyślne IP miernika
DEFAULT_MIERNIK_PORT = 3490
# -----------------------------

class Fluke8846A:
    """Klasa do obsługi połączenia z miernikiem (teraz z funkcją 'retry')"""

    def __init__(self, ip, port):
        self.ip = ip
        self.port = port
        self.sock = None
        self.lock = threading.Lock()

    def connect(self):
        """Łączy się z miernikiem, próbując 3 razy w razie niepowodzenia."""

        # --- NOWA LOGIKA PONOWNEJ PRÓBY ---
        max_retries = 3
        for attempt in range(max_retries):
            try:
                print(f"Próba połączenia {attempt + 1}/{max_retries}...")
                self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.sock.settimeout(2) # Krótszy timeout na próbę
                self.sock.connect((self.ip, self.port))

                # Jeśli się udało, kontynuuj jak wcześniej
                self.sock.sendall(b"syst:rem\n")
                time.sleep(0.5)

                print("Połączono. Przełączono w tryb zdalny.")
                return True # Wyjdź z funkcji z sukcesem

            except socket.error as e:
                print(f"Próba {attempt + 1} nieudana: {e}")
                if attempt < max_retries - 1:
                    time.sleep(1) # Odczekaj 1s przed kolejną próbą
                else:
                    # To była ostatnia próba, pokaż błąd
                    messagebox.showerror("Błąd Połączenia", f"Nie można połączyć z miernikiem po {max_retries} próbach: {e}")
                    return False

        # To się nie powinno zdarzyć, ale na wszelki wypadek
        return False

    def disconnect(self):
        """Bezpiecznie rozłącza miernik."""
        if self.sock:
            try:
                with self.lock:
                    self.sock.settimeout(1.0)
                    self.sock.sendall(b"syst:loc\n")
                self.sock.close()
            except socket.error as e:
                print(f"Ignorowanie błędu przy rozłączaniu (to normalne): {e}")
            self.sock = None

    def ask_command(self, cmd):
        """Wysyła komendę i zwraca odpowiedź (bezpieczne dla wątków)"""
        if not self.sock:
            return None

        try:
            with self.lock:
                self.sock.settimeout(10)
                self.sock.sendall(f"{cmd}\n".encode())
                response = self.sock.recv(1024).decode().strip()
            return response
        except socket.timeout:
            print(f"Błąd polecenia '{cmd}': TIMEOUT. Miernik nie odpowiedział na czas.")
            return None
        except socket.error as e:
            print(f"Błąd polecenia '{cmd}': {e}")
            return None

# --- Okno konfiguracyjne połączenia ---

class ConnectionDialog(tk.Toplevel):
    """Okno do konfiguracji i połączenia z miernikiem"""

    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.fluke = None
        self.connected = False

        self.title("Konfiguracja połączenia - Fluke 8846A")
        self.geometry("400x250")
        self.resizable(False, False)

        # Centrowanie okna
        self.update_idletasks()
        x = (self.winfo_screenwidth() // 2) - (400 // 2)
        y = (self.winfo_screenheight() // 2) - (250 // 2)
        self.geometry(f"400x250+{x}+{y}")

        # Czcionki
        label_font = font.Font(family="Helvetica", size=10)
        button_font = font.Font(family="Helvetica", size=11, weight="bold")
        status_font = font.Font(family="Helvetica", size=9)

        # Nagłówek
        header = tk.Label(self, text="Konfiguracja połączenia z miernikiem",
                         font=font.Font(family="Helvetica", size=12, weight="bold"))
        header.pack(pady=15)

        # Ramka na pola
        input_frame = tk.Frame(self)
        input_frame.pack(pady=10)

        # IP Address
        tk.Label(input_frame, text="Adres IP:", font=label_font).grid(row=0, column=0, sticky="e", padx=10, pady=8)
        self.ip_entry = tk.Entry(input_frame, font=label_font, width=20)
        self.ip_entry.grid(row=0, column=1, padx=10, pady=8)
        self.ip_entry.insert(0, DEFAULT_MIERNIK_IP)

        # Port
        tk.Label(input_frame, text="Port:", font=label_font).grid(row=1, column=0, sticky="e", padx=10, pady=8)
        self.port_entry = tk.Entry(input_frame, font=label_font, width=20)
        self.port_entry.grid(row=1, column=1, padx=10, pady=8)
        self.port_entry.insert(0, str(DEFAULT_MIERNIK_PORT))

        # Status label
        self.status_label = tk.Label(self, text="Gotowy do połączenia",
                                     font=status_font, fg="blue")
        self.status_label.pack(pady=10)

        # Przycisk połącz
        self.connect_button = tk.Button(self, text="POŁĄCZ", font=button_font,
                                       bg="#4CAF50", fg="white",
                                       command=self.attempt_connection,
                                       width=15, height=1)
        self.connect_button.pack(pady=10)

        # Blokowanie zamknięcia okna bez połączenia
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def attempt_connection(self):
        """Próba połączenia z miernikiem"""
        ip = self.ip_entry.get().strip()
        port = self.port_entry.get().strip()

        # Walidacja
        if not ip:
            messagebox.showerror("Błąd", "Podaj adres IP miernika!")
            return

        try:
            port = int(port)
        except ValueError:
            messagebox.showerror("Błąd", "Port musi być liczbą całkowitą!")
            return

        # Wyłączenie przycisku podczas łączenia
        self.connect_button.config(state=tk.DISABLED)
        self.status_label.config(text="Łączenie z miernikiem...", fg="orange")
        self.update()

        # Tworzenie obiektu Fluke i próba połączenia
        self.fluke = Fluke8846A(ip, port)
        success = self.fluke.connect()

        if success:
            self.status_label.config(text="✓ Połączono pomyślnie!", fg="green")
            self.connected = True
            self.update()
            time.sleep(0.5)
            self.destroy()  # Zamknij okno konfiguracji
        else:
            self.status_label.config(text="✗ Nie udało się połączyć", fg="red")
            self.connect_button.config(state=tk.NORMAL)
            self.fluke = None

    def on_close(self):
        """Obsługa zamknięcia okna"""
        if not self.connected:
            if messagebox.askokcancel("Zakończ", "Czy chcesz zakończyć bez połączenia?"):
                self.parent.destroy()
        else:
            self.destroy()

# --- Reszta kodu (klasa App, itp.) pozostaje bez zmian ---

class App(tk.Tk):
    """Główna klasa aplikacji UI"""

    def __init__(self, fluke_controller):
        super().__init__()
        self.fluke = fluke_controller

        self.is_running = False
        self.measurement_thread = None

        self.current_command = "meas:volt:dc?"
        self.current_unit = "V"

        self.title("Kontroler Fluke 8846A")
        # Zwiększamy lekko wysokość okna na nowe przyciski
        self.geometry("400x450")

        self.result_font = font.Font(family="Courier", size=28, weight="bold")
        self.button_font = font.Font(family="Helvetica", size=12)

        self.result_label = tk.Label(self, text="---.---", font=self.result_font, bg="black", fg="green", pady=20)
        self.result_label.pack(fill=tk.X, expand=True, padx=10, pady=10)

        self.mode_label = tk.Label(self, text="Tryb: Rozłączono", font=self.button_font)
        self.mode_label.pack(pady=5)

        # --- Ramka na przyciski trybów (TERAZ 3x2) ---
        mode_frame = tk.Frame(self)
        mode_frame.pack(pady=10)

        # Rząd 1
        tk.Button(mode_frame, text="Napięcie DC (V)", font=self.button_font, command=lambda: self.set_mode("DCV", "meas:volt:dc?", "V")).grid(row=0, column=0, padx=5, pady=5, sticky="ew")
        tk.Button(mode_frame, text="Napięcie AC (V)", font=self.button_font, command=lambda: self.set_mode("ACV", "meas:volt:ac?", "V")).grid(row=0, column=1, padx=5, pady=5, sticky="ew")

        # Rząd 2
        tk.Button(mode_frame, text="Prąd DC (A)", font=self.button_font, command=lambda: self.set_mode("DCA", "meas:curr:dc?", "A")).grid(row=1, column=0, padx=5, pady=5, sticky="ew")
        # --- NOWY PRZYCISK ---
        tk.Button(mode_frame, text="Prąd AC (A)", font=self.button_font, command=lambda: self.set_mode("ACA", "meas:curr:ac?", "A")).grid(row=1, column=1, padx=5, pady=5, sticky="ew")

        # Rząd 3
        tk.Button(mode_frame, text="Rezystancja (Ω)", font=self.button_font, command=lambda: self.set_mode("OHM", "meas:res?", "Ω")).grid(row=2, column=0, padx=5, pady=5, sticky="ew")
        # --- NOWY PRZYCISK (BONUS) ---
        tk.Button(mode_frame, text="Częstotliwość (Hz)", font=self.button_font, command=lambda: self.set_mode("FREQ", "meas:freq?", "Hz")).grid(row=2, column=1, padx=5, pady=5, sticky="ew")

        # --- Ramka na przyciski START/STOP ---
        control_frame = tk.Frame(self)
        control_frame.pack(fill=tk.X, padx=10, pady=10)

        self.start_button = tk.Button(control_frame, text="START", font=self.button_font, bg="#4CAF50", fg="white", command=self.start_measurement)
        self.start_button.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5)

        self.stop_button = tk.Button(control_frame, text="STOP", font=self.button_font, bg="#f44336", fg="white", command=self.stop_measurement, state=tk.DISABLED)
        self.stop_button.pack(side=tk.RIGHT, expand=True, fill=tk.X, padx=5)

        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        # Ustaw domyślny tryb (miernik już połączony)
        self.set_initial_mode()

    def set_initial_mode(self):
        """Ustawia początkowy tryb pomiaru po połączeniu"""
        try:
            idn = self.fluke.ask_command("*IDN?")
            if idn:
                model = idn.split(',')[1] if ',' in idn else "Fluke 8846A"
                self.mode_label.config(text=f"Połączono: {model}")
            else:
                self.mode_label.config(text="Połączono")
        except:
            self.mode_label.config(text="Połączono")

        self.set_mode("DCV", "meas:volt:dc?", "V")

    def set_mode(self, name, command, unit):
        if self.is_running:
            messagebox.showwarning("Stop", "Najpierw zatrzymaj pomiary, aby zmienić tryb.")
            return

        self.current_command = command
        self.current_unit = unit
        self.mode_label.config(text=f"Tryb: {name}")

    def start_measurement(self):
        if self.is_running:
            return

        self.is_running = True
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)

        self.measurement_thread = threading.Thread(target=self.measurement_loop, daemon=True)
        self.measurement_thread.start()

    def stop_measurement(self):
        self.is_running = False
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)

    def measurement_loop(self):
        while self.is_running:
            raw_data = self.fluke.ask_command(self.current_command)

            if raw_data is None:
                self.is_running = False
                self.after(0, self.handle_connection_error)
                break

            try:
                value = float(raw_data)
                formatted_value = f"{value:.6f} {self.current_unit}"
                self.after(0, self.update_label, formatted_value)

            except ValueError:
                self.after(0, self.update_label, f"{raw_data} {self.current_unit}")

            time.sleep(0.5)

        self.after(0, self.stop_measurement)

    def update_label(self, text):
        self.result_label.config(text=text)

    def handle_connection_error(self):
        messagebox.showerror("Błąd Połączenia", "Połączenie z miernikiem zostało zerwane lub nie odpowiada.")
        self.stop_measurement()
        self.start_button.config(state=tk.DISABLED)
        self.mode_label.config(text="Tryb: ROZŁĄCZONO")

    def on_closing(self):
        if messagebox.askokcancel("Zakończ", "Czy na pewno chcesz zakończyFć i rozłączyć miernik?"):
            self.is_running = False
            time.sleep(0.1)
            print("Rozłączanie miernika...")
            self.fluke.disconnect()
            self.destroy()

# --- Główna część programu ---
if __name__ == "__main__":
    # Tworzenie głównego niewidocznego okna root
    root = tk.Tk()
    root.withdraw()  # Ukryj główne okno

    # Pokaż okno konfiguracji
    config_dialog = ConnectionDialog(root)
    root.wait_window(config_dialog)  # Czekaj na zamknięcie okna konfiguracji

    # Sprawdź czy połączenie się udało
    if config_dialog.connected and config_dialog.fluke:
        # Zniszcz niewidzialne okno root
        root.destroy()

        # Utwórz główne okno aplikacji z połączonym miernikiem
        app = App(config_dialog.fluke)
        app.mainloop()
    else:
        # Użytkownik anulował lub nie udało się połączyć
        root.destroy()
        print("Program zakończony bez połączenia.")
