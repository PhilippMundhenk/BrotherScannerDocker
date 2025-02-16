<?php
include('config.php');
require_once('helper.php');


if(!isset($file)) {
        send_json_error(400, "No file specified");
}

$file_info = file_get_verified_fileinfo('/scans/', urldecode($file));

json($file_info);

?>