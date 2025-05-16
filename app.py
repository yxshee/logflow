import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import psutil
import time
import logging
from datetime import datetime, timedelta
import threading
import os

# --- Configuration ---
LOG_FILE = 'system_performance.log'
DEFAULT_REFRESH_INTERVAL_SECONDS = 3
CPU_READ_INTERVAL_SECONDS = 0.5 # For overall CPU
CPU_CORE_READ_INTERVAL_SECONDS = 0.1 # For per-core CPU, can be faster

# --- Global Variables ---
monitoring_thread = None
monitoring_active = threading.Event()
stop_monitoring_event = threading.Event()
network_stats_initial = None

# --- Color Palette ---
COLOR_BACKGROUND = "#F0F0F0"
COLOR_FRAME_BG = "#FFFFFF"
COLOR_TEXT = "#333333"
COLOR_HEADER_TEXT = "#003366"
COLOR_ACCENT_PRIMARY = "#0078D4"
COLOR_PROGRESS_TROUGH = "#E0E0E0"

# --- Logger Setup ---
def setup_logger():
    logger = logging.getLogger('SystemPerformanceMonitorGUI')
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        file_handler = logging.FileHandler(LOG_FILE)
        file_handler.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    return logger

logger = setup_logger()

# --- Core Monitoring Functions ---
def get_cpu_usage():
    return psutil.cpu_percent(interval=CPU_READ_INTERVAL_SECONDS)

def get_per_core_cpu_usage():
    return psutil.cpu_percent(interval=CPU_CORE_READ_INTERVAL_SECONDS, percpu=True)

def get_cpu_frequency():
    try:
        freq = psutil.cpu_freq()
        if freq:
            return {"current": freq.current, "min": freq.min, "max": freq.max}
    except Exception: # Handles cases where it might not be supported or accessible
        pass
    return None

def get_cpu_stats():
    try:
        stats = psutil.cpu_stats()
        return {"ctx_switches": stats.ctx_switches, "interrupts": stats.interrupts, "soft_interrupts": stats.soft_interrupts}
    except Exception:
        return None


def get_memory_usage():
    mem = psutil.virtual_memory()
    return {"total": mem.total, "available": mem.available, "percent": mem.percent, "used": mem.used, "free": mem.free}

def get_swap_memory_usage():
    swap = psutil.swap_memory()
    return {"total": swap.total, "used": swap.used, "free": swap.free, "percent": swap.percent, "sin": swap.sin, "sout": swap.sout}


def get_disk_partitions():
    partitions = []
    try:
        for part in psutil.disk_partitions(all=False):
            if os.name == 'nt':
                 if 'fixed' in part.opts.lower() or part.fstype != '':
                    partitions.append(part.device)
            else: 
                if part.fstype and 'loop' not in part.device:
                    partitions.append(part.mountpoint)
    except Exception as e:
        logger.error(f"Error getting disk partitions: {e}")
    return sorted(list(set(partitions)))

def get_disk_usage(path):
    try:
        disk = psutil.disk_usage(path)
        return {"total": disk.total, "used": disk.used, "free": disk.free, "percent": disk.percent}
    except FileNotFoundError:
        return None
    except Exception as e:
        logger.error(f"Error getting disk usage for {path}: {e}")
        return None

def get_disk_io_counters():
    try:
        io = psutil.disk_io_counters(perdisk=False) # System-wide
        if io:
            return {"read_count": io.read_count, "write_count": io.write_count, 
                    "read_bytes": io.read_bytes, "write_bytes": io.write_bytes,
                    "read_time": getattr(io, 'read_time', 0), # May not be on all platforms
                    "write_time": getattr(io, 'write_time', 0)} # May not be on all platforms
    except Exception:
        pass
    return None


