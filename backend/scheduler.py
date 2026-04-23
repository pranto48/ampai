import subprocess
import re
from apscheduler.schedulers.background import BackgroundScheduler
from database import get_network_targets, engine
from sqlalchemy import text
from datetime import datetime

scheduler = BackgroundScheduler()

def ping_target(ip_address: str) -> dict:
    try:
        # Run ping command with 3 packets, timeout 2s per packet
        result = subprocess.run(
            ['ping', '-c', '3', '-W', '2', ip_address],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        output = result.stdout
        
        if result.returncode == 0:
            # Parse average ping
            # Linux ping format usually: rtt min/avg/max/mdev = 0.525/0.600/0.700/0.050 ms
            # Mac ping format: round-trip min/avg/max/stddev = 0.525/0.600/0.700/0.050 ms
            avg_ping_match = re.search(r'(?:rtt|round-trip) min/avg/max/(?:mdev|stddev) = [0-9.]+?/([0-9.]+)', output)
            avg_ping = avg_ping_match.group(1) if avg_ping_match else "unknown"
            
            # Simple latency check
            try:
                latency = float(avg_ping)
                if latency < 20:
                    status = "Good"
                elif latency < 100:
                    status = "Fair"
                else:
                    status = "Poor"
            except:
                status = "Good"
                
            return {"status": status, "avg_ping": avg_ping, "details": "stable"}
        else:
            return {"status": "Offline", "avg_ping": "N/A", "details": "unreachable"}
    except Exception as e:
        return {"status": "Error", "avg_ping": "N/A", "details": str(e)}

def run_network_sweep():
    print("Running scheduled network sweep...")
    targets = get_network_targets()
    if not targets:
        print("No network targets configured.")
        return

    report_lines = ["Link Status Overview:"]
    for t in targets:
        ping_result = ping_target(t['ip_address'])
        if ping_result['status'] == 'Offline':
            line = f"{t['name']} Connectivity: Offline (Host unreachable)"
        else:
            line = f"{t['name']} Connectivity: {ping_result['status']} (Average Ping Time: {ping_result['avg_ping']}ms)"
        report_lines.append(line)
    
    final_report = "\n".join(report_lines)
    print("Network Sweep Complete:\n", final_report)
    
    # Save the report to the "System Reports" chat session in the DB
    session_id = "system_reports"
    try:
        with engine.connect() as conn:
            # Ensure session metadata exists
            upsert_meta = text(
                "INSERT INTO session_metadata (session_id, category) VALUES (:s, :c) "
                "ON CONFLICT (session_id) DO UPDATE SET category = EXCLUDED.category"
            )
            conn.execute(upsert_meta, {"s": session_id, "c": "System Reports"})
            
            # Save the message
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            ai_message = f"**Automated Network Report ({timestamp})**\n```\n{final_report}\n```"
            
            # Add a user trigger message to make the UI look normal
            ins_user = text("INSERT INTO message_store (session_id, message) VALUES (:s, :m)")
            conn.execute(ins_user, {"s": session_id, "m": f"Run daily network sweep for {timestamp}"})
            
            ins_ai = text("INSERT INTO message_store (session_id, message) VALUES (:s, :m)")
            conn.execute(ins_ai, {"s": session_id, "m": ai_message})
            
            conn.commit()
    except Exception as e:
        print(f"Error saving report to DB: {e}")

def start_scheduler():
    if not scheduler.running:
        # Run every day at 9:00 AM
        scheduler.add_job(run_network_sweep, 'cron', hour=9, minute=0)
        scheduler.start()
        print("Background scheduler started.")
