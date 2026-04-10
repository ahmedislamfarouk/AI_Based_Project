import subprocess
import os

def run_test(name, script_path):
    print(f"\n{'='*20}")
    print(f"RUNNING: {name}")
    print(f"{'='*20}")
    try:
        # We use subprocess.run to wait for each test to finish
        subprocess.run(['python3', script_path], check=True)
    except Exception as e:
        print(f"Test {name} failed or was interrupted: {e}")

if __name__ == "__main__":
    # Get the directory where this script is located
    base_path = os.path.dirname(os.path.abspath(__file__))
    
    # 1. System Stats
    run_test("Jetson System Stats", os.path.join(base_path, "test_jetson.py"))
    
    print("\nNext: Camera Test. A window will open for 10 seconds. Press 'q' to skip/close.")
    input("Press Enter to continue...")
    run_test("Camera Test", os.path.join(base_path, "test_camera.py"))
    
    print("\nNext: Audio Test. It will record 3 seconds and then play it back.")
    input("Press Enter to continue...")
    run_test("Audio Test", os.path.join(base_path, "test_audio.py"))
    
    print("\nAll tests completed.")