def get_network_stats():
    global network_stats_initial
    net_io = psutil.net_io_counters()
    if network_stats_initial is None:
        network_stats_initial = net_io
    
    bytes_sent_since_start = net_io.bytes_sent - network_stats_initial.bytes_sent
    bytes_recv_since_start = net_io.bytes_recv - network_stats_initial.bytes_recv

    return {
        "bytes_sent_session": bytes_sent_since_start, "bytes_recv_session": bytes_recv_since_start,
    }

def get_process_count():
    return len(psutil.pids())

def get_boot_time():
    boot_timestamp = psutil.boot_time()
    return datetime.fromtimestamp(boot_timestamp)

def get_system_uptime():
    boot_time_dt = get_boot_time()
    now = datetime.now()
    uptime_delta = now - boot_time_dt
    return uptime_delta

def get_cpu_temperatures():
    temps = {}
    try:
        sensor_temps = psutil.sensors_temperatures()
        if not sensor_temps:
            return {"error": "Not supported by OS or no sensors found."}

        # Prioritize 'coretemp' or 'k10temp' for CPU, common on Linux
        # For other OS or more generic, look for labels containing 'CPU' or 'Core'
        priority_keys = ['coretemp', 'k10temp', 'cpu_thermal', 'acpitz'] # acpitz can sometimes be CPU
        
        for name, entries in sensor_temps.items():
            if name in priority_keys:
                for entry in entries:
                    label = entry.label if entry.label else name
                    temps[f"{label} ({name})"] = entry.current
            else: # More generic check for other sensors
                for entry in entries:
                    if "cpu" in entry.label.lower() or "core" in entry.label.lower() or \
                       "package" in entry.label.lower() or "socket" in entry.label.lower():
                        label = entry.label if entry.label else name
                        temps[f"{label} ({name})"] = entry.current
        
        if not temps and sensor_temps: # If no specific CPU temps found, show first available as a fallback
            first_sensor_name = list(sensor_temps.keys())[0]
            first_sensor_entries = sensor_temps[first_sensor_name]
            if first_sensor_entries:
                 temps[f"{first_sensor_entries[0].label or first_sensor_name} (Fallback)"] = first_sensor_entries[0].current


        return temps if temps else {"info": "No CPU temperature sensors identified."}

    except AttributeError: # sensors_temperatures might not exist
        return {"error": "psutil.sensors_temperatures() not available on this system."}
    except Exception as e:
        logger.error(f"Error getting CPU temperatures: {e}")
        return {"error": str(e)}


