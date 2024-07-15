#!/usr/bin/python3

import bareos.bsock
from bareos.bsock.director import DirectorConsole
from prometheus_client import start_http_server, Gauge, Counter
import time
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)

# Bareos Director connection parameters
bareos_params = {
    'address': 'localhost',
    'port': 9101,
    'password': 'your_password',
    'name': 'admin'
}

# Define Prometheus metrics
# Job Status
SUCCESSFUL_JOBS = Counter('bareos_successful_jobs_total', 'Total number of successful jobs')
FAILED_JOBS = Counter('bareos_failed_jobs_total', 'Total number of failed jobs')
RUNNING_JOBS = Gauge('bareos_running_jobs', 'Current number of running jobs')

# Job Duration
JOB_DURATION = Gauge('bareos_job_duration_seconds', 'Duration of each backup job', ['job_name'])
AVERAGE_JOB_DURATION = Gauge('bareos_average_job_duration_seconds', 'Average job duration')
MAXIMUM_JOB_DURATION = Gauge('bareos_maximum_job_duration_seconds', 'Maximum job duration')

# Backup Size
BACKUP_SIZE = Gauge('bareos_backup_size_bytes', 'Total size of data backed up per job', ['job_name'])
AVERAGE_BACKUP_SIZE = Gauge('bareos_average_backup_size_bytes', 'Average backup size')
TOTAL_BACKUP_SIZE = Gauge('bareos_total_backup_size_bytes', 'Total size of all backups')

# Storage Information
FREE_SPACE = Gauge('bareos_free_space_bytes', 'Free space on storage devices')
USED_SPACE = Gauge('bareos_used_space_bytes', 'Used space on storage devices')
NUMBER_OF_VOLUMES = Gauge('bareos_volumes_total', 'Total number of volumes')

# File Information
FILES_BACKED_UP = Gauge('bareos_files_backed_up_total', 'Total number of files backed up per job', ['job_name'])
TOTAL_FILES_BACKED_UP = Gauge('bareos_total_files_backed_up', 'Total number of files backed up')

# Client Information
NUMBER_OF_CLIENTS = Gauge('bareos_clients_total', 'Total number of clients')
CLIENT_STATUS = Gauge('bareos_client_status', 'Status of each client', ['client_name', 'status'])

# Pool Information
NUMBER_OF_POOLS = Gauge('bareos_pools_total', 'Total number of pools')
POOL_SIZE = Gauge('bareos_pool_size_bytes', 'Size of each pool', ['pool_name'])
VOLUMES_IN_POOL = Gauge('bareos_volumes_in_pool_total', 'Total number of volumes in each pool', ['pool_name'])

# Volume Information
VOLUME_STATUS = Gauge('bareos_volume_status', 'Status of each volume', ['volume_name', 'status'])
LAST_WRITE_TIME = Gauge('bareos_last_write_time', 'Last write time for each volume', ['volume_name'])
VOLUME_RETENTION = Gauge('bareos_volume_retention_seconds', 'Retention period for each volume', ['volume_name'])

# Director Information
DIRECTOR_STATUS = Gauge('bareos_director_status', 'Status of Bareos Director')
DIRECTOR_UPTIME = Gauge('bareos_director_uptime_seconds', 'Uptime of Bareos Director')

# Network Statistics
BANDWIDTH_USAGE = Gauge('bareos_bandwidth_usage_bytes', 'Bandwidth usage during backup')
AVERAGE_TRANSFER_RATE = Gauge('bareos_average_transfer_rate_bytes_per_second', 'Average transfer rate per job')

# Scheduler Information
SCHEDULED_JOBS = Gauge('bareos_scheduled_jobs_total', 'Total number of scheduled jobs')
MISSED_JOBS = Counter('bareos_missed_jobs_total', 'Total number of missed jobs')
AVERAGE_QUEUE_TIME = Gauge('bareos_average_queue_time_seconds', 'Average queue time')

# Error Information
ERRORS_PER_JOB = Counter('bareos_errors_per_job_total', 'Total number of errors per job', ['job_name'])
ERROR_TYPES = Counter('bareos_error_types_total', 'Total number of each error type', ['error_type'])

# Resource Utilization
CPU_USAGE = Gauge('bareos_cpu_usage_percent', 'CPU usage during backup')
MEMORY_USAGE = Gauge('bareos_memory_usage_bytes', 'Memory usage during backup')
DISK_IO = Gauge('bareos_disk_io_bytes', 'Disk I/O during backup')

def query_bareos(command):
    try:
        director = DirectorConsole(
            address=bareos_params['address'],
            port=bareos_params['port'],
            name=bareos_params['name'],
            password=bareos_params['password']
        )
        result = director.call(command)
        director.disconnect()
        return result
    except Exception as e:
        logging.error(f"Error querying Bareos Director: {e}")
        return None

def collect_job_status():
    result = query_bareos("list jobs")
    if result:
        successful_jobs = sum(1 for job in result['job'] if job['JobStatus'] == 'T')
        failed_jobs = sum(1 for job in result['job'] if job['JobStatus'] == 'E')
        running_jobs = sum(1 for job in result['job'] if job['JobStatus'] == 'R')

        SUCCESSFUL_JOBS.inc(successful_jobs)
        FAILED_JOBS.inc(failed_jobs)
        RUNNING_JOBS.set(running_jobs)

