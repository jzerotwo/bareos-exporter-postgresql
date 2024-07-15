#!/usr/bin/python3

import psycopg2
from prometheus_client import start_http_server, Gauge, Counter
import time
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)

# Database connection parameters
db_params = {
    'dbname': 'bareos',
    'user': 'prometheus',
    'password': 'prometheus',
    'host': '127.0.0.1',
    'port': 5432
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

def query_database(query, params=None):
    try:
        conn = psycopg2.connect(**db_params)
        cursor = conn.cursor()
        cursor.execute(query, params)
        result = cursor.fetchall()
        cursor.close()
        conn.close()
        return result
    except Exception as e:
        logging.error(f"Error querying database: {e}")
        return []

def collect_job_status():
    successful_jobs = query_database("SELECT COUNT(*) FROM job WHERE jobstatus = 'T'")[0][0] or 0
    failed_jobs = query_database("SELECT COUNT(*) FROM job WHERE jobstatus = 'E'")[0][0] or 0
    running_jobs = query_database("SELECT COUNT(*) FROM job WHERE jobstatus = 'R'")[0][0] or 0

    SUCCESSFUL_JOBS.inc(successful_jobs)
    FAILED_JOBS.inc(failed_jobs)
    RUNNING_JOBS.set(running_jobs)

def collect_job_duration():
    job_durations = query_database("SELECT jobid, EXTRACT(EPOCH FROM (endtime - starttime)) AS duration FROM job WHERE endtime IS NOT NULL")
    durations = [duration[1] for duration in job_durations if duration[1] is not None]
    if durations:
        AVERAGE_JOB_DURATION.set(sum(durations) / len(durations))
        MAXIMUM_JOB_DURATION.set(max(durations))
        for job in job_durations:
            if job[1] is not None:
                JOB_DURATION.labels(job_name=job[0]).set(job[1])

def collect_backup_size():
    backup_sizes = query_database("SELECT jobid, jobbytes FROM job")
    sizes = [size[1] for size in backup_sizes if size[1] is not None]
    if sizes:
        AVERAGE_BACKUP_SIZE.set(sum(sizes) / len(sizes))
        TOTAL_BACKUP_SIZE.set(sum(sizes))
        for job in backup_sizes:
            if job[1] is not None:
                BACKUP_SIZE.labels(job_name=job[0]).set(job[1])

def collect_storage_info():
    free_space = query_database("SELECT SUM(volbytes) FROM media WHERE volstatus = 'Append'")[0][0] or 0
    used_space = query_database("SELECT SUM(volbytes) FROM media WHERE volstatus = 'Full'")[0][0] or 0
    number_of_volumes = query_database("SELECT COUNT(*) FROM media")[0][0] or 0

    FREE_SPACE.set(free_space)
    USED_SPACE.set(used_space)
    NUMBER_OF_VOLUMES.set(number_of_volumes)

def collect_file_info():
    files_per_job = query_database("SELECT jobid, jobfiles FROM job")
    total_files = sum([files[1] for files in files_per_job if files[1] is not None])

    for job in files_per_job:
        if job[1] is not None:
            FILES_BACKED_UP.labels(job_name=job[0]).set(job[1])
    TOTAL_FILES_BACKED_UP.set(total_files)

def collect_pool_info():
    pools = query_database("SELECT name, maxvolbytes FROM pool")
    NUMBER_OF_POOLS.set(len(pools))
    for pool in pools:
        if pool[1] is not None:
            POOL_SIZE.labels(pool_name=pool[0]).set(pool[1])

def collect_volume_info():
    volumes = query_database("SELECT volumename, volstatus, lastwritten, volretention FROM media")
    for volume in volumes:
        VOLUME_STATUS.labels(volume_name=volume[0], status=volume[1]).set(1)
        if volume[2] is not None:
            LAST_WRITE_TIME.labels(volume_name=volume[0]).set(volume[2].timestamp())
        if volume[3] is not None:
            VOLUME_RETENTION.labels(volume_name=volume[0]).set(volume[3])

def collect_network_stats():
    bandwidth_usage = query_database("SELECT SUM(jobbytes) FROM job WHERE jobstatus = 'R'")[0][0] or 0
    transfer_rates = query_database("SELECT jobid, (jobbytes / EXTRACT(EPOCH FROM (endtime - starttime))) AS rate FROM job WHERE endtime IS NOT NULL")
    rates = [rate[1] for rate in transfer_rates if rate[1] is not None]
    if rates:
        AVERAGE_TRANSFER_RATE.set(sum(rates) / len(rates))
    BANDWIDTH_USAGE.set(bandwidth_usage)

def collect_scheduler_info():
    scheduled_jobs = query_database("SELECT COUNT(*) FROM job WHERE jobstatus = 'S'")[0][0] or 0
    missed_jobs = query_database("SELECT COUNT(*) FROM job WHERE jobstatus = 'M'")[0][0] or 0
    queue_times = query_database("SELECT jobid, EXTRACT(EPOCH FROM (starttime - schedtime)) AS queue_time FROM job WHERE starttime IS NOT NULL")
    queue_durations = [queue_time[1] for queue_time in queue_times if queue_time[1] is not None]
    if queue_durations:
        AVERAGE_QUEUE_TIME.set(sum(queue_durations) / len(queue_durations))
    SCHEDULED_JOBS.set(scheduled_jobs)
    MISSED_JOBS.inc(missed_jobs)

def collect_error_info():
    errors_per_job = query_database("SELECT jobid, COUNT(*) FROM job WHERE jobstatus = 'E' GROUP BY jobid")
    errors_per_job = query_database("SELECT jobid, COUNT(*) FROM job WHERE jobstatus = 'E' GROUP BY jobid")
    error_types = query_database("SELECT logtext, COUNT(*) FROM log WHERE jobid IN (SELECT jobid FROM job WHERE jobstatus = 'E') GROUP BY logtext")

    for error in errors_per_job:
        ERRORS_PER_JOB.labels(job_name=error[0]).inc(error[1])

    for error in error_types:
        ERROR_TYPES.labels(error_type=error[0]).inc(error[1])


def collect_all_metrics():
    while True:
        collect_job_status()
        collect_job_duration()
        collect_backup_size()
        collect_storage_info()
        collect_file_info()
        collect_pool_info()
        collect_volume_info()
        collect_network_stats()
        collect_scheduler_info()
        collect_error_info()
        time.sleep(30)  # Adjust the sleep interval as needed

if __name__ == '__main__':
    # Start the Prometheus metrics server
    start_http_server(9625)
    logging.info("Starting to collect metrics...")
    collect_all_metrics()
