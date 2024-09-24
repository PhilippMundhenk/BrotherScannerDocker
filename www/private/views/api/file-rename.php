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


// Function to get file access and modification times
function getFileTimes($original_filename) {
    return [
        'access_time' => fileatime($original_filename), // Access time
        'modification_time' => filemtime($original_filename) // Modification time
    ];
}

$file_info = file_get_verified_fileinfo('/scans/', urldecode($file));

$original_filename = $file_info['full_path'];

$jsonData = file_get_contents('php://input');
$data = json_decode($jsonData, true);



if ($data !== null) {
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


    // Get access and modification times of the old file
    $times = getFileTimes($original_filename);

    // Rename the file
    if (rename($original_filename, $final_filename)) {
        
        // Restore access and modification time using 'touch'
        @touch($final_filename, $times['modification_time'], $times['access_time']);
        send_json_error(200, "Renamed file successfully");
    } else {
        send_json_error(400, "Error renaming the file");
    }  

}else{
    send_json_error(400, "Invalid filename");
}



?>