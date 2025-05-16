import psutil  # For system and process utilities
import time    # For pausing the script
import logging # For logging data to a file
from datetime import datetime # For timestamping log entries

# --- Configuration ---
LOG_FILE = 'system_performance.log'  # Name of the log file
LOG_INTERVAL_SECONDS = 60  # How often to log data (in seconds). Change as needed.
CPU_READ_INTERVAL_SECONDS = 1.0 # Interval for psutil.cpu_percent() for a more accurate reading

def setup_logger():
    """
    Configures and returns a logger instance.
    The logger will output to both a file and the console.
    """
    # Create a logger object
    logger = logging.getLogger('SystemPerformanceMonitor')
    logger.setLevel(logging.INFO)  # Set the minimum logging level to INFO

    # --- File Handler ---
    # This handler writes log messages to a file.
    file_handler = logging.FileHandler(LOG_FILE)
    file_handler.setLevel(logging.INFO) # Set level for file output

    # --- Console Handler ---
    # This handler prints log messages to the console.
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO) # Set level for console output

    # --- Log Formatter ---
    # Defines the format of the log messages.
    # Format: Timestamp - LogLevel - Message
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    # --- Add Handlers to Logger ---
    # Attach the configured handlers to the logger object.
    if not logger.handlers: # Avoid adding multiple handlers if re-running in some environments
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

    return logger

def get_cpu_usage():
    """
    Retrieves the current system-wide CPU utilization percentage.
    Uses a short interval for a more accurate, non-blocking reading.
    """
    # psutil.cpu_percent(interval) compares system CPU times elapsed before and
    # after the interval (blocking). If interval is 0.0 or None, it compares system CPU
    # times elapsed since last call or module import, returning immediately (non-blocking).
    # The first call with interval=None or 0.0 will return a meaningless 0.0.
    # Using a small, positive interval gives a more reliable reading.
    return psutil.cpu_percent(interval=CPU_READ_INTERVAL_SECONDS)

def get_memory_usage():
    """
    Retrieves the current system-wide memory utilization percentage.
    """
    memory_info = psutil.virtual_memory()  # Get virtual memory status
    # memory_info.percent gives the memory usage percentage directly
    return memory_info.percent

def monitor_and_log(logger_instance):
    """
    Continuously monitors CPU and memory usage and logs the data.
    Args:
        logger_instance: The configured logger object.
    """
    logger_instance.info("Starting system performance monitoring...")
    print(f"Logging performance data every {LOG_INTERVAL_SECONDS} seconds. Press Ctrl+C to stop.")
    print(f"Log file: {LOG_FILE}")

    try:
        while True:
            # Get current timestamp
            # current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S') # Timestamp is handled by logger

            # Get current CPU and Memory usage
            cpu_percent = get_cpu_usage()
            memory_percent = get_memory_usage()

            # Prepare log message
            log_message = f"CPU Usage: {cpu_percent:.2f}% | Memory Usage: {memory_percent:.2f}%"

            # Log the information
            logger_instance.info(log_message)

            # Wait for the specified interval
            time.sleep(LOG_INTERVAL_SECONDS)

    except KeyboardInterrupt:
        # Handle user interruption (Ctrl+C)
        logger_instance.info("System performance monitoring stopped by user.")
        print("\nMonitoring stopped.")
    except Exception as e:
        # Log any other unexpected errors
        logger_instance.error(f"An unexpected error occurred: {e}", exc_info=True)
        print(f"An error occurred: {e}")
    finally:
        logger_instance.info("System performance monitoring finished.")

if __name__ == "__main__":
    # This block executes when the script is run directly.

    # Check if psutil is installed
    try:
        import psutil
    except ImportError:
        print("Error: The 'psutil' library is not installed.")
        print("Please install it by running: pip install psutil")
        exit(1) # Exit the script if psutil is not found

    # Set up the logger
    performance_logger = setup_logger()

    # Start monitoring
    monitor_and_log(performance_logger)
