#!/usr/bin/python3


def sendtoftps(log, user, password, address, filepath, file):
    """Uploads a file to an FTP server.

    Args:
      user (str): The FTP username.
      password (str): The FTP password.
      address (str): The FTP address.
      filepath (str): The file path on the FTP server.
      file (str): The file to upload.
    """

    command = [
        "curl",
        "--silent",
        "--show-error",
        "--ssl-reqd",
        "--user",
        f"{user}:{password}",
        "--upload-file",
        file,
        f"ftp://{address}{filepath}",
    ]

    try:
        subprocess.run(command, check=True, stdout=log, stderr=log)
        print(f"Uploading to FTP server {address} successful.")
    except subprocess.CalledProcessError:
        print("Uploading to FTP failed while using curl")
        print(f"user: {user}")
        print(f"address: {address}")
        print(f"filepath: {filepath}")
        print(f"file: {file}")
        exit(1)
