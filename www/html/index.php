<?php
ini_set('display_errors', '1');
ini_set('display_startup_errors', '1');
error_reporting(E_ALL);

set_include_path('/var/www/private/');
include('config.php');
require_once('classes/AltoRouter.php');
require_once('helper.php');

if (!isset($TZ)) {
	$TZ = 'Europe/Berlin';
}
date_default_timezone_set($TZ);

#session_start();

$router = new AltoRouter();
$router->addMatchTypes(array('char' => '(?:[^\/]*)'));


// Frontend routes

$router->map( 'GET', '/', function() {
	require_once 'views/frontend/home.php';
});


$router->map( 'GET', '/list-files', function() {
	require_once 'views/frontend/file-list.php';
});


$router->map( 'GET', '/file/[char:file]/rename', function( $file) {
	require_once 'views/frontend/file-rename.php';
});


$router->map( 'GET', '/file/[char:file]/delete', function( $file) {
	require_once 'views/frontend/file-delete.php';
});


// API routes

$router->map( 'GET', '/api/scanner/status', function() {
	require_once 'views/api/scanner-status.php';
});


$router->map( 'POST', '/api/scanner/scanto', function() {
    $scanto = $_POST["target"];
    $method = 'return';
	require_once 'views/api/scanner-scanto.php';
});


$router->map( 'GET', '/api/scanner/scanto/[char:parameter]', function( $parameter) {
    $scanto = $parameter;
    $method = 'wait';
	require_once 'views/api/scanner-scanto.php';
});


$router->map( 'GET', '/api/file-list', function() {
	require_once 'views/api/file-list.php';
});

$router->map( 'GET', '/api/file/[char:file]/info', function( $file) {
	require_once 'views/api/file-info.php';
});


$router->map( 'GET', '/api/file/[char:file]/download', function( $file) {
	require_once 'views/api/file-download.php';
});

$router->map( 'DELETE', '/api/file/[char:file]/delete', function( $file) {
	require_once 'views/api/file-delete.php';
});


$router->map( 'PUT', '/api/file/[char:file]/rename', function( $file) {
	require_once 'views/api/file-rename.php';
});


$router->map( 'GET', '/api/dev/timezone', function() {
	require_once 'views/api/dev-timezone.php';
});


$match = $router->match();


// Call closure or throw 404 status if route not found

if( is_array($match) && is_callable( $match['target'] ) ) {
    call_user_func_array( $match['target'], $match['params'] );
} else {
    if (str_contains($_SERVER['REQUEST_URI'], '/api')) {
        send_json_error(404, 'Not Found');
    } else {
        send_error_page(404, $page_title='404', $page_message='Sorry, the page you are looking for could not be found.');
    }
    exit();
}
?>