def collect_job_duration():
    result = query_bareos("list jobs")
    if result:
        durations = []
        for job in result['job']:
            if job['EndTime'] and job['StartTime']:
                duration = job['EndTime'] - job['StartTime']
                durations.append(duration.total_seconds())
                JOB_DURATION.labels(job_name=job['JobName']).set(duration.total_seconds())

        if durations:
            AVERAGE_JOB_DURATION.set(sum(durations) / len(durations))
            MAXIMUM_JOB_DURATION.set(max(durations))

def collect_backup_size():
    result = query_bareos("list jobs")
    if result:
        sizes = [job['JobBytes'] for job in result['job'] if job['JobBytes']]
        if sizes:
            AVERAGE_BACKUP_SIZE.set(sum(sizes) / len(sizes))
            TOTAL_BACKUP_SIZE.set(sum(sizes))
            for job in result['job']:
                BACKUP_SIZE.labels(job_name=job['JobName']).set(job['JobBytes'])

def collect_storage_info():
    result = query_bareos("list volumes")
    if result:
        free_space = sum(volume['VolBytes'] for volume in result['volumes'] if volume['VolStatus'] == 'Append')
        used_space = sum(volume['VolBytes'] for volume in result['volumes'] if volume['VolStatus'] == 'Full')
        number_of_volumes = len(result['volumes'])

        FREE_SPACE.set(free_space)
        USED_SPACE.set(used_space)
        NUMBER_OF_VOLUMES.set(number_of_volumes)

def collect_file_info():
    result = query_bareos("list jobs")
    if result:
        total_files = sum(job['JobFiles'] for job in result['job'] if job['JobFiles'])
        for job in result['job']:
            FILES_BACKED_UP.labels(job_name=job['JobName']).set(job['JobFiles'])
        TOTAL_FILES_BACKED_UP.set(total_files)

def collect_client_info():
    result = query_bareos("list clients")
    if result:
        NUMBER_OF_CLIENTS.set(len(result['client']))
        for client in result['client']:
            CLIENT_STATUS.labels(client_name=client['Name'], status='online').set(1)

def collect_pool_info():
    result = query_bareos("list pools")
    if result:
        NUMBER_OF_POOLS.set(len(result['pool']))
        for pool in result['pool']:
            POOL_SIZE.labels(pool_name=pool['Name']).set(pool['MaxVolBytes'])

def collect_volume_info():
    result = query_bareos("list volumes")
    if result:
        for volume in result['volumes']:
            VOLUME_STATUS.labels(volume_name=volume['VolName'], status=volume['VolStatus']).set(1)
            LAST_WRITE_TIME.labels(volume_name=volume['VolName']).set(volume['LastWritten'].timestamp())
            VOLUME_RETENTION.labels(volume_name=volume['VolName']).set(volume['VolRetention'])

def collect_network_stats():
    result = query_bareos("list jobs")
    if result:
        bandwidth_usage = sum(job['JobBytes'] for job in result['job'] if job['JobStatus'] == 'R')
        transfer_rates = [
            job['JobBytes'] / (job['EndTime'] - job['StartTime']).total_seconds()
            for job in result['job'] if job['EndTime'] and job['StartTime']
        ]
        if transfer_rates:
            AVERAGE_TRANSFER_RATE.set(sum(transfer_rates) / len(transfer_rates))
        BANDWIDTH_USAGE.set(bandwidth_usage)

def collect_scheduler_info():
    result = query_bareos("list jobs")
    if result:
        scheduled_jobs = sum(1 for job in result['job'] if job['JobStatus'] == 'S')
        missed_jobs = sum(1 for job in result['job'] if job['JobStatus'] == 'M')
        queue_times = [
            (job['StartTime'] - job['SchedTime']).total_seconds()
            for job in result['job'] if job['StartTime'] and job['SchedTime']
        ]
        if queue_times:
            AVERAGE_QUEUE_TIME.set(sum(queue_times) / len(queue_times))
        SCHEDULED_JOBS.set(scheduled_jobs)
        MISSED_JOBS.inc(missed_jobs)

def collect_error_info():
    result = query_bareos("list jobs")
    if result:
        errors_per_job = {job['JobName']: job['Errors'] for job in result['job'] if job['Errors']}
        error_types = {job['JobName']: job['Error'] for job in result['job'] if job['Error']}

        for job_name, count in errors_per_job.items():
            ERRORS_PER_JOB.labels(job_name=job_name).inc(count)

        for error_type, count in error_types.items():
            ERROR_TYPES.labels(error_type=error_type).inc(count)

def collect_resource_utilization():
    # Assuming these metrics are not available directly from Bareos
    CPU_USAGE.set(0)
    MEMORY_USAGE.set(0)
    DISK_IO.set(0)

def collect_all_metrics():
    while True:
        collect_job_status()
        collect_job_duration()
        collect_backup_size()
        collect_storage_info()
        collect_file_info()
        collect_client_info()
        collect_pool_info()
        collect_volume_info()
        collect_network_stats()
        collect_scheduler_info()
        collect_error_info()
        collect_resource_utilization()
        time.sleep(30)  # Adjust the sleep interval as needed

if __name__ == '__main__':
    # Start the Prometheus metrics server
    start_http_server(9625)
    logging.info("Starting to collect metrics...")
    collect_all_metrics()
