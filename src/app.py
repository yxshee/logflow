import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import psutil
import time
import logging
from datetime import datetime, timedelta
import threading
import os
from collections import deque

# --- Configuration ---
LOG_FILE = 'system_performance_pro.log' # New log file name
DEFAULT_REFRESH_INTERVAL_SECONDS = 2 # Faster for better graph updates
CPU_READ_INTERVAL_SECONDS = 0.25
CPU_CORE_READ_INTERVAL_SECONDS = 0.1
PROCESS_LIST_REFRESH_INTERVAL_MULTIPLIER = 1 # Process list refreshes at main interval * this
GRAPH_HISTORY_POINTS = 60 # Number of data points to show in graphs

# --- Global Variables ---
monitoring_thread = None
monitoring_active = threading.Event()
stop_monitoring_event = threading.Event()
network_stats_initial = None

# --- Color Palette ---
COLOR_BACKGROUND = "#ECECEC" # Slightly lighter gray
COLOR_FRAME_BG = "#FFFFFF"
COLOR_TEXT = "#333333"
COLOR_HEADER_TEXT = "#003366"
COLOR_ACCENT_PRIMARY = "#0078D4"
COLOR_PROGRESS_TROUGH = "#E0E0E0"
COLOR_GRAPH_LINE = "#0078D4"
COLOR_GRAPH_FILL = "#D6EAF8" # Light blue fill for under graph line

# --- Logger Setup ---
def setup_logger():
    logger = logging.getLogger('SystemPerformanceMonitorGUI_Pro')
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        file_handler = logging.FileHandler(LOG_FILE)
        file_handler.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    return logger

logger = setup_logger()

# --- Graph Canvas Helper Class ---
class GraphCanvas:
    def __init__(self, parent_frame, width, height, max_value=100, history_points=GRAPH_HISTORY_POINTS):
        self.history_points = history_points
        self.data_history = deque([0] * self.history_points, maxlen=self.history_points)
        self.max_value = max_value
        
        self.canvas = tk.Canvas(parent_frame, width=width, height=height, bg=COLOR_FRAME_BG, highlightthickness=0)
        self.canvas.pack(fill=tk.X, pady=5)
        self.width = width
        self.height = height

    def add_data_point(self, value):
        self.data_history.append(min(value, self.max_value)) # Cap value at max_value
        self.draw_graph()

    def draw_graph(self):
        self.canvas.delete("all")
        
        points_to_draw = list(self.data_history)
        num_points = len(points_to_draw)
        if num_points < 2:
            return

        # Calculate coordinates
        x_increment = self.width / (self.history_points -1 if self.history_points > 1 else 1)
        
        # Create a list of (x, y) coordinates for the line
        line_coords = []
        for i, y_val in enumerate(points_to_draw):
            x = i * x_increment
            y = self.height - (y_val / self.max_value * self.height)
            line_coords.extend([x, y])

        # Draw the fill polygon
        if len(line_coords) >= 4:
            fill_coords = list(line_coords)
            fill_coords.extend([self.width, self.height, 0, self.height]) # Close polygon at bottom
            self.canvas.create_polygon(fill_coords, fill=COLOR_GRAPH_FILL, outline="")
        
        # Draw the line
        self.canvas.create_line(line_coords, fill=COLOR_GRAPH_LINE, width=2)

        # Draw Y-axis labels (0% and 100%)
        self.canvas.create_text(5, 5, text=f"{self.max_value}%", anchor="nw", fill=COLOR_TEXT, font=('Helvetica', 8))
        self.canvas.create_text(5, self.height - 5, text="0%", anchor="sw", fill=COLOR_TEXT, font=('Helvetica', 8))


# --- Core Monitoring Functions (mostly unchanged, added get_processes) ---
def get_cpu_usage():
    return psutil.cpu_percent(interval=CPU_READ_INTERVAL_SECONDS)

def get_per_core_cpu_usage():
    return psutil.cpu_percent(interval=CPU_CORE_READ_INTERVAL_SECONDS, percpu=True)

def get_cpu_frequency():
    try:
        freq = psutil.cpu_freq()
        return {"current": freq.current, "min": freq.min, "max": freq.max} if freq else None
    except Exception: return None

def get_cpu_stats_info(): # Renamed to avoid conflict
    try:
        stats = psutil.cpu_stats()
        return {"ctx_switches": stats.ctx_switches, "interrupts": stats.interrupts, "soft_interrupts": stats.soft_interrupts}
    except Exception: return None

