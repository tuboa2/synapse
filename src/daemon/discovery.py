import psutil
import logging
from typing import List, Tuple
import os

logger = logging.getLogger(__name__)

class ProcessDiscovery:
    """
    Cross-platform discovery for target processes.
    Finds all active Python processes running locally.
    """
    
    @staticmethod
    def get_python_pids(max_count: int = 64) -> List[Tuple[int, str]]:
        """
        Scans all running processes and returns a list of (PID, Name)
        that correspond to Python applications.
        """
        python_procs = []
        my_pid = os.getpid()
        
        try:
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    if proc.info['pid'] == my_pid:
                        continue # Don't track ourselves
                    
                    name = proc.info.get('name', '')
                    cmdline = proc.info.get('cmdline', [])
                    
                    is_python = False
                    script_name = name
                    
                    if name and 'python' in name.lower():
                        is_python = True
                        if cmdline and len(cmdline) > 1:
                            script_name = os.path.basename(cmdline[1])
                    elif cmdline and any('python' in arg.lower() for arg in cmdline):
                        is_python = True
                        script_name = os.path.basename(cmdline[1]) if len(cmdline) > 1 else name
                        
                    if is_python:
                        python_procs.append((proc.info['pid'], script_name[:31]))
                        
                        if len(python_procs) >= max_count:
                            break
                            
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
                    
        except Exception as e:
            logger.error(f"Error discovering Python processes: {e}")
            
        return python_procs
