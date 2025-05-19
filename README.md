# 🌀 **Logflow** &nbsp; <img src="https://img.shields.io/badge/Python-3.7%2B-blue?logo=python" alt="Python" height="20"/> <img src="https://img.shields.io/badge/License-GPLv3-blue.svg" alt="License" height="20"/> <img src="https://img.shields.io/badge/Platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey" alt="Platform" height="20"/>

---

<p align="center">
  <img src="https://user-images.githubusercontent.com/your-screenshot.png" alt="Logflow Screenshot" width="700"/><br>
  <b>Real-time system monitoring, beautiful graphs, and logs at your fingertips.</b>
</p>

---

## 📋 Overview

> **Logflow** is a modern Python application with a graphical interface for real-time monitoring and logging of CPU, memory, disk, and network usage.  
> <br>
> <img src="https://img.icons8.com/color/48/000000/computer-support.png" width="32"/> Ideal for system administrators, developers, and power users who want to keep track of their system's health and performance.

---

## ✨ Features

<div align="center">

| 🚦 Live Monitoring | 🖼️ Graphical UI | 📝 Logging | ⚙️ Customizable | 💻 Cross-platform | 🛡️ Error Handling |
|:------------------:|:--------------:|:----------:|:--------------:|:----------------:|:----------------:|
| View CPU, memory, disk, and network usage in real time | Clean and intuitive Tkinter-based interface with graphs | All stats are logged to <code>logflow.log</code> for later analysis | Choose refresh interval and disk partition to monitor | Works on Windows, Linux, and macOS | Robust logging and user-friendly error messages |

</div>

---

## 🚀 Getting Started

<details>
<summary><b>Step-by-step Setup</b></summary>

1. **Clone the Repository**
    ```bash
    git clone https://github.com/yxshee/logflow
    cd  logflow
    ```

2. **Install Dependencies**
    - Make sure you have Python 3.7+ installed.
    - Install required packages:
      ```bash
      pip install -r src/requirements.txt
      ```
    - Or install in editable mode:
      ```bash
      pip install -e src
      ```

3. **Run the Application**
    ```bash
    python src/app.py
    ```
</details>

---

## ⚙️ Usage

<div align="center">

| ![Start](https://img.icons8.com/fluency/24/play.png) Start | ![Stop](https://img.icons8.com/fluency/24/stop.png) Stop | ![Disk](https://img.icons8.com/fluency/24/hdd.png) Disk | ![Refresh](https://img.icons8.com/fluency/24/refresh.png) Refresh | ![Log](https://img.icons8.com/fluency/24/notepad.png) Log |
|:---:|:---:|:---:|:---:|:---:|
| Click the <b>Start Monitoring</b> button | Click the <b>Stop Monitoring</b> button | Use the dropdown to choose which disk to monitor | Adjust the interval (in seconds) for data refresh | Click <b>Open Log File</b> to view the log in your default editor |

</div>

---

## 📑 Log File Example

```text
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

```text
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

<details>
<summary><b>Why is my disk usage not showing?</b></summary>
Make sure you select a valid disk partition from the dropdown.
</details>

<details>
<summary><b>How do I clear the log file?</b></summary>
Simply delete or truncate <code>logflow.log</code>. It will be recreated on next run.
</details>

<details>
<summary><b>Can I run this headless (without GUI)?</b></summary>
The current version is GUI-based. For CLI-only, use a previous version or adapt the code.
</details>

---

## 🤝 Contributing

Contributions are welcome!  
Please fork the repo and submit a pull request.

---

## 📄 License

This project is licensed under the [GNU GPL v3](LICENSE).

---

## 💡 Credits

- Built with [psutil](https://github.com/giampaolo/psutil) and [Tkinter](https://docs.python.org/3/library/tkinter.html).
- Icons by [Icons8](https://icons8.com/).

---
