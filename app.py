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
DEFAULT_REFRESH_INTERVAL_SECONDS = 3 # Slightly faster default for better visual feedback
CPU_READ_INTERVAL_SECONDS = 0.5

# --- Global Variables ---
monitoring_thread = None
monitoring_active = threading.Event()
stop_monitoring_event = threading.Event()
network_stats_initial = None

# --- Color Palette (Example - can be customized further) ---
COLOR_BACKGROUND = "#F0F0F0"  # Light gray
COLOR_FRAME_BG = "#FFFFFF"    # White for frames
COLOR_TEXT = "#333333"       # Dark gray for text
COLOR_HEADER_TEXT = "#003366" # Dark blue for headers
COLOR_ACCENT_PRIMARY = "#0078D4" # Blue for progress bars, buttons
COLOR_ACCENT_SECONDARY = "#5CB85C" # Green for success/status
COLOR_PROGRESS_TROUGH = "#E0E0E0" # Light gray for progress bar trough

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

# --- Core Monitoring Functions (Identical to previous version) ---
def get_cpu_usage():
    return psutil.cpu_percent(interval=CPU_READ_INTERVAL_SECONDS)

def get_memory_usage():
    mem = psutil.virtual_memory()
    return {"total": mem.total, "available": mem.available, "percent": mem.percent, "used": mem.used, "free": mem.free}

def get_disk_partitions():
    partitions = []
    try:
        for part in psutil.disk_partitions(all=False):
            if os.name == 'nt':
                 if 'fixed' in part.opts.lower() or part.fstype != '':
                    partitions.append(part.device)
            else: # Linux/MacOS
                if part.fstype and 'loop' not in part.device: # Exclude loop devices on Linux
                    partitions.append(part.mountpoint)
    except Exception as e:
        logger.error(f"Error getting disk partitions: {e}")
    return sorted(list(set(partitions)))

def get_disk_usage(path):
    try:
        disk = psutil.disk_usage(path)
        return {"total": disk.total, "used": disk.used, "free": disk.free, "percent": disk.percent}
    except FileNotFoundError:
        logger.warning(f"Disk path not found: {path}")
        return None
    except Exception as e:
        logger.error(f"Error getting disk usage for {path}: {e}")
        return None

def get_network_stats():
    global network_stats_initial
    net_io = psutil.net_io_counters()
    if network_stats_initial is None:
        network_stats_initial = net_io # Store initial counters when monitoring starts or first called
    
    # Calculate bytes since application start (or last reset if we implement that)
    bytes_sent_since_start = net_io.bytes_sent - network_stats_initial.bytes_sent
    bytes_recv_since_start = net_io.bytes_recv - network_stats_initial.bytes_recv

    return {
        "bytes_sent_total": net_io.bytes_sent, # Overall system count
        "bytes_recv_total": net_io.bytes_recv, # Overall system count
        "bytes_sent_session": bytes_sent_since_start, # Since app start/monitor start
        "bytes_recv_session": bytes_recv_since_start, # Since app start/monitor start
        "packets_sent": net_io.packets_sent,
        "packets_recv": net_io.packets_recv
    }

