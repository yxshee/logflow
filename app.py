import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import psutil
import time
import logging
from datetime import datetime
import threading
import os

# --- Configuration ---
LOG_FILE = 'system_performance.log'
DEFAULT_REFRESH_INTERVAL_SECONDS = 5
CPU_READ_INTERVAL_SECONDS = 0.5 # Interval for psutil.cpu_percent() for a more accurate reading

# --- Global Variables ---
monitoring_thread = None
monitoring_active = threading.Event() # Event to signal monitoring status
stop_monitoring_event = threading.Event() # Event to signal thread to stop
network_stats_initial = None # To store initial network counters

# --- Logger Setup ---
def setup_logger():
    """Configures and returns a logger instance."""
    logger = logging.getLogger('SystemPerformanceMonitorGUI')
    logger.setLevel(logging.INFO)
    
    # Prevent adding multiple handlers if function is called again
    if not logger.handlers:
        # File Handler
        file_handler = logging.FileHandler(LOG_FILE)
        file_handler.setLevel(logging.INFO)
        
        # Console Handler (optional, for debugging, can be removed for cleaner UI run)
        # console_handler = logging.StreamHandler()
        # console_handler.setLevel(logging.INFO)

        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
        file_handler.setFormatter(formatter)
        # console_handler.setFormatter(formatter)

        logger.addHandler(file_handler)
        # logger.addHandler(console_handler)
    return logger

logger = setup_logger()

# --- Core Monitoring Functions ---
def get_cpu_usage():
    """Retrieves system-wide CPU utilization percentage."""
    return psutil.cpu_percent(interval=CPU_READ_INTERVAL_SECONDS)

def get_memory_usage():
    """Retrieves memory usage statistics."""
    mem = psutil.virtual_memory()
    return {
        "total": mem.total,
        "available": mem.available,
        "percent": mem.percent,
        "used": mem.used,
        "free": mem.free
    }

def get_disk_partitions():
    """Retrieves all disk partitions."""
    partitions = []
    try:
        for part in psutil.disk_partitions(all=False): # all=False to ignore cd-roms, etc.
            if os.name == 'nt': # Windows: check for fixed drives
                 if 'fixed' in part.opts.lower() or part.fstype != '':
                    partitions.append(part.device)
            else: # Linux/MacOS: typically all listed are usable
                if part.fstype and 'loop' not in part.device: # Exclude loop devices
                    partitions.append(part.mountpoint)
    except Exception as e:
        logger.error(f"Error getting disk partitions: {e}")
    return sorted(list(set(partitions))) # Unique and sorted

def get_disk_usage(path):
    """Retrieves disk usage for a given path."""
    try:
        disk = psutil.disk_usage(path)
        return {
            "total": disk.total,
            "used": disk.used,
            "free": disk.free,
            "percent": disk.percent
        }
    except FileNotFoundError:
        logger.warning(f"Disk path not found: {path}")
        return None
    except Exception as e:
        logger.error(f"Error getting disk usage for {path}: {e}")
        return None

def get_network_stats():
    """Retrieves network I/O counters."""
    global network_stats_initial
    net_io = psutil.net_io_counters()
    if network_stats_initial is None:
        network_stats_initial = net_io # Store initial counters
    
    # Calculate bytes since application start (or last reset if we implement that)
    bytes_sent_since_start = net_io.bytes_sent - network_stats_initial.bytes_sent
    bytes_recv_since_start = net_io.bytes_recv - network_stats_initial.bytes_recv

    return {
        "bytes_sent_total": net_io.bytes_sent,
        "bytes_recv_total": net_io.bytes_recv,
        "bytes_sent_session": bytes_sent_since_start,
        "bytes_recv_session": bytes_recv_since_start,
        "packets_sent": net_io.packets_sent,
        "packets_recv": net_io.packets_recv
    }

