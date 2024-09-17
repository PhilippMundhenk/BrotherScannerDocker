<?php


function json($data){
    header('Content-Type: application/json');
    print_r(json_encode($data, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE));
    die();

}

function send_error_page($http_code, $page_title='', $page_message=''){
    http_response_code($http_code);
    if ($page_title != '' && $page_message != ''){
        require 'views/frontend/error.php';
    }
    die();
}

function send_json_error($http_code, $message){
    http_response_code($http_code);
    json(array('code' => $http_code, 'message' => $message));
    die();
}

?>