def get_memory_usage():
    mem = psutil.virtual_memory()
    return {"total": mem.total, "available": mem.available, "percent": mem.percent, "used": mem.used, "free": mem.free}

def get_swap_memory_usage():
    swap = psutil.swap_memory()
    return {"total": swap.total, "used": swap.used, "free": swap.free, "percent": swap.percent}

def get_disk_partitions():
    partitions = []
    try:
        for part in psutil.disk_partitions(all=False):
            if os.name == 'nt' and ('fixed' in part.opts.lower() or part.fstype != ''):
                partitions.append(part.device)
            elif os.name != 'nt' and part.fstype and 'loop' not in part.device:
                partitions.append(part.mountpoint)
    except Exception as e: logger.error(f"Error getting disk partitions: {e}")
    return sorted(list(set(partitions)))

def get_disk_usage(path):
    try:
        disk = psutil.disk_usage(path)
        return {"total": disk.total, "used": disk.used, "free": disk.free, "percent": disk.percent}
    except Exception: return None

def get_disk_io_counters():
    try:
        io = psutil.disk_io_counters(perdisk=False)
        return {"read_count": io.read_count, "write_count": io.write_count, 
                "read_bytes": io.read_bytes, "write_bytes": io.write_bytes} if io else None
    except Exception: return None

def get_network_stats():
    global network_stats_initial
    net_io = psutil.net_io_counters()
    if network_stats_initial is None: network_stats_initial = net_io
    return {
        "bytes_sent_session": net_io.bytes_sent - network_stats_initial.bytes_sent,
        "bytes_recv_session": net_io.bytes_recv - network_stats_initial.bytes_recv,
    }

def get_process_count():
    return len(psutil.pids())

def get_system_uptime():
    return datetime.now() - datetime.fromtimestamp(psutil.boot_time())

def get_cpu_temperatures():
    temps = {}
    try:
        sensor_temps = psutil.sensors_temperatures()
        if not sensor_temps: return {"error": "Not supported or no sensors."}
        priority_keys = ['coretemp', 'k10temp', 'cpu_thermal', 'acpitz']
        for name, entries in sensor_temps.items():
            for entry in entries:
                is_priority = name in priority_keys
                is_cpu_label = any(k in entry.label.lower() for k in ["cpu", "core", "package"])
                if is_priority or is_cpu_label:
                    label = entry.label if entry.label else name
                    temps[f"{label} ({name})"] = entry.current
        if not temps and sensor_temps: # Fallback
            name, entries = list(sensor_temps.items())[0]
            if entries: temps[f"{entries[0].label or name} (Fallback)"] = entries[0].current
        return temps if temps else {"info": "No CPU temperature sensors identified."}
    except Exception: return {"error": "Unavailable"}

def get_processes_info():
    processes = []
    for proc in psutil.process_iter(['pid', 'name', 'username', 'cpu_percent', 'memory_percent']):
        try:
            p_info = proc.as_dict(attrs=['pid', 'name', 'username', 'cpu_percent', 'memory_percent'])
            if p_info['cpu_percent'] is None:
                p_info['cpu_percent'] = 0.0 
            processes.append(p_info)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    return processes

