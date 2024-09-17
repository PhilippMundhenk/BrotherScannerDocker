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

session_start();

$router = new AltoRouter();
$router->addMatchTypes(array('char' => '(?:[^\/]*)'));


$router->map( 'GET', '/', function() {
	require 'views/frontend/home.php';
});


$router->map( 'GET', '/list-files', function() {
	require 'views/frontend/list.php';
});


$router->map( 'GET', '/api/scanner/status', function() {
	require 'views/api/scanner-status.php';
});


$router->map( 'POST', '/api/scanner/scanto', function() {
    $scanto = $_POST["target"];
    $method = 'return';
	require 'views/api/scanner-scanto.php';
});


$router->map( 'GET', '/api/scanner/scanto/[char:parameter]', function( $parameter) {
    $scanto = $parameter;
    $method = 'wait';
	require 'views/api/scanner-scanto.php';
});


$router->map( 'GET', '/api/file/[char:file]/download', function( $file) {
	require 'views/api/file-download.php';
});


$router->map( 'GET', '/api/dev/timezone', function() {
	require 'views/api/dev-timezone.php';
});


$match = $router->match();


if( is_array($match) && is_callable( $match['target'] ) ) {
	call_user_func_array( $match['target'], $match['params'] ); 
} else {
    send_error_page(404, 'Not Found', 'The requested resource could not be found.');

}

?>