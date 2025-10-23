#!/usr/bin/env python3
"""
CloudMouse Flash & Registration Tool - UNIVERSAL VERSION
Flash any firmware binary and register device
"""

import serial
import time
import json
import argparse
import subprocess
import mysql.connector
import os
import sys
from datetime import datetime
from pathlib import Path

# Try to import tqdm for progress bar
try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False

# Load config
config_file = Path(__file__).parent / 'config.json'
with open(config_file) as f:
    config = json.load(f)

# MySQL Config
DB_HOST = config['db_host']
DB_USER = config['db_user']
DB_PASS = config['db_pass']
DB_NAME = config['db_name']

# Produzione Config
OPERATOR_EMAIL = config['operator_email']

class DeviceProvisioner:
    def __init__(self, port, firmware_path, baud=115200):
        self.port = port
        self.firmware_path = firmware_path
        self.baud = baud
        self.serial = None
        self.db = None
        self.production_batch = f"BATCH-{datetime.now().strftime('%Y-%m-%d')}"
        
    def connect_db(self):
        """Connetti al database MySQL"""
        print("🗄️  Connecting to database...")
        try:
            self.db = mysql.connector.connect(
                host=DB_HOST,
                user=DB_USER,
                password=DB_PASS,
                database=DB_NAME
            )
            print("✅ Database connected!")
            return True
        except Exception as e:
            print(f"❌ Database connection failed: {e}")
            return False
    
    def flash_firmware(self):
        """Flash firmware usando esptool con progress bar"""
        print("🔥 Flashing firmware with esptool...")
        
        # Controlla che il binario esista
        if not os.path.exists(self.firmware_path):
            print(f"❌ Firmware binary not found: {self.firmware_path}")
            return False
        
        # Info file
        file_size = os.path.getsize(self.firmware_path) / 1024  # KB
        print(f"   Binary: {self.firmware_path}")
        print(f"   Size: {file_size:.2f} KB")
        print(f"   Port: {self.port}")
        
        # Comando esptool
        cmd = [
            "esptool.py",
            "--chip", "esp32s3",
            "--port", self.port,
            "--baud", "921600",
            "--before", "default_reset",
            "--after", "hard_reset",
            "write_flash",
            "-z",
            "--flash_mode", "dio",
            "--flash_freq", "80m",
            "--flash_size", "detect",
            "0x10000", self.firmware_path
        ]
        
        try:
            if HAS_TQDM:
                # Con progress bar! 🎉
                print("\n📊 Flashing progress:")
                
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    universal_newlines=True,
                    bufsize=1
                )
                
                pbar = None
                
                for line in process.stdout:
                    # Cerca linee con percentuale
                    if "Writing at" in line or "%" in line:
                        # Estrai percentuale
                        if "(" in line and "%" in line:
                            try:
                                percent_str = line.split("(")[1].split("%")[0].strip()
                                percent = int(percent_str)
                                
                                # Crea progress bar al primo uso
                                if pbar is None:
                                    pbar = tqdm(total=100, unit='%', bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt}% [{elapsed}]')
                                
                                # Aggiorna
                                pbar.n = percent
                                pbar.refresh()
                                
                            except (ValueError, IndexError):
                                pass
                
                process.wait()
                
                if pbar:
                    pbar.close()
                
                if process.returncode != 0:
                    print("❌ Flash failed!")
                    return False
                    
            else:
                # Senza progress bar (fallback)
                print("\n📊 Flashing... (install tqdm for progress bar: pip install tqdm)")
                result = subprocess.run(cmd, capture_output=True, text=True)
                
                if result.returncode != 0:
                    print("❌ Flash failed!")
                    print("\n=== STDOUT ===")
                    print(result.stdout)
                    print("\n=== STDERR ===")
                    print(result.stderr)
                    return False
            
            print("✅ Firmware flashed successfully!")
            time.sleep(3)
            return True
            
        except FileNotFoundError:
            print("❌ esptool.py not found!")
            print("   Install with: pip install esptool")
            return False
        except Exception as e:
            print(f"❌ Flash error: {e}")
            return False
    
    def connect_serial(self):
        """Connetti alla seriale"""
        print(f"📡 Connecting to {self.port}...")
        try:
            self.serial = serial.Serial(self.port, self.baud, timeout=2)
            time.sleep(2)
            self.serial.reset_input_buffer()
            self.serial.reset_output_buffer()
            print("✅ Serial connected!")
            return True
        except Exception as e:
            print(f"❌ Serial connection failed: {e}")
            return False
    
    def get_device_info(self):
        """Ottieni info device via seriale"""
        print("📱 Reading device info...")
        
        # Invia comando
        self.serial.write(b"get uuid\n")
        time.sleep(1)
        
        # Leggi risposta
        lines = []
        capturing = False
        timeout = time.time() + 5
        
        while time.time() < timeout:
            if self.serial.in_waiting > 0:
                line = self.serial.readline().decode('utf-8', errors='ignore').strip()
                
                if "DEVICE_INFO_START" in line:
                    capturing = True
                    continue
                    
                if "DEVICE_INFO_END" in line:
                    break
                    
                if capturing and line:
                    lines.append(line)
            else:
                time.sleep(0.1)
        
        if not lines:
            print("❌ No device info received")
            return None
        
        # Parse JSON
        json_str = '\n'.join(lines)
        try:
            device_info = json.loads(json_str)
            print(f"✅ UUID: {device_info['uuid']}")
            print(f"   Device ID: {device_info['device_id']}")
            print(f"   MAC: {device_info['mac_address']}")
            return device_info
        except json.JSONDecodeError as e:
            print(f"❌ Parse error: {e}")
            print(f"Raw data: {json_str}")
            return None
    
    def save_to_db(self, device_info):
        """Salva nel database"""
        print("💾 Saving to database...")
        
        try:
            cursor = self.db.cursor()
            
            query = """
                INSERT INTO devices 
                (uuid, device_id, mac_address, pcb_version, firmware_version, 
                 chip_model, chip_revision, production_batch, manufactured_at, manufactured_by)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            
            values = (
                device_info['uuid'],
                device_info['device_id'],
                device_info['mac_address'],
                device_info['pcb_version'],
                device_info['firmware_version'],
                device_info['chip_model'],
                device_info['chip_revision'],
                self.production_batch,
                datetime.utcnow(),
                OPERATOR_EMAIL
            )
            
            cursor.execute(query, values)
            self.db.commit()
            
            device_id = cursor.lastrowid
            print(f"✅ Saved! (DB ID: {device_id})")
            cursor.close()
            return device_id
            
        except mysql.connector.IntegrityError:
            print("⚠️  Device already in database!")
            return -1
        except Exception as e:
            print(f"❌ Database error: {e}")
            return None
    
    def show_stats(self):
        """Mostra statistiche"""
        cursor = self.db.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM devices")
        total = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM devices WHERE production_batch = %s", (self.production_batch,))
        batch_total = cursor.fetchone()[0]
        
        print(f"\n📊 Stats:")
        print(f"   Total devices: {total}")
        print(f"   Current batch ({self.production_batch}): {batch_total}")
        
        cursor.close()
    
    def close(self):
        if self.serial:
            self.serial.close()
        if self.db:
            self.db.close()

def main():
    parser = argparse.ArgumentParser(
        description='Flash and register CloudMouse device',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Flash and register
  python flash_and_register.py --port /dev/ttyUSB0 --bin build/firmware.bin
  
  # Only register (skip flash)
  python flash_and_register.py --port /dev/ttyUSB0 --bin build/firmware.bin --skip-flash
  
  # Show production stats
  python flash_and_register.py --stats
        """
    )
    
    parser.add_argument('--port', help='Serial port (e.g., /dev/ttyUSB0 or COM3)')
    parser.add_argument('--bin', '--firmware', dest='firmware', help='Path to firmware binary (.bin file)')
    parser.add_argument('--skip-flash', action='store_true', help='Skip firmware flash (only register)')
    parser.add_argument('--stats', action='store_true', help='Show production statistics')
    
    args = parser.parse_args()
    
    # Solo stats
    if args.stats:
        provisioner = DeviceProvisioner(None, None)
        if provisioner.connect_db():
            provisioner.show_stats()
            provisioner.close()
        return 0
    
    # Validazione parametri
    if not args.port:
        print("❌ Error: --port is required!")
        parser.print_help()
        return 1
    
    if not args.skip_flash and not args.firmware:
        print("❌ Error: --bin is required (or use --skip-flash)!")
        parser.print_help()
        return 1
    
    # Espandi path relativo/assoluto
    firmware_path = None
    if args.firmware:
        firmware_path = os.path.abspath(os.path.expanduser(args.firmware))
    
    print(f"""
╔════════════════════════════════════════╗
║      CloudMouse Provisioning v1.0      ║
╚════════════════════════════════════════╝
  Operator: {OPERATOR_EMAIL}
  Port: {args.port}
  Firmware: {firmware_path if firmware_path else 'N/A (skip flash)'}
""")
    
    # Avviso se tqdm non installato
    if not HAS_TQDM:
        print("💡 Tip: Install tqdm for fancy progress bar: pip install tqdm\n")
    
    provisioner = DeviceProvisioner(args.port, firmware_path)
    
    try:
        # Connetti DB
        if not provisioner.connect_db():
            return 1
        
        # Flash firmware
        if not args.skip_flash:
            if not provisioner.flash_firmware():
                return 1
        
        # Connetti seriale
        if not provisioner.connect_serial():
            return 1
        
        # Leggi info device
        device_info = provisioner.get_device_info()
        if not device_info:
            return 1
        
        # Salva in DB
        device_db_id = provisioner.save_to_db(device_info)
        if device_db_id is None:
            return 1
        
        # Stats
        provisioner.show_stats()
        
        print(f"""
╔════════════════════════════════════════╗
║            ✅ SUCCESS! ✅              ║
╚════════════════════════════════════════╝
  UUID: {device_info['uuid']}
  Device ID: {device_info['device_id']}
  DB ID: {device_db_id if device_db_id > 0 else 'Already registered'}
  
  Device ready for packaging! 📦
""")
        
        return 0
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        return 1
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        provisioner.close()

if __name__ == '__main__':
    exit(main())