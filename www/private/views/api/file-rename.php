<?php
ini_set('display_errors', '1');
ini_set('display_startup_errors', '1');
error_reporting(E_ALL);

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

$original_filename = $file_info['full_path'];

$jsonData = file_get_contents('php://input');
$data = json_decode($jsonData, true);



if ($data !== null) {
   // Access the data and perform operations
   $new_filename = $data['new_filename'];
   $new_filename_prefix = $data['new_filename_prefix'];
   
   
} else {
    send_json_error(400, "JSON decoding error");
}

if (file_is_valid_name_string($new_filename)){


    $target_filename = preg_replace('/[^a-zA-Z0-9äöüßÄÖÜ\-\_ ]/u', '', $new_filename) . '.' . strtolower($file_info['extension']);
    
    $final_filename = $file_info['dir'] . '/' . $target_filename;
    

    if ($new_filename_prefix == 'date') {

        $final_filename = $file_info['dir'] . '/' . $file_info['date_from_file'] . ' ' . $target_filename;

    } elseif ($new_filename_prefix == 'datetime') {
        $final_filename = $file_info['dir'] . '/' . $file_info['date_from_file'] . '-' . $file_info['time_from_file'] . ' ' . $target_filename;
    }

    
    $UID = escapeshellarg($UID);  // Ensure UID is safe
    $original_filename = escapeshellarg($original_filename);  // Escape the filename for shell
    $final_filename = escapeshellarg($final_filename);        // Escape the new filename

    $command = 'sudo -u \#'.$UID.' mv '.$original_filename.' '.$final_filename;
    $output = shell_exec($command);


    json(array('status' => 'success'));
}else{
    send_json_error(400, "Invalid filename");
}



?>