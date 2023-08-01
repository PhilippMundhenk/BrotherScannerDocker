user=$1
password=$2
address=$3
filepath=$4
file=$5

if [ -z "${user}" ] || [ -z "${password}" ] || [ -z "${address}" ] || [ -z "${filepath}" ]; then
  echo "SSH environment variables not set, skipping inotify trigger."
fi

if sshpass -p "$password" ssh -o StrictHostKeyChecking=no $user@$address "sed \"\" -i $filepath/$file"; then
  echo "trigger inotify successful"
else
  echo "trigger inotify failed"
  exit 1
fi
