user=$1
password=$2
address=$3
filepath=$4
file=$5

if [ -z "${user}" ] || [ -z "${password}" ] || [ -z "${address}" ] || [ -z "${filepath}" ] || [ -z "${file}" ]; then
  echo "FTP environment variables not set, skipping inotify trigger."
else
  if curl --silent \
      --show-error \
      --ssl-reqd \
      --user "${user}:${password}" \
      --upload-file "${file}" \
      "ftp://${address}${filepath}" ; then
    echo "Uploading to ftp server ${address} successful."
  else
    echo "Uploading to ftp failed while using curl"
    echo "user: ${user}"
    echo "address: ${address}"
    echo "filepath: ${filepath}"
    echo "file: ${file}"
    exit 1
  fi
fi

