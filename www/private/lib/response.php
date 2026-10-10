<?php
// JSON and error responses shared by every view.

function json($data){

    header('Content-Type: application/json');
    print_r(json_encode($data, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE));
    die();

}

function send_json_error($http_code, $message){

    header('Content-Type: application/json');
    http_response_code($http_code);
    json(array('code' => $http_code, 'message' => $message));  // json() exits
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
