import multiprocessing


# Generator mode setting
MODE_SINGLE_PROCESS = "MODE_SINGLE_PROCESS"
MODE_MULTIPROCESSING = "MODE_MULTIPROCESSING"
# Test generator mode
GENERATOR_MODE = MODE_SINGLE_PROCESS
# Number of subprocesses when using MODE_MULTIPROCESSING
NUM_PROCESS = multiprocessing.cpu_count() // 2 - 1

# Diagnostics
TIME_THRESHOLD_TO_PRINT = 1.0  # seconds
