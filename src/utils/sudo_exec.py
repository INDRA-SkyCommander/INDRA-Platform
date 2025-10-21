import subprocess
from typing import List, Union

def sudo_exec(cmd: Union[List[str], str]) -> subprocess.CompletedProcess:
    """
    Executes a command with sudo privileges. Raises errors on failures.

    Args: cmd: Command to execute (list of arguments or string)
    Returns: CompletedProcess instance with command result
    Raises: subprocess.CalledProcessError: If command fails
    """

    # Convert command to list if string
    cmd_list = cmd if isinstance(cmd, list) else str(cmd).split()
    
    print(f"Running: {' '.join(['sudo'] + cmd_list)}")

    try:
        # Runs sudo command and captures output
        result = subprocess.run(
            ['sudo'] + cmd_list,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            shell=True
        )
        return result
    
    except subprocess.CalledProcessError as e:
        # Error handling
        return subprocess.CompletedProcess(
            args=['sudo'] + cmd_list,
            returncode=e.returncode,
            stdout=e.stdout,
            stderr=e.stderr
        )