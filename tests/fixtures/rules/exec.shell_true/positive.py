import subprocess


def extract(archive_name):
    subprocess.run(f"tar -xzf {archive_name}", shell=True)