# --- UI Update Functions ---
def update_ui_labels(app_instance):
    """Updates all UI labels and progress bars with current data."""
    if not monitoring_active.is_set():
        return # Don't update if monitoring is stopped

    try:
        # CPU
        cpu_percent = get_cpu_usage()
        app_instance.cpu_label.config(text=f"CPU Usage: {cpu_percent:.2f}%")
        app_instance.cpu_progress['value'] = cpu_percent
        
        # Memory
        mem_data = get_memory_usage()
        app_instance.mem_label.config(
            text=f"Memory: {mem_data['percent']:.2f}% "
                 f"(Used: {bytes_to_gb(mem_data['used']):.2f}GB / "
                 f"Total: {bytes_to_gb(mem_data['total']):.2f}GB / "
                 f"Available: {bytes_to_gb(mem_data['available']):.2f}GB)"
        )
        app_instance.mem_progress['value'] = mem_data['percent']

        # Disk
        selected_disk = app_instance.disk_var.get()
        if selected_disk and selected_disk != "Select Partition":
            disk_data = get_disk_usage(selected_disk)
            if disk_data:
                app_instance.disk_label.config(
                    text=f"Disk ({selected_disk}): {disk_data['percent']:.2f}% "
                         f"(Used: {bytes_to_gb(disk_data['used']):.2f}GB / "
                         f"Total: {bytes_to_gb(disk_data['total']):.2f}GB)"
                )
                app_instance.disk_progress['value'] = disk_data['percent']
            else:
                app_instance.disk_label.config(text=f"Disk ({selected_disk}): Error fetching data")
                app_instance.disk_progress['value'] = 0
        else:
            app_instance.disk_label.config(text="Disk: Select a partition")
            app_instance.disk_progress['value'] = 0

        # Network
        net_data = get_network_stats()
        app_instance.net_label.config(
            text=f"Network I/O (Session): "
                 f"Sent: {bytes_to_readable(net_data['bytes_sent_session'])} / "
                 f"Received: {bytes_to_readable(net_data['bytes_recv_session'])}"
        )
        
        # Log the data
        log_message = (
            f"CPU: {cpu_percent:.2f}%, "
            f"Mem: {mem_data['percent']:.2f}%, "
            f"Disk ({selected_disk if selected_disk else 'N/A'}): {disk_data['percent']:.2f}% (if selected), "
            f"Net Sent (Session): {bytes_to_readable(net_data['bytes_sent_session'])}, "
            f"Net Recv (Session): {bytes_to_readable(net_data['bytes_recv_session'])}"
        )
        logger.info(log_message)
        app_instance.update_status("Monitoring...")

    except Exception as e:
        logger.error(f"Error updating UI: {e}", exc_info=True)
        app_instance.update_status(f"Error: {e}")

    # Schedule next update if monitoring is still active
    if monitoring_active.is_set() and not stop_monitoring_event.is_set():
        refresh_interval_ms = int(app_instance.interval_var.get() * 1000)
        app_instance.root.after(refresh_interval_ms, lambda: update_ui_labels(app_instance))


# --- Helper Functions ---
def bytes_to_gb(bytes_val):
    """Converts bytes to gigabytes."""
    return bytes_val / (1024**3)

def bytes_to_readable(bytes_val):
    """Converts bytes to a human-readable string (KB, MB, GB)."""
    if bytes_val < 1024:
        return f"{bytes_val} B"
    elif bytes_val < 1024**2:
        return f"{bytes_val/1024:.2f} KB"
    elif bytes_val < 1024**3:
        return f"{bytes_val/(1024**2):.2f} MB"
    else:
        return f"{bytes_val/(1024**3):.2f} GB"

# --- Monitoring Thread Function ---
def monitoring_loop(app_instance):
    """The main loop for monitoring, runs in a separate thread."""
    global network_stats_initial
    network_stats_initial = psutil.net_io_counters() # Reset session network stats on start

    stop_monitoring_event.clear() # Ensure stop event is clear at start
    
    # Initial UI update call from the main thread via 'after'
    app_instance.root.after(0, lambda: update_ui_labels(app_instance))
    
    # The actual periodic updates are now scheduled by update_ui_labels itself
    # This loop just keeps the thread alive and checks the stop event.
    # Or, it could just trigger the first update_ui_labels and then rely on its self-scheduling.
    # For simplicity, we'll let update_ui_labels handle its own rescheduling.
    
    while not stop_monitoring_event.is_set():
        time.sleep(0.1) # Keep thread responsive to stop event

    logger.info("Monitoring thread finished.")


