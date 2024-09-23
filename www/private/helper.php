<?php


function json($data){

    header('Content-Type: application/json');
    print_r(json_encode($data, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE));
    die();

}


function send_json_error($http_code, $message){

    header('Content-Type: application/json');
    http_response_code($http_code);
    json(array('code' => $http_code, 'message' => $message));
    die();
}


function send_error_page($http_code, $page_title='', $page_message=''){
    http_response_code($http_code);
    if ($page_title != '' && $page_message != ''){
        require 'views/frontend/error.php';
    }
    die();
}

/**
 * Constructs a safe file path within a specified directory.
 *
 * This function takes a directory and a filename, constructs the full file path,
 * and ensures that the file path is within the specified directory. It prevents
 * directory traversal attacks by validating the real path of the constructed file path.
 *
 * @param string $directory The directory in which the file should be located.
 * @param string $filename The name of the file.
 * @return string|false The real path to the file if it is within the specified directory, or false if it is not.
 */
function file_get_real_filepath($directory, $filename) {

    $filename = basename($filename);
    $filePath = $directory . DIRECTORY_SEPARATOR . $filename;
    $realPath = realpath($filePath);

    if ($realPath === false || strpos($realPath, realpath($directory)) !== 0) {
        return false; 
    }

    return $realPath;
}


function file_get_verified_fileinfo($dir, $file) {

        
    $filename = file_get_real_filepath($dir, $file);
    
    if ($filename === false) {
            send_json_error(400, "No valid file specified");
    } 
    
    if(!file_exists($filename)){
            send_json_error(404, "File does not exist");
    }

    $pathInfo = pathinfo($filename);
    $filenameWithoutExtension = pathinfo($filename, PATHINFO_FILENAME);
    $fileCreationTime = filectime($filename);
    $fileModificationTime = filemtime($filename);
    $finfo = new finfo(FILEINFO_MIME_TYPE);
    $mimetype = $finfo->file($filename);

    $file_info = array(
            'full_path' => $filename,
            'file' => $pathInfo['basename'] ?? '',
            'name' => $filenameWithoutExtension ?? '',
            'name_clean' => '',
            'dir' => $pathInfo['dirname'] ?? '',
            'date_from_name' => '',
            'time_from_name' => '',
            'fileCreationTime' => $fileCreationTime,
            'fileModificationTime' => $fileModificationTime,
            'date_from_file' => date('Y-m-d', $fileModificationTime),
            'time_from_file' => date('H-i-s', $fileModificationTime),
            'extension' => $pathInfo['extension'] ?? '',
            'mimetype' => $mimetype,
            'size' => filesize($filename)
    );

    if (preg_match('/(\d{4}-\d{2}-\d{2})(?:-(\d{2})(?:-(\d{2})(?:-(\d{2}))?)?)?/', $filename, $matches)) {
            
            $file_info['date_from_name'] = $matches[1] ?? '';
            
            if (isset($matches[2])) {
                    $file_info['time_from_name'] = $matches[2] . ':' . ($matches[3] ?? '00') . ':' . ($matches[4] ?? '00');
            }
    }
    // Combine date and time with the dash to form the full datetime string
    $pattern = '/^\d{4}-\d{2}-\d{2}-\d{2}-\d{2}-\d{2}\s*/';
    $remove_datetime = $file_info['date_from_name'].'-'.$file_info['time_from_name'];
    $clean_name = preg_replace($pattern, '', $filenameWithoutExtension);

    // Remove only the date and time without extra spaces around
    $remove_date = $file_info['date_from_name'];
    $clean_name = str_replace($remove_date, '', $clean_name);

    $remove_time = $file_info['time_from_name'];
    $clean_name = str_replace($remove_time, '', $clean_name);

    // Trim any remaining leading or trailing spaces
    $clean_name = trim($clean_name);
    $file_info['name_clean'] = $clean_name;

    if($file_info['mimetype'] != 'application/pdf'){
        send_json_error(400, "No valid file specified");
    }
    

    return $file_info;
}


function file_is_valid_name_string($filename) {

    $pattern = '/[<>:"\/\\|?*\x00-\x1F]/'; // Invalid characters for filenames

    if (preg_match($pattern, $filename)) {
        return false;
    }

    if (strlen($filename) > 255) {
        return false;
    }

    if (strlen($filename) < 3) {
        return false;
    }
    

    return true;
}

function list_files($dir){
    $files = scandir($dir);
    $files = array_diff($files, array('.', '..'));
    
    $data = array();
    foreach ($files as $file) {
        $filePath = $dir . '/' . $file;
        if (is_file($filePath) && pathinfo($filePath, PATHINFO_EXTENSION) === 'pdf') {
            $data[] = file_get_verified_fileinfo($dir, $file);
        }
        
    }
    uasort($data, function($a, $b) {
        return $b['fileModificationTime'] <=> $a['fileModificationTime'];
    });
    return array_values($data);
}
?>