# --- UI Update Functions (Logic identical, relies on app_instance for widget access) ---
def update_ui_labels(app_instance):
    if not monitoring_active.is_set():
        return

    try:
        cpu_percent = get_cpu_usage()
        app_instance.cpu_label.config(text=f"Current Usage: {cpu_percent:.2f}%")
        app_instance.cpu_progress['value'] = cpu_percent
        
        mem_data = get_memory_usage()
        app_instance.mem_label.config(
            text=f"{mem_data['percent']:.2f}% "
                 f"(Used: {bytes_to_gb(mem_data['used']):.2f}GB / "
                 f"Total: {bytes_to_gb(mem_data['total']):.2f}GB)"
        )
        app_instance.mem_progress['value'] = mem_data['percent']

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
                disk_display_text = f"Disk ({selected_disk}): Error fetching data"
        app_instance.disk_label.config(text=disk_display_text)
        app_instance.disk_progress['value'] = disk_percent_val
        
        net_data = get_network_stats()
        app_instance.net_label.config(
            text=f"Sent (Session): {bytes_to_readable(net_data['bytes_sent_session'])} / "
                 f"Received (Session): {bytes_to_readable(net_data['bytes_recv_session'])}"
        )
        
        log_message = (
            f"CPU: {cpu_percent:.2f}%, Mem: {mem_data['percent']:.2f}%, "
            f"Disk ({selected_disk if selected_disk and selected_disk not in ['Select Partition', 'No partitions found'] else 'N/A'}): {disk_percent_val:.2f}%, "
            f"Net Sent: {bytes_to_readable(net_data['bytes_sent_session'])}, Net Recv: {bytes_to_readable(net_data['bytes_recv_session'])}"
        )
        logger.info(log_message)
        app_instance.update_status("Monitoring...")

    except Exception as e:
        logger.error(f"Error updating UI: {e}", exc_info=True)
        app_instance.update_status(f"Error: {str(e)[:50]}...") # Show truncated error

    if monitoring_active.is_set() and not stop_monitoring_event.is_set():
        try:
            refresh_interval_ms = int(float(app_instance.interval_var.get()) * 1000)
            if refresh_interval_ms <=0: refresh_interval_ms = 1000 # Safety net
            app_instance.root.after(refresh_interval_ms, lambda: update_ui_labels(app_instance))
        except ValueError: # Handle case where interval entry is not a valid float
             app_instance.root.after(int(DEFAULT_REFRESH_INTERVAL_SECONDS * 1000), lambda: update_ui_labels(app_instance))


# --- Helper Functions (Identical) ---
def bytes_to_gb(bytes_val):
    return bytes_val / (1024**3)

def bytes_to_readable(bytes_val):
    if bytes_val < 1024: return f"{bytes_val} B"
    elif bytes_val < 1024**2: return f"{bytes_val/1024:.2f} KB"
    elif bytes_val < 1024**3: return f"{bytes_val/(1024**2):.2f} MB"
    else: return f"{bytes_val/(1024**3):.2f} GB"

# --- Monitoring Thread Function (Identical) ---
def monitoring_loop(app_instance):
    global network_stats_initial
    network_stats_initial = psutil.net_io_counters() # Initialize/reset session counters
    stop_monitoring_event.clear()
    app_instance.root.after(0, lambda: update_ui_labels(app_instance)) # Initial call to start chain
    while not stop_monitoring_event.is_set():
        time.sleep(0.1) # Keep thread responsive, updates are handled by 'after'
    logger.info("Monitoring thread finished.")

