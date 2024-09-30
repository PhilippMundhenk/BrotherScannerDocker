<?php
include('config.php');
require_once('helper.php');

if (isset($ALLOW_GUI_FILEOPERATIONS) && $ALLOW_GUI_FILEOPERATIONS) {
    $file_op = True;
} else {
    send_json_error(403, "File operations are disabled in config");
}

if(!isset($file)) {
        send_json_error(400, "No file specified");
}

$file_info = file_get_verified_fileinfo('/scans/', urldecode($file));



if(unlink($file_info['full_path'])){
    json(array('status' => 'success'));
} else {
    trigger_error("can not deleted file ".$file_info['full_path'], E_API);
    send_json_error(500, "Could not delete file");   
}

?>