# --- UI Update Functions ---
def update_ui_labels(app_instance):
    if not monitoring_active.is_set(): return

    try:
        # --- CPU Data ---
        cpu_percent_overall = get_cpu_usage()
        app_instance.cpu_overall_label.config(text=f"Overall Usage: {cpu_percent_overall:.2f}%")
        app_instance.cpu_overall_progress['value'] = cpu_percent_overall
        app_instance.cpu_graph.add_data_point(cpu_percent_overall)
        
        core_usages = get_per_core_cpu_usage()
        app_instance.cpu_cores_label.config(text="Per Core: " + " | ".join([f"C{i}: {u:.1f}%" for i, u in enumerate(core_usages)]))
        
        freq = get_cpu_frequency()
        app_instance.cpu_freq_label.config(text=f"Frequency: {freq['current']:.0f} MHz (Min: {freq.get('min',0):.0f}, Max: {freq.get('max',0):.0f} MHz)" if freq else "Frequency: N/A")
        
        cpu_s = get_cpu_stats_info()
        app_instance.cpu_extra_stats_label.config(text=f"Ctx Switches: {cpu_s['ctx_switches']:,} | Interrupts: {cpu_s['interrupts']:,}" if cpu_s else "CPU Stats: N/A")
        
        temps = get_cpu_temperatures()
        if "error" in temps: app_instance.cpu_temp_label.config(text=f"CPU Temp: {temps['error']}")
        elif "info" in temps: app_instance.cpu_temp_label.config(text=f"CPU Temp: {temps['info']}")
        elif temps: app_instance.cpu_temp_label.config(text="CPU Temp: " + " | ".join([f"{n}: {t}°C" for n, t in temps.items()]))
        else: app_instance.cpu_temp_label.config(text="CPU Temp: N/A")

        # --- Memory Data ---
        mem_data = get_memory_usage()
        app_instance.mem_ram_label.config(text=f"RAM: {mem_data['percent']:.2f}% (Used: {bytes_to_gb(mem_data['used']):.2f}GB / Total: {bytes_to_gb(mem_data['total']):.2f}GB)")
        app_instance.mem_ram_progress['value'] = mem_data['percent']
        app_instance.mem_graph.add_data_point(mem_data['percent'])

        swap_data = get_swap_memory_usage()
        if swap_data['total'] > 0:
            app_instance.mem_swap_label.config(text=f"Swap: {swap_data['percent']:.2f}% (Used: {bytes_to_readable(swap_data['used'])} / Total: {bytes_to_readable(swap_data['total'])})")
            app_instance.mem_swap_progress['value'] = swap_data['percent']
            # Ensure widgets are packed if not already (e.g., after being forgotten)
            if not app_instance.mem_swap_label.winfo_ismapped():
                app_instance.mem_swap_label.pack(fill=tk.X, pady=(5,0), before=app_instance.mem_swap_progress_placeholder)
            if not app_instance.mem_swap_progress.winfo_ismapped():
                app_instance.mem_swap_progress.pack(fill=tk.X, pady=(2,0), before=app_instance.mem_swap_progress_placeholder)

        else:
            app_instance.mem_swap_label.pack_forget()
            app_instance.mem_swap_progress.pack_forget()


        # --- Disk Data ---
        selected_disk = app_instance.disk_var.get()
        disk_display_text, disk_percent_val = "Disk: Select a partition", 0
        if selected_disk not in ["Select Partition", "No partitions found"]:
            disk_data = get_disk_usage(selected_disk)
            if disk_data:
                disk_display_text = f"{selected_disk}: {disk_data['percent']:.2f}% (Used: {bytes_to_gb(disk_data['used']):.2f}GB / Total: {bytes_to_gb(disk_data['total']):.2f}GB)"
                disk_percent_val = disk_data['percent']
            else: disk_display_text = f"Disk ({selected_disk}): Error"
        app_instance.disk_label.config(text=disk_display_text)
        app_instance.disk_progress['value'] = disk_percent_val
        
        disk_io = get_disk_io_counters()
        app_instance.disk_io_label.config(text=f"Sys I/O Reads: {disk_io['read_count']:,} ({bytes_to_readable(disk_io['read_bytes'])}) | Writes: {disk_io['write_count']:,} ({bytes_to_readable(disk_io['write_bytes'])})" if disk_io else "Sys Disk I/O: N/A")

        # --- Network Data ---
        net_data = get_network_stats()
        app_instance.net_stats_label.config(text=f"Sent (Session): {bytes_to_readable(net_data['bytes_sent_session'])} / Received (Session): {bytes_to_readable(net_data['bytes_recv_session'])}")
        app_instance.sys_uptime_label.config(text=f"Uptime: {format_timedelta(get_system_uptime())}")
        
        # --- Processes Data (handled by its own update method) ---
        if app_instance.process_update_counter % PROCESS_LIST_REFRESH_INTERVAL_MULTIPLIER == 0:
            app_instance.update_process_list_ui()
        app_instance.process_update_counter +=1


        log_message = ( # Simplified log message
            f"CPU: {cpu_percent_overall:.1f}%, Mem: {mem_data['percent']:.1f}%, "
            f"Disk({selected_disk[0] if selected_disk not in ['Select Partition', 'No partitions found'] else 'N/A'}): {disk_percent_val:.1f}%"
        )
        logger.info(log_message)
        app_instance.update_status("Monitoring...")

    except Exception as e:
        logger.error(f"Error updating UI: {e}", exc_info=True)
        app_instance.update_status(f"Error: {str(e)[:50]}...")

    if monitoring_active.is_set() and not stop_monitoring_event.is_set():
        try:
            refresh_interval_ms = int(float(app_instance.interval_var.get()) * 1000)
            app_instance.root.after(max(500, refresh_interval_ms), lambda: update_ui_labels(app_instance)) # Min 500ms
        except ValueError: 
             app_instance.root.after(int(DEFAULT_REFRESH_INTERVAL_SECONDS * 1000), lambda: update_ui_labels(app_instance))

