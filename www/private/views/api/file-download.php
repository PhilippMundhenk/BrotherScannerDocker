<?php
include('config.php');
require_once('helper.php');

if(!isset($file)) {
        send_json_error(400, "No file specified");
}

if(str_contains($file, "..") || str_contains($file, "/")) {
        send_json_error(400, "Invalid file specified");
}

$filename="/scans/".$file;

if(!file_exists($filename)){
        send_json_error(400, "File does not exist");
}


header("Content-type:application/pdf");
header("Content-Disposition:attachment;filename=\"$file\"");
readfile($filename);
die();

?>