# --- UI Update Functions ---
def update_ui_labels(app_instance):
    if not monitoring_active.is_set():
        return

    try:
        # Overall CPU
        cpu_percent = get_cpu_usage()
        app_instance.cpu_label.config(text=f"Overall Usage: {cpu_percent:.2f}%")
        app_instance.cpu_progress['value'] = cpu_percent
        
        # Per-Core CPU
        core_usages = get_per_core_cpu_usage()
        core_text = "Per Core: " + " | ".join([f"C{i}: {usage:.1f}%" for i, usage in enumerate(core_usages)])
        app_instance.cpu_cores_label.config(text=core_text)

        # CPU Frequency
        freq = get_cpu_frequency()
        if freq:
            freq_text = f"Frequency: {freq['current']:.0f} MHz"
            if freq['min'] and freq['max']:
                freq_text += f" (Min: {freq['min']:.0f} MHz, Max: {freq['max']:.0f} MHz)"
            app_instance.cpu_freq_label.config(text=freq_text)
        else:
            app_instance.cpu_freq_label.config(text="Frequency: N/A")

        # CPU Stats
        cpu_s = get_cpu_stats()
        if cpu_s:
            stats_text = (f"Ctx Switches: {cpu_s['ctx_switches']:,} | "
                          f"Interrupts: {cpu_s['interrupts']:,} | "
                          f"Soft Interrupts: {cpu_s['soft_interrupts']:,}")
            app_instance.cpu_extra_stats_label.config(text=stats_text)
        else:
            app_instance.cpu_extra_stats_label.config(text="CPU Stats: N/A")


        # Memory
        mem_data = get_memory_usage()
        app_instance.mem_label.config(
            text=f"{mem_data['percent']:.2f}% "
                 f"(Used: {bytes_to_gb(mem_data['used']):.2f}GB / "
                 f"Total: {bytes_to_gb(mem_data['total']):.2f}GB)"
        )
        app_instance.mem_progress['value'] = mem_data['percent']

        # Swap Memory
        swap_data = get_swap_memory_usage()
        if swap_data['total'] > 0: # Only show if swap is configured
            app_instance.swap_label.config(
                text=f"{swap_data['percent']:.2f}% "
                     f"(Used: {bytes_to_readable(swap_data['used'])} / "
                     f"Total: {bytes_to_readable(swap_data['total'])})"
            )
            app_instance.swap_progress['value'] = swap_data['percent']
            app_instance.swap_label.grid() # Make visible
            app_instance.swap_progress.grid() # Make visible
        else:
            app_instance.swap_label.grid_remove() # Hide if no swap
            app_instance.swap_progress.grid_remove() # Hide if no swap


        # Disk (Selected)
        selected_disk = app_instance.disk_var.get()
        disk_display_text = "Disk: Select a partition"
        disk_percent_val = 0
        if selected_disk and selected_disk != "Select Partition" and selected_disk != "No partitions found":
            disk_data = get_disk_usage(selected_disk)
            if disk_data:
                disk_display_text = (f"{selected_disk}: {disk_data['percent']:.2f}% "
                                     f"(Used: {bytes_to_gb(disk_data['used']):.2f}GB / "
                                     f"Total: {bytes_to_gb(disk_data['total']):.2f}GB)")
                disk_percent_val = disk_data['percent']
            else:
                disk_display_text = f"Disk ({selected_disk}): Error"
        app_instance.disk_label.config(text=disk_display_text)
        app_instance.disk_progress['value'] = disk_percent_val
        
        # System-wide Disk I/O
        disk_io = get_disk_io_counters()
        if disk_io:
            disk_io_text = (f"Reads: {disk_io['read_count']:,} ({bytes_to_readable(disk_io['read_bytes'])}) | "
                            f"Writes: {disk_io['write_count']:,} ({bytes_to_readable(disk_io['write_bytes'])})")
            app_instance.disk_io_label.config(text=disk_io_text)
        else:
            app_instance.disk_io_label.config(text="Disk I/O (System): N/A")


        # Network
        net_data = get_network_stats()
        app_instance.net_label.config(
            text=f"Sent (Session): {bytes_to_readable(net_data['bytes_sent_session'])} / "
                 f"Received (Session): {bytes_to_readable(net_data['bytes_recv_session'])}"
        )

        # Process Count
        app_instance.process_count_label.config(text=f"Processes: {get_process_count()}")

        # System Uptime
        uptime = get_system_uptime()
        app_instance.uptime_label.config(text=f"Uptime: {format_timedelta(uptime)}")

        # CPU Temperatures
        temps = get_cpu_temperatures()
        if "error" in temps:
            app_instance.cpu_temp_label.config(text=f"CPU Temp: {temps['error']}")
        elif "info" in temps:
             app_instance.cpu_temp_label.config(text=f"CPU Temp: {temps['info']}")
        elif temps:
            temp_str = "CPU Temp: " + " | ".join([f"{name}: {temp}°C" for name, temp in temps.items()])
            app_instance.cpu_temp_label.config(text=temp_str)
        else:
            app_instance.cpu_temp_label.config(text="CPU Temp: N/A")
        
        # Log the data
        log_message = (
            f"CPU: {cpu_percent:.2f}%, Cores: {core_usages}, Freq: {freq['current'] if freq else 'N/A'}MHz, "
            f"Mem: {mem_data['percent']:.2f}%, Swap: {swap_data['percent'] if swap_data['total']>0 else 'N/A'}%, "
            f"Disk ({selected_disk if selected_disk and selected_disk not in ['Select Partition', 'No partitions found'] else 'N/A'}): {disk_percent_val:.2f}%, "
            f"DiskIO Reads: {disk_io['read_count'] if disk_io else 'N/A'}, DiskIO Writes: {disk_io['write_count'] if disk_io else 'N/A'}, "
            f"NetSent(Session): {bytes_to_readable(net_data['bytes_sent_session'])}, NetRecv(Session): {bytes_to_readable(net_data['bytes_recv_session'])}, "
            f"Processes: {get_process_count()}, Uptime: {format_timedelta(uptime)}"
        )
        logger.info(log_message)
        app_instance.update_status("Monitoring...")

    except Exception as e:
        logger.error(f"Error updating UI: {e}", exc_info=True)
        app_instance.update_status(f"Error: {str(e)[:50]}...")

    if monitoring_active.is_set() and not stop_monitoring_event.is_set():
        try:
            refresh_interval_ms = int(float(app_instance.interval_var.get()) * 1000)
            if refresh_interval_ms <=0: refresh_interval_ms = 1000 
            app_instance.root.after(refresh_interval_ms, lambda: update_ui_labels(app_instance))
        except ValueError: 
             app_instance.root.after(int(DEFAULT_REFRESH_INTERVAL_SECONDS * 1000), lambda: update_ui_labels(app_instance))


