# 🖥️ Logflow

![Python](https://img.shields.io/badge/Python-3.7%2B-blue?logo=python)
![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)
![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey)

---

## 📋 Overview

**Logflow** is a Python application with a graphical interface for real-time monitoring and logging of CPU, memory, disk, and network usage. It is ideal for system administrators, developers, and power users who want to keep track of their system's health and performance.

---

## ✨ Features

- **Live Monitoring**: View CPU, memory, disk, and network usage in real time.
- **Graphical UI**: Clean and intuitive Tkinter-based interface.
- **Logging**: All stats are logged to `logflow.log` for later analysis.
- **Customizable**: Choose refresh interval and disk partition to monitor.
- **Cross-platform**: Works on Windows, Linux, and macOS.
- **Error Handling**: Robust logging and user-friendly error messages.

---

## 🚀 Getting Started

### 1. **Clone the Repository**

```bash
git clone https://github.com/yxshee/logflow
cd  logflow
```

### 2. **Install Dependencies**

- Make sure you have Python 3.7+ installed.
- Install required packages:
```bash
pip install -r src/requirements.txt
```
Or install in editable mode:
```bash
pip install -e src
```

### 3. **Run the Application**

```bash
python src/app.py
```

---

## ⚙️ Usage

- **Start Monitoring**: Click the `Start Monitoring` button.
- **Stop Monitoring**: Click the `Stop Monitoring` button.
- **Select Disk Partition**: Use the dropdown to choose which disk to monitor.
- **Set Refresh Interval**: Adjust the interval (in seconds) for data refresh.
- **Open Log File**: Click `Open Log File` to view the log in your default editor.

---

## 📑 Log File Example

```
2025-05-16 17:15:36 - INFO - Starting Logflow monitoring...
2025-05-16 17:15:37 - INFO - CPU: 27.00%, Mem: 86.80%, Disk (C:): 60.00% (if selected), Net Sent (Session): 1.23 MB, Net Recv (Session): 2.34 MB
2025-05-16 17:16:54 - INFO - Logflow monitoring stopped by user action.
```

---

## 🛠️ Configuration

You can change these variables in `app.py`:

```python
LOG_FILE = 'logflow.log'  # Log file name
DEFAULT_REFRESH_INTERVAL_SECONDS = 5 # UI refresh interval (seconds)
CPU_READ_INTERVAL_SECONDS = 0.5      # CPU usage sampling interval (seconds)
```

---

## 🧩 Project Structure

```
logflow/
├── src/
│   ├── app.py                  # Main application (GUI)
│   ├── requirements.txt        # Python dependencies
│   └── setup.py                # Packaging script
├── logflow.log                 # Log file (auto-generated, gitignored)
├── .gitignore
├── README.md
└── LICENSE
```

---

## 🙋 FAQ

- **Q:** _Why is my disk usage not showing?_
  - **A:** Make sure you select a valid disk partition from the dropdown.

- **Q:** _How do I clear the log file?_
  - **A:** Simply delete or truncate `logflow.log`. It will be recreated on next run.

- **Q:** _Can I run this headless (without GUI)?_
  - **A:** The current version is GUI-based. For CLI-only, use a previous version or adapt the code.

---

## 🤝 Contributing

Contributions are welcome! Please fork the repo and submit a pull request.

---

## 📄 License

This project is licensed under the [GNU GPL v3](LICENSE).

---

## 💡 Credits

- Built with [psutil](https://github.com/giampaolo/psutil) and [Tkinter](https://docs.python.org/3/library/tkinter.html).
