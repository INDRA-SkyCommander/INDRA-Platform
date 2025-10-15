def sudo_exec(cmd):
    """
    Executes a command with sudo privileges. Raises errors on failures.

    Args:
        cmd: Command to execute (list of arguments or string)
    
    Returns:
        CompletedProcess instance with command result
    
    Raises:
        subprocess.CalledProcessError: If command fails
    """

    # Convert command to list if string
    cmd_list = cmd if isinstance(cmd, list) else str(cmd).split()
    
    print(f"Running: {' '.join(['sudo'] + cmd_list)}")

    try:
        # Runs sudo command and captures output
        subprocess.run(
            ['sudo'] + cmd_list,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
    except subprocess.CalledProcessError as e:
        # Error handling
        print(f"Error executing command: {' '.join(e.cmd)}")
        print(f"Stdout: {e.stdout}")
        print(f"Stderr: {e.stderr}")


# 

import subprocess
from typing import List, Union

def sudo_exec(cmd: Union[List[str], str], capture_output: bool = True) -> subprocess.CompletedProcess:
    """
    Executes a command with sudo privileges.
    
    Args:
        cmd: Command to execute (list of arguments or string)
        capture_output: Whether to capture and return command output
    
    Returns:
        CompletedProcess instance with command result
        
    Raises:
        subprocess.CalledProcessError: If command fails
    """
    # Convert command to list if string
    cmd_list = cmd if isinstance(cmd, list) else str(cmd).split()
    
    print(f"Running: {' '.join(['sudo'] + cmd_list)}")

    try:
        result = subprocess.run(
            ['sudo'] + cmd_list,
            check=True,
            stdout=subprocess.PIPE if capture_output else None,
            stderr=subprocess.PIPE if capture_output else None,
            text=True
        )
        return result
    except subprocess.CalledProcessError as e:
        print(f"Error executing command: {' '.join(e.cmd)}")
        if capture_output:
            print(f"Stdout: {e.stdout}")
            print(f"Stderr: {e.stderr}")
        raise

#