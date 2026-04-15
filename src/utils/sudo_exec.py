import subprocess
from typing import List, Union

def sudo_exec(cmd: Union[List[str], str]) -> subprocess.CompletedProcess:
	"""
	Executes a command with sudo privileges. Captures output and return code.

	Args: cmd: Command to execute (list of arguments or string)
	Returns: CompletedProcess instance with command result
	"""

	# Convert command to list if string
	cmd_list = cmd if isinstance(cmd, list) else str(cmd).split()
	
	print(f"Running: {' '.join(['sudo'] + cmd_list)}")

	try:
		# Runs sudo command and captures output and return code
		result = subprocess.run(
			' '.join(['sudo'] + cmd_list),
			shell=True,
			capture_output=True,
			text=True
		)
		
		if result.stdout:
			print(result.stdout)
		if result.stderr:
			print(result.stderr, end='')
		
		return result
	
	except Exception as e:
		# Error handling
		return subprocess.CompletedProcess(
			args=['sudo'] + cmd_list,
			returncode=1,
			stdout="",
			stderr=str(e)
		)