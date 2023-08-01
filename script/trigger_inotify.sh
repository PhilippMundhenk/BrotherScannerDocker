user=$1
password=$2
address=$3
filepath=$4
file=$5
sshpass -p "$password" ssh -o StrictHostKeyChecking=no $user@$address "sed \"\" -i $filepath/$file"