# --- Helper Functions ---
def bytes_to_gb(b): return b / (1024**3)
def bytes_to_readable(b):
    if b < 1024: return f"{b} B"
    if b < 1024**2: return f"{b/1024:.2f} KB"
    if b < 1024**3: return f"{b/(1024**2):.2f} MB"
    return f"{b/(1024**3):.2f} GB"
def format_timedelta(td):
    d, s = td.days, td.seconds
    h, rem = divmod(s, 3600)
    m, s = divmod(rem, 60)
    return f"{d}d {h:02}:{m:02}:{s:02}"

# --- Monitoring Thread ---
def monitoring_loop(app_instance):
    global network_stats_initial
    network_stats_initial = psutil.net_io_counters() 
    stop_monitoring_event.clear()
    app_instance.process_update_counter = 0 # Initialize counter for process list
    app_instance.root.after(0, lambda: update_ui_labels(app_instance)) 
    while not stop_monitoring_event.is_set(): time.sleep(0.1) 
    logger.info("Monitoring thread finished.")

# --- Application Class ---
class SystemMonitorApp:
    def __init__(self, root_window):
        self.root = root_window
        self.root.title("System Monitor Pro")
        self.root.geometry("900x800") # Increased size
        self.root.configure(bg=COLOR_BACKGROUND)
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.process_update_counter = 0

        self._setup_styles()
        self._create_main_widgets()
        self._create_tabs()
        self._create_controls_and_status_bar()
        
        logger.info("Application initialized with Tabs and Graphs.")

    def _setup_styles(self):
        style = ttk.Style()
        style.theme_use('alt')
        common_font = ('Helvetica', 10)
        header_font = ('Helvetica', 14, 'bold')
        small_font = ('Helvetica', 9)

        style.configure("TFrame", background=COLOR_FRAME_BG)
        style.configure("Section.TFrame", background=COLOR_FRAME_BG, relief=tk.SOLID, borderwidth=1)
        style.configure("Tab.TFrame", background=COLOR_BACKGROUND) # Frame inside tab
        style.configure("Background.TFrame", background=COLOR_BACKGROUND) # For frames matching root bg

        style.configure("TLabel", background=COLOR_FRAME_BG, foreground=COLOR_TEXT, padding=3, font=common_font)
        style.configure("Header.TLabel", background=COLOR_FRAME_BG, foreground=COLOR_HEADER_TEXT, font=header_font, padding=(5,8,5,5))
        style.configure("SubHeader.TLabel", background=COLOR_FRAME_BG, foreground=COLOR_TEXT, font=common_font, padding=(5,1,5,1))
        style.configure("Small.TLabel", background=COLOR_FRAME_BG, foreground=COLOR_TEXT, font=small_font, padding=(5,1,5,1))
        
        style.configure("RefreshLabel.TLabel", background=COLOR_BACKGROUND, foreground=COLOR_TEXT, font=common_font, padding=(5,1,5,1))
        style.configure("StatusBar.TLabel", background=COLOR_FRAME_BG, foreground=COLOR_TEXT, font=small_font, padding=5)

        style.configure("TProgressbar", thickness=18, troughcolor=COLOR_PROGRESS_TROUGH, background=COLOR_ACCENT_PRIMARY)
        
        style.configure("TButton", foreground=COLOR_FRAME_BG, background=COLOR_ACCENT_PRIMARY, font=common_font, padding=(8,4))
        style.map("TButton", background=[('active', '#005A9E'), ('disabled', '#B0B0B0')], foreground=[('active', COLOR_FRAME_BG), ('disabled', '#F0F0F0')])
        style.configure("Stop.TButton", background="#D9534F", foreground=COLOR_FRAME_BG) 
        style.map("Stop.TButton", background=[('active', "#C9302C"), ('disabled', '#E0B0B0')], foreground=[('active', COLOR_FRAME_BG), ('disabled', '#F5F5F5')])

        style.configure("TOptionMenu", font=common_font, padding=3)
        style.configure("TEntry", font=common_font, padding=3)
        style.configure("Treeview.Heading", font=('Helvetica', 10, 'bold'))


    def _create_main_widgets(self):
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(expand=True, fill='both', padx=10, pady=(10,0))

    def _create_section_frame(self, parent_tab, title):
        # Main frame for the tab content, matches root background
        tab_content_frame = ttk.Frame(parent_tab, style="Tab.TFrame", padding=10)
        tab_content_frame.pack(expand=True, fill='both')
        
        # Section frame within the tab, white background with border
        section = ttk.Frame(tab_content_frame, style="Section.TFrame", padding=10)
        section.pack(fill=tk.X, pady=5)
        ttk.Label(section, text=title, style="Header.TLabel").pack(anchor='w', pady=(0,5))
        return section

    def _create_tabs(self):
        # --- CPU Tab ---
        cpu_tab = ttk.Frame(self.notebook, style="Tab.TFrame")
        self.notebook.add(cpu_tab, text='CPU')
        cpu_section = self._create_section_frame(cpu_tab, "CPU Load & Information")
        
        self.cpu_overall_label = ttk.Label(cpu_section, text="Overall Usage: N/A", style="SubHeader.TLabel")
        self.cpu_overall_label.pack(fill=tk.X)
        self.cpu_overall_progress = ttk.Progressbar(cpu_section, mode='determinate')
        self.cpu_overall_progress.pack(fill=tk.X, pady=(2,5))
        self.cpu_graph = GraphCanvas(cpu_section, width=700, height=100) # Graph added
        self.cpu_cores_label = ttk.Label(cpu_section, text="Per Core: N/A", style="Small.TLabel", wraplength=750)
        self.cpu_cores_label.pack(fill=tk.X, pady=2)
        self.cpu_freq_label = ttk.Label(cpu_section, text="Frequency: N/A", style="Small.TLabel")
        self.cpu_freq_label.pack(fill=tk.X, pady=2)
        self.cpu_extra_stats_label = ttk.Label(cpu_section, text="CPU Stats: N/A", style="Small.TLabel", wraplength=750)
        self.cpu_extra_stats_label.pack(fill=tk.X, pady=2)
        self.cpu_temp_label = ttk.Label(cpu_section, text="CPU Temp: N/A", style="Small.TLabel", wraplength=750)
        self.cpu_temp_label.pack(fill=tk.X, pady=2)

        # --- Memory Tab ---
        mem_tab = ttk.Frame(self.notebook, style="Tab.TFrame")
        self.notebook.add(mem_tab, text='Memory')
        mem_section = self._create_section_frame(mem_tab, "Memory Usage")

        self.mem_ram_label = ttk.Label(mem_section, text="RAM: N/A", style="SubHeader.TLabel")
        self.mem_ram_label.pack(fill=tk.X)
        self.mem_ram_progress = ttk.Progressbar(mem_section, mode='determinate')
        self.mem_ram_progress.pack(fill=tk.X, pady=(2,5))
        self.mem_graph = GraphCanvas(mem_section, width=700, height=100) # Graph added

        # Placeholder for swap progress to maintain pack order if needed later
        self.mem_swap_progress_placeholder = ttk.Frame(mem_section, height=0) # Invisible placeholder
        self.mem_swap_progress_placeholder.pack()


        self.mem_swap_label = ttk.Label(mem_section, text="Swap: N/A", style="SubHeader.TLabel")
        self.mem_swap_label.pack(fill=tk.X, pady=(5,0)) 
        self.mem_swap_label.pack_forget() # Start hidden

        self.mem_swap_progress = ttk.Progressbar(mem_section, mode='determinate')
        self.mem_swap_progress.pack(fill=tk.X, pady=(2,0))
        self.mem_swap_progress.pack_forget() # Start hidden
        
        # --- Disk Tab ---
        disk_tab = ttk.Frame(self.notebook, style="Tab.TFrame")
        self.notebook.add(disk_tab, text='Disk')
        disk_section = self._create_section_frame(disk_tab, "Disk Usage & I/O")
        
        disk_controls_frame = ttk.Frame(disk_section, style="TFrame") 
        disk_controls_frame.pack(fill=tk.X, pady=(0,3))
        self.disk_var = tk.StringVar(value="Select Partition")
        self.disk_options = get_disk_partitions()
        if not self.disk_options: self.disk_options = ["No partitions found"]
        self.disk_menu = ttk.OptionMenu(disk_controls_frame, self.disk_var, self.disk_options[0], *self.disk_options, command=self.on_disk_select)
        self.disk_menu.pack(side=tk.LEFT, padx=(0,10))
        self.disk_label = ttk.Label(disk_controls_frame, text="Disk: Select a partition", style="SubHeader.TLabel")
        self.disk_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        self.disk_progress = ttk.Progressbar(disk_section, mode='determinate')
        self.disk_progress.pack(fill=tk.X, pady=(2,5))
        self.disk_io_label = ttk.Label(disk_section, text="System Disk I/O: N/A", style="Small.TLabel", wraplength=750)
        self.disk_io_label.pack(fill=tk.X)

        # --- Network Tab ---
        net_tab = ttk.Frame(self.notebook, style="Tab.TFrame")
        self.notebook.add(net_tab, text='Network')
        net_section = self._create_section_frame(net_tab, "Network & System Information")
        self.net_stats_label = ttk.Label(net_section, text="Network I/O (Session): N/A", style="SubHeader.TLabel")
        self.net_stats_label.pack(fill=tk.X, pady=2)
        self.sys_uptime_label = ttk.Label(net_section, text="Uptime: N/A", style="SubHeader.TLabel")
        self.sys_uptime_label.pack(fill=tk.X, pady=2)

        # --- Processes Tab ---
        proc_tab = ttk.Frame(self.notebook, style="Tab.TFrame")
        self.notebook.add(proc_tab, text='Processes')
        proc_section_container = ttk.Frame(proc_tab, style="Tab.TFrame", padding=10) # Matches tab background
        proc_section_container.pack(expand=True, fill='both')
        
        # The Treeview itself will be inside a white frame
        proc_list_frame = ttk.Frame(proc_section_container, style="Section.TFrame", padding=10)
        proc_list_frame.pack(expand=True, fill='both')

        # Treeview for processes
        cols = ("PID", "Name", "User", "CPU %", "Memory %")
        self.process_tree = ttk.Treeview(proc_list_frame, columns=cols, show='headings', style="Treeview")
        for col in cols:
            self.process_tree.heading(col, text=col, command=lambda _col=col: self._treeview_sort_column(_col, False))
            self.process_tree.column(col, width=100, anchor='center' if col in ["PID", "CPU %", "Memory %"] else 'w')
        self.process_tree.column("Name", width=250) # Wider name column
        
        vsb = ttk.Scrollbar(proc_list_frame, orient="vertical", command=self.process_tree.yview)
        self.process_tree.configure(yscrollcommand=vsb.set)
        
        vsb.pack(side='right', fill='y')
        self.process_tree.pack(expand=True, fill='both')
        self.update_process_list_ui() # Initial population

    def _treeview_sort_column(self, col, reverse):
        try:
            l = [(self.process_tree.set(k, col), k) for k in self.process_tree.get_children('')]
            
            def sort_key(item_tuple):
                val_str = str(item_tuple[0]).replace('%', '')
                try:
                    return float(val_str)
                except ValueError:
                    return val_str.lower() # Fallback to string sort if not float

            l.sort(key=sort_key, reverse=reverse)

            for index, (val, k) in enumerate(l):
                self.process_tree.move(k, '', index)
            self.process_tree.heading(col, command=lambda _col=col: self._treeview_sort_column(_col, not reverse))
        except Exception as e:
            logger.error(f"Error sorting treeview column {col}: {e}")


    def update_process_list_ui(self):
        # Clear existing items
        for item in self.process_tree.get_children():
            self.process_tree.delete(item)
        
        processes = get_processes_info()
        for p_info in processes:
            username = p_info.get('username', 'N/A')
            if os.name == 'nt' and username and '\\' in username: # Shorten Windows usernames
                username = username.split('\\')[-1]

            cpu_val = p_info.get('cpu_percent') # This might be None
            mem_val = p_info.get('memory_percent') # This might be None

            # Handle None before formatting
            cpu_str = f"{cpu_val:.1f}%" if cpu_val is not None else "0.0%"
            mem_str = f"{mem_val:.1f}%" if mem_val is not None else "0.0%"
            
            self.process_tree.insert("", "end", values=(
                p_info.get('pid', 'N/A'),
                p_info.get('name', 'N/A'),
                username,
                cpu_str, 
                mem_str  
            ))


    def _create_controls_and_status_bar(self):
        controls_outer_frame = ttk.Frame(self.root, style="Background.TFrame", padding=(10,8,10,8)) 
        controls_outer_frame.pack(fill=tk.X)

        self.start_button = ttk.Button(controls_outer_frame, text="Start Monitoring", command=self.start_monitoring, style="TButton")
        self.start_button.pack(side=tk.LEFT, padx=5)
        self.stop_button = ttk.Button(controls_outer_frame, text="Stop Monitoring", command=self.stop_monitoring, state=tk.DISABLED, style="Stop.TButton")
        self.stop_button.pack(side=tk.LEFT, padx=5)
        
        refresh_frame = ttk.Frame(controls_outer_frame, style="Background.TFrame") 
        refresh_frame.pack(side=tk.LEFT, padx=(15,5))
        ttk.Label(refresh_frame, text="Refresh (s):", style="RefreshLabel.TLabel").pack(side=tk.LEFT) 
        self.interval_var = tk.StringVar(value=str(DEFAULT_REFRESH_INTERVAL_SECONDS)) 
        self.interval_entry = ttk.Entry(refresh_frame, textvariable=self.interval_var, width=4, font=('Helvetica', 10))
        self.interval_entry.pack(side=tk.LEFT)
        
        self.open_log_button = ttk.Button(controls_outer_frame, text="View Log", command=self.open_log_file, style="TButton")
        self.open_log_button.pack(side=tk.RIGHT, padx=5)

        self.status_var = tk.StringVar(value="Ready. Click 'Start Monitoring'.")
        status_bar_frame = ttk.Frame(self.root, style="TFrame", relief=tk.SUNKEN) 
        status_bar_frame.pack(side=tk.BOTTOM, fill=tk.X)
        status_bar = ttk.Label(status_bar_frame, textvariable=self.status_var, style="StatusBar.TLabel", anchor=tk.W)
        status_bar.pack(fill=tk.X)

    def on_disk_select(self, selected_value): # Simplified
        self.disk_var.set(selected_value)
        # UI will update on next monitoring cycle or if start is pressed

    def update_status(self, message): self.status_var.set(message)

    def start_monitoring(self):
        global monitoring_thread, monitoring_active, stop_monitoring_event, network_stats_initial
        if monitoring_active.is_set():
            messagebox.showinfo("Info", "Monitoring is already active.")
            return
        try:
            if float(self.interval_var.get()) <= 0:
                messagebox.showerror("Error", "Refresh interval must be positive.")
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
        if not monitoring_active.is_set(): return

        self.update_status("Stopping monitoring...")
        logger.info("Stopping monitoring...")
        stop_monitoring_event.set()
        monitoring_active.clear()

        if monitoring_thread and monitoring_thread.is_alive():
            monitoring_thread.join(timeout=1.0) 
            if monitoring_thread.is_alive(): logger.warning("Monitoring thread unresponsive.")

        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.interval_entry.config(state=tk.NORMAL)
        self.disk_menu.config(state=tk.NORMAL)
        self.update_status("Monitoring stopped. Ready.")

    def open_log_file(self):
        try:
            log_path = os.path.abspath(LOG_FILE)
            if not os.path.exists(log_path):
                messagebox.showinfo("Open Log", "Log file not found. Start monitoring to create it.")
                return
            if os.name == 'nt': os.startfile(log_path)
            elif os.name == 'posix':
                if os.system(f'open "{log_path}"') != 0 and os.system(f'xdg-open "{log_path}"') != 0:
                    messagebox.showinfo("Open Log", f"Could not auto-open log. Path:\n{log_path}")
            else: messagebox.showinfo("Open Log", f"Log file at:\n{log_path}")
        except Exception as e:
            messagebox.showerror("Error", f"Could not open log: {e}")
            logger.error(f"Error opening log: {e}", exc_info=True)

    def on_closing(self):
        if monitoring_active.is_set() and messagebox.askyesno("Quit", "Monitoring active. Quit anyway?"):
            self.stop_monitoring()
        self.root.destroy()
        logger.info("Application closed.")

# --- Main Execution ---
if __name__ == "__main__":
    try: import psutil
    except ImportError:
        r_check = tk.Tk(); r_check.withdraw()
        messagebox.showerror("Dependency Error", "psutil library not found.\nPlease install: pip install psutil")
        r_check.destroy(); exit(1)

    root = tk.Tk()
    app = SystemMonitorApp(root)
    root.mainloop()