# --- Application Class ---
class SystemMonitorApp:
    def __init__(self, root_window):
        self.root = root_window
        self.root.title("System Performance Monitor")
        self.root.geometry("650x500") # Adjusted size
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing) # Handle window close

        # --- Styling ---
        style = ttk.Style()
        style.theme_use('clam') # Or 'alt', 'default', 'classic'
        style.configure("TProgressbar", thickness=20, troughcolor='#E0E0E0', background='#4CAF50')
        style.configure("TLabel", padding=5, font=('Helvetica', 10))
        style.configure("TButton", padding=5, font=('Helvetica', 10))
        style.configure("Header.TLabel", font=('Helvetica', 12, 'bold'))

        # --- Main Frame ---
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(expand=True, fill=tk.BOTH)

        # --- CPU ---
        ttk.Label(main_frame, text="CPU Usage", style="Header.TLabel").pack(pady=(0,5), anchor='w')
        self.cpu_label = ttk.Label(main_frame, text="CPU Usage: N/A")
        self.cpu_label.pack(fill=tk.X)
        self.cpu_progress = ttk.Progressbar(main_frame, orient=tk.HORIZONTAL, length=100, mode='determinate')
        self.cpu_progress.pack(fill=tk.X, pady=(0, 10))

        # --- Memory ---
        ttk.Label(main_frame, text="Memory Usage", style="Header.TLabel").pack(pady=(5,5), anchor='w')
        self.mem_label = ttk.Label(main_frame, text="Memory: N/A")
        self.mem_label.pack(fill=tk.X)
        self.mem_progress = ttk.Progressbar(main_frame, orient=tk.HORIZONTAL, length=100, mode='determinate')
        self.mem_progress.pack(fill=tk.X, pady=(0, 10))

        # --- Disk ---
        ttk.Label(main_frame, text="Disk Usage", style="Header.TLabel").pack(pady=(5,5), anchor='w')
        
        disk_frame = ttk.Frame(main_frame)
        disk_frame.pack(fill=tk.X)
        
        self.disk_var = tk.StringVar(value="Select Partition")
        self.disk_options = get_disk_partitions()
        if not self.disk_options: # Fallback if no partitions found
            self.disk_options = ["No partitions found"]
            self.disk_var.set(self.disk_options[0])

        self.disk_menu = ttk.OptionMenu(disk_frame, self.disk_var, self.disk_var.get(), *self.disk_options, command=self.on_disk_select)
        self.disk_menu.pack(side=tk.LEFT, padx=(0,10))
        
        self.disk_label = ttk.Label(disk_frame, text="Disk: Select a partition")
        self.disk_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        self.disk_progress = ttk.Progressbar(main_frame, orient=tk.HORIZONTAL, length=100, mode='determinate')
        self.disk_progress.pack(fill=tk.X, pady=(5, 10))

        # --- Network ---
        ttk.Label(main_frame, text="Network I/O", style="Header.TLabel").pack(pady=(5,5), anchor='w')
        self.net_label = ttk.Label(main_frame, text="Network I/O: N/A")
        self.net_label.pack(fill=tk.X, pady=(0,10))

        # --- Controls ---
        controls_frame = ttk.Frame(main_frame, padding=(0,10,0,0))
        controls_frame.pack(fill=tk.X)

        self.start_button = ttk.Button(controls_frame, text="Start Monitoring", command=self.start_monitoring)
        self.start_button.pack(side=tk.LEFT, padx=5)

        self.stop_button = ttk.Button(controls_frame, text="Stop Monitoring", command=self.stop_monitoring, state=tk.DISABLED)
        self.stop_button.pack(side=tk.LEFT, padx=5)

        ttk.Label(controls_frame, text="Refresh Interval (s):").pack(side=tk.LEFT, padx=(10, 5))
        self.interval_var = tk.DoubleVar(value=DEFAULT_REFRESH_INTERVAL_SECONDS)
        self.interval_entry = ttk.Entry(controls_frame, textvariable=self.interval_var, width=5)
        self.interval_entry.pack(side=tk.LEFT)
        
        self.open_log_button = ttk.Button(controls_frame, text="Open Log File", command=self.open_log_file)
        self.open_log_button.pack(side=tk.RIGHT, padx=5)


        # --- Status Bar ---
        self.status_var = tk.StringVar(value="Ready. Click 'Start Monitoring'.")
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W, padding=5)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
        logger.info("Application initialized.")

    def on_disk_select(self, selected_value):
        """Handles disk selection change. Forces an immediate UI update for disk info if monitoring."""
        self.disk_var.set(selected_value) # Ensure var is updated
        if monitoring_active.is_set(): # If monitoring, update disk info now
             # Temporarily fetch and update only disk part of UI
            disk_data = get_disk_usage(selected_value)
            if disk_data:
                self.disk_label.config(
                    text=f"Disk ({selected_value}): {disk_data['percent']:.2f}% "
                         f"(Used: {bytes_to_gb(disk_data['used']):.2f}GB / "
                         f"Total: {bytes_to_gb(disk_data['total']):.2f}GB)"
                )
                self.disk_progress['value'] = disk_data['percent']
            else:
                self.disk_label.config(text=f"Disk ({selected_value}): Error fetching data")
                self.disk_progress['value'] = 0


    def update_status(self, message):
        self.status_var.set(message)
        logger.info(f"Status: {message}")

    def start_monitoring(self):
        global monitoring_thread, monitoring_active, stop_monitoring_event
        if monitoring_active.is_set():
            messagebox.showinfo("Info", "Monitoring is already active.")
            return

        try:
            interval = self.interval_var.get()
            if interval <= 0:
                messagebox.showerror("Error", "Refresh interval must be greater than 0.")
                return
        except tk.TclError:
            messagebox.showerror("Error", "Invalid refresh interval. Please enter a number.")
            return
        
        monitoring_active.set()
        stop_monitoring_event.clear() # Clear stop event before starting thread
        
        # Disable start button and interval entry, enable stop button
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        self.interval_entry.config(state=tk.DISABLED)
        self.disk_menu.config(state=tk.DISABLED) # Disable disk selection during active monitoring for simplicity

        self.update_status("Starting monitoring...")
        monitoring_thread = threading.Thread(target=monitoring_loop, args=(self,), daemon=True)
        monitoring_thread.start()
        logger.info("Monitoring thread started.")
        
    def stop_monitoring(self):
        global monitoring_active, stop_monitoring_event
        if not monitoring_active.is_set():
            messagebox.showinfo("Info", "Monitoring is not active.")
            return

        self.update_status("Stopping monitoring...")
        stop_monitoring_event.set() # Signal the thread to stop
        monitoring_active.clear()   # Clear the active flag

        # Wait for the thread to finish (optional, with timeout)
        if monitoring_thread and monitoring_thread.is_alive():
            monitoring_thread.join(timeout=2.0) 
            if monitoring_thread.is_alive():
                 logger.warning("Monitoring thread did not terminate gracefully.")


        # Enable start button and interval entry, disable stop button
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.interval_entry.config(state=tk.NORMAL)
        self.disk_menu.config(state=tk.NORMAL)

        self.update_status("Monitoring stopped. Ready.")
        logger.info("Monitoring stopped by user action.")

    def open_log_file(self):
        try:
            if os.path.exists(LOG_FILE):
                # Try to open with default system editor
                if os.name == 'nt': # Windows
                    os.startfile(LOG_FILE)
                elif os.name == 'posix': # macOS, Linux
                    # Try common commands
                    if os.system(f'open "{LOG_FILE}"') != 0: # macOS
                        if os.system(f'xdg-open "{LOG_FILE}"') != 0: # Linux
                            messagebox.showinfo("Open Log", f"Could not automatically open log. Please find it at:\n{os.path.abspath(LOG_FILE)}")
                else:
                     messagebox.showinfo("Open Log", f"Log file at:\n{os.path.abspath(LOG_FILE)}")
            else:
                messagebox.showinfo("Open Log", "Log file does not exist yet. Start monitoring to create it.")
        except Exception as e:
            messagebox.showerror("Error", f"Could not open log file: {e}")
            logger.error(f"Error opening log file: {e}", exc_info=True)

    def on_closing(self):
        """Handles the window close event."""
        if monitoring_active.is_set():
            if messagebox.askyesno("Quit", "Monitoring is active. Are you sure you want to quit?"):
                self.stop_monitoring()
                self.root.destroy()
            else:
                return # Do not close
        else:
            self.root.destroy()
        
        logger.info("Application closed.")


# --- Main Execution ---
if __name__ == "__main__":
    # Check if psutil is installed (optional, as it's imported at the top)
    try:
        import psutil
    except ImportError:
        # This message box will appear before Tkinter root is initialized if psutil is missing.
        # For a better user experience, this check could be done after root init,
        # or the script could simply fail on import.
        root_check = tk.Tk()
        root_check.withdraw() # Hide the empty root window
        messagebox.showerror("Dependency Error", 
                             "The 'psutil' library is not installed.\n"
                             "Please install it by running: pip install psutil")
        root_check.destroy()
        exit(1)

    root = tk.Tk()
    app = SystemMonitorApp(root)
    root.mainloop()
