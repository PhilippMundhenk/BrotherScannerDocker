<?php
include('config.php');
require_once('helper.php');

#'/scans/'

if(!isset($file)) {
        send_json_error(400, "No file specified");
}

$file_info = file_get_verified_fileinfo('/scans/', urldecode($file));
$full_path = $file_info['full_path'];
$filename = $file_info['file'];
$mimetype = $file_info['mimetype'];

header("Content-type:$mimetype");
header("Content-Disposition:attachment;filename=\"$filename\"");
readfile($full_path);
die();

?>