# --- Helper Functions ---
def bytes_to_gb(bytes_val):
    return bytes_val / (1024**3)

def bytes_to_readable(bytes_val):
    if bytes_val < 1024: return f"{bytes_val} B"
    elif bytes_val < 1024**2: return f"{bytes_val/1024:.2f} KB"
    elif bytes_val < 1024**3: return f"{bytes_val/(1024**2):.2f} MB"
    else: return f"{bytes_val/(1024**3):.2f} GB"

def format_timedelta(td):
    """Formats a timedelta object into a human-readable string D H:M:S."""
    days = td.days
    hours, remainder = divmod(td.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{days}d {hours:02}:{minutes:02}:{seconds:02}"


# --- Monitoring Thread Function ---
def monitoring_loop(app_instance):
    global network_stats_initial
    network_stats_initial = psutil.net_io_counters() 
    stop_monitoring_event.clear()
    app_instance.root.after(0, lambda: update_ui_labels(app_instance)) 
    while not stop_monitoring_event.is_set():
        time.sleep(0.1) 
    logger.info("Monitoring thread finished.")

# --- Application Class ---
class SystemMonitorApp:
    def __init__(self, root_window):
        self.root = root_window
        self.root.title("System Performance Monitor Pro")
        self.root.geometry("850x750") # Increased size for more tools
        self.root.configure(bg=COLOR_BACKGROUND)
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        # --- Styling ---
        style = ttk.Style()
        style.theme_use('alt') 

        style.configure("TFrame", background=COLOR_FRAME_BG)
        style.configure("Section.TFrame", background=COLOR_FRAME_BG, relief=tk.RIDGE, borderwidth=1)
        
        style.configure("TLabel", background=COLOR_FRAME_BG, foreground=COLOR_TEXT, padding=3, font=('Helvetica', 10))
        style.configure("Header.TLabel", background=COLOR_FRAME_BG, foreground=COLOR_HEADER_TEXT, font=('Helvetica', 14, 'bold'), padding=(5, 8, 5, 5))
        style.configure("SubHeader.TLabel", background=COLOR_FRAME_BG, foreground=COLOR_TEXT, font=('Helvetica', 10), padding=(5,1,5,1)) # Slightly smaller padding
        style.configure("Small.TLabel", background=COLOR_FRAME_BG, foreground=COLOR_TEXT, font=('Helvetica', 9), padding=(5,1,5,1))
        
        style.configure("RefreshLabel.TLabel", background=COLOR_BACKGROUND, foreground=COLOR_TEXT, font=('Helvetica', 10), padding=(5,1,5,1))
        style.configure("StatusBar.TLabel", background=COLOR_FRAME_BG, foreground=COLOR_TEXT, font=('Helvetica', 9), padding=5)

        style.configure("TProgressbar", thickness=20, troughcolor=COLOR_PROGRESS_TROUGH, background=COLOR_ACCENT_PRIMARY)
        
        style.configure("TButton", foreground=COLOR_FRAME_BG, background=COLOR_ACCENT_PRIMARY, font=('Helvetica', 10, 'bold'), padding=(8, 4))
        style.map("TButton",
            background=[('active', '#005A9E'), ('disabled', '#B0B0B0')], 
            foreground=[('active', COLOR_FRAME_BG), ('disabled', '#F0F0F0')]
        )
        style.configure("Stop.TButton", background="#D9534F", foreground=COLOR_FRAME_BG) 
        style.map("Stop.TButton", 
                  background=[('active', "#C9302C"), ('disabled', '#E0B0B0')],
                  foreground=[('active', COLOR_FRAME_BG), ('disabled', '#F5F5F5')]
        )

        style.configure("TOptionMenu", font=('Helvetica', 10), padding=3)
        style.configure("TEntry", font=('Helvetica', 10), padding=3)

        # --- Main Container Frame ---
        main_container = ttk.Frame(self.root, style="TFrame", padding=10)
        main_container.pack(expand=True, fill=tk.BOTH)

        # Function to create a section frame
        def create_section(parent, title_text, **kwargs):
            section_frame = ttk.Frame(parent, style="Section.TFrame", padding=8, **kwargs)
            section_frame.pack(fill=tk.X, pady=4)
            ttk.Label(section_frame, text=title_text, style="Header.TLabel").pack(anchor='w', pady=(0,3))
            return section_frame

        # --- CPU Section ---
        cpu_section = create_section(main_container, "CPU Information")
        self.cpu_label = ttk.Label(cpu_section, text="Overall Usage: N/A", style="SubHeader.TLabel")
        self.cpu_label.pack(fill=tk.X)
        self.cpu_progress = ttk.Progressbar(cpu_section, orient=tk.HORIZONTAL, length=100, mode='determinate')
        self.cpu_progress.pack(fill=tk.X, pady=(2,4))
        self.cpu_cores_label = ttk.Label(cpu_section, text="Per Core: N/A", style="Small.TLabel", wraplength=700)
        self.cpu_cores_label.pack(fill=tk.X)
        self.cpu_freq_label = ttk.Label(cpu_section, text="Frequency: N/A", style="Small.TLabel")
        self.cpu_freq_label.pack(fill=tk.X)
        self.cpu_extra_stats_label = ttk.Label(cpu_section, text="CPU Stats: N/A", style="Small.TLabel", wraplength=700)
        self.cpu_extra_stats_label.pack(fill=tk.X)
        self.cpu_temp_label = ttk.Label(cpu_section, text="CPU Temp: N/A", style="Small.TLabel", wraplength=700)
        self.cpu_temp_label.pack(fill=tk.X)


        # --- Memory Section ---
        mem_section = create_section(main_container, "Memory Usage")
        self.mem_label = ttk.Label(mem_section, text="RAM: N/A", style="SubHeader.TLabel")
        self.mem_label.pack(fill=tk.X)
        self.mem_progress = ttk.Progressbar(mem_section, orient=tk.HORIZONTAL, length=100, mode='determinate')
        self.mem_progress.pack(fill=tk.X, pady=(2,4))
        
        self.swap_label = ttk.Label(mem_section, text="Swap: N/A", style="SubHeader.TLabel")
        self.swap_label.pack(fill=tk.X) # pack, will be hidden/shown by grid_remove/grid
        self.swap_label.pack_forget() # Start hidden
        self.swap_progress = ttk.Progressbar(mem_section, orient=tk.HORIZONTAL, length=100, mode='determinate')
        self.swap_progress.pack(fill=tk.X, pady=(2,0)) # pack, will be hidden/shown
        self.swap_progress.pack_forget() # Start hidden


        # --- Disk Section ---
        disk_section = create_section(main_container, "Disk Usage & I/O")
        disk_controls_frame = ttk.Frame(disk_section, style="TFrame") 
        disk_controls_frame.pack(fill=tk.X, pady=(0,3))
        self.disk_var = tk.StringVar(value="Select Partition")
        self.disk_options = get_disk_partitions()
        if not self.disk_options:
            self.disk_options = ["No partitions found"]
            self.disk_var.set(self.disk_options[0])
        self.disk_menu = ttk.OptionMenu(disk_controls_frame, self.disk_var, self.disk_var.get(), *self.disk_options, command=self.on_disk_select)
        self.disk_menu.pack(side=tk.LEFT, padx=(0,10))
        self.disk_label = ttk.Label(disk_controls_frame, text="Disk: Select a partition", style="SubHeader.TLabel")
        self.disk_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.disk_progress = ttk.Progressbar(disk_section, orient=tk.HORIZONTAL, length=100, mode='determinate')
        self.disk_progress.pack(fill=tk.X, pady=(2,4))
        self.disk_io_label = ttk.Label(disk_section, text="Disk I/O (System): N/A", style="Small.TLabel", wraplength=700)
        self.disk_io_label.pack(fill=tk.X)


        # --- Network & System Info Section ---
        net_sys_section = create_section(main_container, "Network & System Info")
        self.net_label = ttk.Label(net_sys_section, text="Network I/O (Session): N/A", style="SubHeader.TLabel")
        self.net_label.pack(fill=tk.X)
        self.process_count_label = ttk.Label(net_sys_section, text="Processes: N/A", style="SubHeader.TLabel")
        self.process_count_label.pack(fill=tk.X)
        self.uptime_label = ttk.Label(net_sys_section, text="Uptime: N/A", style="SubHeader.TLabel")
        self.uptime_label.pack(fill=tk.X)


        # --- Controls Section ---
        controls_outer_frame = ttk.Frame(main_container, style="TFrame", padding=(0,8,0,0)) 
        controls_outer_frame.pack(fill=tk.X, pady=8)
        self.start_button = ttk.Button(controls_outer_frame, text="Start Monitoring", command=self.start_monitoring, style="TButton")
        self.start_button.pack(side=tk.LEFT, padx=5)
        self.stop_button = ttk.Button(controls_outer_frame, text="Stop Monitoring", command=self.stop_monitoring, state=tk.DISABLED, style="Stop.TButton")
        self.stop_button.pack(side=tk.LEFT, padx=5)
        refresh_frame = ttk.Frame(controls_outer_frame, style="TFrame") 
        refresh_frame.pack(side=tk.LEFT, padx=(15,5))
        ttk.Label(refresh_frame, text="Refresh (s):", style="RefreshLabel.TLabel").pack(side=tk.LEFT) 
        self.interval_var = tk.StringVar(value=str(DEFAULT_REFRESH_INTERVAL_SECONDS)) 
        self.interval_entry = ttk.Entry(refresh_frame, textvariable=self.interval_var, width=4, font=('Helvetica', 10))
        self.interval_entry.pack(side=tk.LEFT)
        self.open_log_button = ttk.Button(controls_outer_frame, text="View Log", command=self.open_log_file, style="TButton")
        self.open_log_button.pack(side=tk.RIGHT, padx=5)

        # --- Status Bar ---
        self.status_var = tk.StringVar(value="Ready. Click 'Start Monitoring'.")
        status_bar_frame = ttk.Frame(self.root, style="TFrame", relief=tk.SUNKEN) 
        status_bar_frame.pack(side=tk.BOTTOM, fill=tk.X)
        status_bar = ttk.Label(status_bar_frame, textvariable=self.status_var, style="StatusBar.TLabel", anchor=tk.W)
        status_bar.pack(fill=tk.X)
        
        logger.info("Application initialized with more tools.")

    def on_disk_select(self, selected_value):
        self.disk_var.set(selected_value)
        if selected_value != "Select Partition" and selected_value != "No partitions found":
            disk_data = get_disk_usage(selected_value)
            if disk_data:
                 self.disk_label.config(text=f"{selected_value}: {disk_data['percent']:.2f}% ({'Monitoring' if monitoring_active.is_set() else 'Paused'})")
                 self.disk_progress['value'] = disk_data['percent']
            else:
                 self.disk_label.config(text=f"Disk ({selected_value}): Error")
                 self.disk_progress['value'] = 0
        else:
            self.disk_label.config(text="Disk: Select a partition")
            self.disk_progress['value'] = 0


    def update_status(self, message):
        self.status_var.set(message)

    def start_monitoring(self):
        global monitoring_thread, monitoring_active, stop_monitoring_event, network_stats_initial
        if monitoring_active.is_set():
            messagebox.showinfo("Info", "Monitoring is already active.")
            return

        try:
            interval = float(self.interval_var.get()) 
            if interval <= 0:
                messagebox.showerror("Error", "Refresh interval must be a positive number.")
                return
        except ValueError:
            messagebox.showerror("Error", "Invalid refresh interval.")
            return
        
        monitoring_active.set()
        stop_monitoring_event.clear()
        network_stats_initial = psutil.net_io_counters() 
        
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        self.interval_entry.config(state=tk.DISABLED)
        self.disk_menu.config(state=tk.DISABLED)

        self.update_status("Starting monitoring...")
        logger.info("Starting monitoring...")
        monitoring_thread = threading.Thread(target=monitoring_loop, args=(self,), daemon=True)
        monitoring_thread.start()
        
    def stop_monitoring(self):
        global monitoring_active, stop_monitoring_event
        if not monitoring_active.is_set():
            return

        self.update_status("Stopping monitoring...")
        logger.info("Stopping monitoring...")
        stop_monitoring_event.set()
        monitoring_active.clear()

        if monitoring_thread and monitoring_thread.is_alive():
            monitoring_thread.join(timeout=1.5) # Slightly shorter timeout
            if monitoring_thread.is_alive():
                 logger.warning("Monitoring thread did not terminate gracefully.")

        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.interval_entry.config(state=tk.NORMAL)
        self.disk_menu.config(state=tk.NORMAL)

        self.update_status("Monitoring stopped. Ready.")
        logger.info("Monitoring stopped by user action.")

    def open_log_file(self):
        try:
            log_file_path = os.path.abspath(LOG_FILE)
            if os.path.exists(log_file_path):
                if os.name == 'nt': os.startfile(log_file_path)
                elif os.name == 'posix': 
                    if os.system(f'open "{log_file_path}"') != 0: 
                        if os.system(f'xdg-open "{log_file_path}"') != 0: 
                            messagebox.showinfo("Open Log", f"Could not automatically open log.\nPlease find it at:\n{log_file_path}")
                else: 
                     messagebox.showinfo("Open Log", f"Log file at:\n{log_file_path}")
            else:
                messagebox.showinfo("Open Log", "Log file does not exist yet. Start monitoring to create it.")
        except Exception as e:
            messagebox.showerror("Error", f"Could not open log file: {e}")
            logger.error(f"Error opening log file: {e}", exc_info=True)

    def on_closing(self):
        if monitoring_active.is_set():
            if messagebox.askyesno("Quit", "Monitoring is active. Are you sure you want to quit? This will stop monitoring."):
                self.stop_monitoring() 
                self.root.destroy()
            else:
                return 
        else:
            self.root.destroy()
        logger.info("Application closed.")

# --- Main Execution ---
if __name__ == "__main__":
    try:
        import psutil
    except ImportError:
        root_check = tk.Tk()
        root_check.withdraw() 
        messagebox.showerror("Dependency Error", 
                             "The 'psutil' library is not installed.\n"
                             "Please install it by running: pip install psutil")
        root_check.destroy()
        exit(1)

    root = tk.Tk()
    app = SystemMonitorApp(root)
    root.mainloop()
