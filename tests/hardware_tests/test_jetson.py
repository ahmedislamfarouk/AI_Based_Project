import os
import subprocess
import time

def get_jetson_stats():
    print("--- Jetson Nano System Stats ---")
    
    # CPU Usage (using 'top')
    try:
        cpu_cmd = "top -bn1 | grep 'Cpu(s)' | awk '{print $2 + $4}'"
        cpu_usage = subprocess.check_output(cpu_cmd, shell=True).decode().strip()
        print(f"Total CPU Usage: {cpu_usage}%")
    except:
        print("Could not retrieve CPU usage.")
    
    # Memory Usage (using 'free')
    try:
        mem_cmd = "free -h | grep Mem | awk '{print $2, $3}'"
        mem_info = subprocess.check_output(mem_cmd, shell=True).decode().strip().split()
        print(f"Memory: Total {mem_info[0]}, Used {mem_info[1]}")
    except:
        print("Could not retrieve Memory info.")
    
    # Disk Usage (using 'df')
    try:
        disk_cmd = "df -h / | tail -1 | awk '{print $2, $3, $5}'"
        disk_info = subprocess.check_output(disk_cmd, shell=True).decode().strip().split()
        print(f"Disk: Total {disk_info[0]}, Used {disk_info[1]} ({disk_info[2]})")
    except:
        print("Could not retrieve Disk info.")

    # GPU Usage (Jetson specific)
    print("\nAttempting to get GPU stats (tegrastats)...")
    try:
        # Check if tegrastats exists
        if subprocess.run(['which', 'tegrastats'], stdout=subprocess.PIPE, stderr=subprocess.PIPE).returncode == 0:
            process = subprocess.Popen(['tegrastats'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
            time.sleep(1)
            process.terminate()
            stdout, _ = process.communicate()
            if stdout:
                last_line = stdout.strip().split('\n')[-1]
                print(f"Tegrastats: {last_line}")
        else:
            print("tegrastats not found. (Not a Jetson or not in PATH)")
    except Exception as e:
        print(f"Error checking tegrastats: {e}")

if __name__ == "__main__":
    get_jetson_stats()