# --- Application Class (UI and Styling Enhanced) ---
class SystemMonitorApp:
    def __init__(self, root_window):
        self.root = root_window
        self.root.title("System Performance Monitor")
        self.root.geometry("700x580") 
        self.root.configure(bg=COLOR_BACKGROUND) # Configure root window background
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        # --- Styling ---
        style = ttk.Style()
        style.theme_use('alt') 

        style.configure("TFrame", background=COLOR_FRAME_BG) # Default for ttk.Frame
        style.configure("Section.TFrame", background=COLOR_FRAME_BG, relief=tk.RIDGE, borderwidth=1)
        
        style.configure("TLabel", background=COLOR_FRAME_BG, foreground=COLOR_TEXT, padding=5, font=('Helvetica', 10))
        style.configure("Header.TLabel", background=COLOR_FRAME_BG, foreground=COLOR_HEADER_TEXT, font=('Helvetica', 14, 'bold'), padding=(5, 10, 5, 5))
        style.configure("SubHeader.TLabel", background=COLOR_FRAME_BG, foreground=COLOR_TEXT, font=('Helvetica', 11), padding=(5,2,5,2))
        
        # Style for the "Refresh (s):" label to match main background
        style.configure("RefreshLabel.TLabel", background=COLOR_BACKGROUND, foreground=COLOR_TEXT, font=('Helvetica', 11), padding=(5,2,5,2))
        
        # Style for the Status Bar Label
        style.configure("StatusBar.TLabel", background=COLOR_FRAME_BG, foreground=COLOR_TEXT, font=('Helvetica', 9), padding=5)


        style.configure("TProgressbar", thickness=22, troughcolor=COLOR_PROGRESS_TROUGH, background=COLOR_ACCENT_PRIMARY)
        
        style.configure("TButton", foreground=COLOR_FRAME_BG, background=COLOR_ACCENT_PRIMARY, font=('Helvetica', 10, 'bold'), padding=(10, 5)) # Text color white for blue button
        style.map("TButton",
            background=[('active', '#005A9E'), ('disabled', '#B0B0B0')], 
            foreground=[('active', COLOR_FRAME_BG), ('disabled', '#F0F0F0')]
        )
        style.configure("Stop.TButton", background="#D9534F", foreground=COLOR_FRAME_BG) 
        style.map("Stop.TButton", 
                  background=[('active', "#C9302C"), ('disabled', '#E0B0B0')],
                  foreground=[('active', COLOR_FRAME_BG), ('disabled', '#F5F5F5')]
        )

        style.configure("TOptionMenu", font=('Helvetica', 10), padding=5)
        style.configure("TEntry", font=('Helvetica', 10), padding=5)


        # --- Main Container Frame ---
        # This frame will use the "TFrame" style, which has COLOR_FRAME_BG (white)
        main_container = ttk.Frame(self.root, style="TFrame", padding=10)
        main_container.pack(expand=True, fill=tk.BOTH)
        # The line below was causing the error and is removed:
        # main_container.configure(background=COLOR_BACKGROUND) 


        # Function to create a section frame
        def create_section(parent, title_text):
            section_frame = ttk.Frame(parent, style="Section.TFrame", padding=10)
            section_frame.pack(fill=tk.X, pady=5)
            ttk.Label(section_frame, text=title_text, style="Header.TLabel").pack(anchor='w')
            return section_frame

        # --- CPU Section ---
        cpu_section = create_section(main_container, "CPU Usage")
        self.cpu_label = ttk.Label(cpu_section, text="Current Usage: N/A", style="SubHeader.TLabel")
        self.cpu_label.pack(fill=tk.X, pady=(0,5))
        self.cpu_progress = ttk.Progressbar(cpu_section, orient=tk.HORIZONTAL, length=100, mode='determinate')
        self.cpu_progress.pack(fill=tk.X)

        # --- Memory Section ---
        mem_section = create_section(main_container, "Memory Usage")
        self.mem_label = ttk.Label(mem_section, text="N/A", style="SubHeader.TLabel")
        self.mem_label.pack(fill=tk.X, pady=(0,5))
        self.mem_progress = ttk.Progressbar(mem_section, orient=tk.HORIZONTAL, length=100, mode='determinate')
        self.mem_progress.pack(fill=tk.X)

        # --- Disk Section ---
        disk_section = create_section(main_container, "Disk Usage")
        
        disk_controls_frame = ttk.Frame(disk_section, style="TFrame") 
        disk_controls_frame.pack(fill=tk.X, pady=(0,5))

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
        self.disk_progress.pack(fill=tk.X)

        # --- Network Section ---
        net_section = create_section(main_container, "Network I/O")
        self.net_label = ttk.Label(net_section, text="N/A", style="SubHeader.TLabel")
        self.net_label.pack(fill=tk.X)

        # --- Controls Section ---
        # This frame uses "TFrame" style (white), but its children can have different backgrounds if styled
        controls_outer_frame = ttk.Frame(main_container, style="TFrame", padding=(0,10,0,0)) 
        controls_outer_frame.pack(fill=tk.X, pady=10)

        self.start_button = ttk.Button(controls_outer_frame, text="Start Monitoring", command=self.start_monitoring, style="TButton")
        self.start_button.pack(side=tk.LEFT, padx=5)

        self.stop_button = ttk.Button(controls_outer_frame, text="Stop Monitoring", command=self.stop_monitoring, state=tk.DISABLED, style="Stop.TButton")
        self.stop_button.pack(side=tk.LEFT, padx=5)

        # Frame for refresh interval, this frame itself will be white ("TFrame" style)
        refresh_frame = ttk.Frame(controls_outer_frame, style="TFrame") 
        refresh_frame.pack(side=tk.LEFT, padx=(20,5))
        
        # This label is styled with "RefreshLabel.TLabel" to have COLOR_BACKGROUND
        ttk.Label(refresh_frame, text="Refresh (s):", style="RefreshLabel.TLabel").pack(side=tk.LEFT) 
        
        self.interval_var = tk.StringVar(value=str(DEFAULT_REFRESH_INTERVAL_SECONDS)) 
        self.interval_entry = ttk.Entry(refresh_frame, textvariable=self.interval_var, width=5, font=('Helvetica', 10))
        self.interval_entry.pack(side=tk.LEFT)
        
        self.open_log_button = ttk.Button(controls_outer_frame, text="View Log", command=self.open_log_file, style="TButton")
        self.open_log_button.pack(side=tk.RIGHT, padx=5)

        # --- Status Bar ---
        self.status_var = tk.StringVar(value="Ready. Click 'Start Monitoring'.")
        # status_bar_frame uses "TFrame" style (white background)
        status_bar_frame = ttk.Frame(self.root, style="TFrame", relief=tk.SUNKEN) 
        status_bar_frame.pack(side=tk.BOTTOM, fill=tk.X)
        
        # status_bar label uses "StatusBar.TLabel" style (white background to match its parent frame)
        # anchor=tk.W is a valid option for ttk.Label constructor for text alignment within the label
        status_bar = ttk.Label(status_bar_frame, textvariable=self.status_var, style="StatusBar.TLabel", anchor=tk.W)
        status_bar.pack(fill=tk.X)
        
        logger.info("Application initialized with new UI and fixes.")

    def on_disk_select(self, selected_value):
        self.disk_var.set(selected_value) # Ensure var is updated
        # Only update if monitoring, otherwise it will be picked up when monitoring starts/resumes
        if monitoring_active.is_set() and selected_value != "Select Partition" and selected_value != "No partitions found":
            disk_data = get_disk_usage(selected_value)
            if disk_data:
                self.disk_label.config(
                    text=f"{selected_value}: {disk_data['percent']:.2f}% "
                         f"(Used: {bytes_to_gb(disk_data['used']):.2f}GB / "
                         f"Total: {bytes_to_gb(disk_data['total']):.2f}GB)"
                )
                self.disk_progress['value'] = disk_data['percent']
            else:
                self.disk_label.config(text=f"Disk ({selected_value}): Error fetching data")
                self.disk_progress['value'] = 0
        elif not monitoring_active.is_set() and selected_value != "Select Partition" and selected_value != "No partitions found":
             # Update display even if not monitoring, for immediate feedback on selection
            disk_data = get_disk_usage(selected_value)
            if disk_data:
                 self.disk_label.config(text=f"{selected_value}: {disk_data['percent']:.2f}% (Not actively monitoring)")
                 self.disk_progress['value'] = disk_data['percent']
            else:
                 self.disk_label.config(text=f"Disk ({selected_value}): Error (Not actively monitoring)")
                 self.disk_progress['value'] = 0


    def update_status(self, message):
        self.status_var.set(message)
        # logger.info(f"Status: {message}") # Already logged in update_ui_labels or actions

    def start_monitoring(self):
        global monitoring_thread, monitoring_active, stop_monitoring_event, network_stats_initial
        if monitoring_active.is_set():
            messagebox.showinfo("Info", "Monitoring is already active.")
            return

        try:
            interval_str = self.interval_var.get()
            interval = float(interval_str) 
            if interval <= 0:
                messagebox.showerror("Error", "Refresh interval must be a positive number.")
                return
        except ValueError:
            messagebox.showerror("Error", "Invalid refresh interval. Please enter a number (e.g., 3 or 2.5).")
            return
        
        monitoring_active.set()
        stop_monitoring_event.clear()
        network_stats_initial = psutil.net_io_counters() # Reset session network stats on start
        
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
            monitoring_thread.join(timeout=2.0) 
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
                elif os.name == 'posix': # Covers macOS and Linux
                    # 'open' is common on macOS, 'xdg-open' on Linux
                    if os.system(f'open "{log_file_path}"') != 0: 
                        if os.system(f'xdg-open "{log_file_path}"') != 0: 
                            messagebox.showinfo("Open Log", f"Could not automatically open log. Please find it at:\n{log_file_path}")
                else: # Fallback for other OS
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
        # Create a temporary root to show messagebox if psutil is missing
        # This is needed because messagebox needs a root window.
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
