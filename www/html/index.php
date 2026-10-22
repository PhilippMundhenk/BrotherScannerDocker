<?php
define('E_API', 1024);
define('E_FRONTEND', 1025);

function customErrorHandler($errno, $errstr, $errfile, $errline) {
    if (!(error_reporting() & $errno)) {
        return false;  // @-suppressed (PHP masks the level while the call runs), nothing to log
    }
    $date = date("Y-m-d H:i:s");

    $errorType = match ($errno) {
        E_WARNING => "Warning",
        E_NOTICE => "Notice",
        E_ERROR => "Error",
        E_API => "API",  // Custom log type
		E_FRONTEND => "Frontend",  // Custom log type
        default => "Unknown"
    };

	if (($errno == E_API) OR ($errno == E_FRONTEND)) {
		$logMessage = "[$errorType] $errstr\n";
	} else {
    	$logMessage = "[$date] [$errorType] $errstr in $errfile on line $errline\n";
	}

    error_log($logMessage, 3, '/var/log/scanner.log');
}

set_error_handler("customErrorHandler");
set_include_path('/var/www/private/');

include('config.php');
require_once('classes/AltoRouter.php');
require_once('helper.php');
require_once('settings.php');

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


$router->map( 'GET', '/settings', function() {
	require_once 'views/frontend/settings.php';
});


$router->map( 'GET', '/list-files', function() {
	require_once 'views/frontend/file-list.php';
});



// API routes
// Everything that starts a scan or changes a file calls api_token_required()
// first; it is a no-op unless API_TOKEN is configured.

$router->map( 'GET', '/api/actions', function() {
	require_once 'views/api/actions.php';
});


$router->map( 'GET', '/api/scanner/status', function() {
	require_once 'views/api/scanner-status.php';
});


$router->map( 'GET', '/api/scanner/device', function() {
	require_once 'views/api/scanner-device.php';
});


$router->map( 'POST', '/api/scanner/scanto', function() {
    api_token_required();
    $scanto = $_POST["target"] ?? '';
    $method = 'return';
	require_once 'views/api/scanner-scanto.php';
});


$router->map( 'GET', '/api/scanner/scanto/[char:parameter]', function( $parameter) {
    api_token_required();
    $scanto = $parameter;
    $method = 'wait';
	require_once 'views/api/scanner-scanto.php';
});


// Endpoints of the web UI before the rewrite, kept so existing automations
// (Home Assistant rest sensors, control panels) survive the upgrade (#148):
// active.php answers like /api/scanner/status, scan.php?target=<file|email|image|OCR>
// like GET /api/scanner/scanto/<target>. New setups use the /api routes.
$router->map( 'GET', '/active.php', function() {
    require_once 'views/api/scanner-status.php';
});


$router->map( 'GET', '/scan.php', function() {
    api_token_required();
    $query = $_GET;
    if (empty($query) && isset($_SERVER['REQUEST_URI'])) {
        $raw = parse_url($_SERVER['REQUEST_URI'], PHP_URL_QUERY);
        if (is_string($raw)) {
            parse_str($raw, $query);
        }
    }
    $scanto = strtolower(trim((string)($query['target'] ?? '')));
    $method = 'wait';
    require_once 'views/api/scanner-scanto.php';
});


$router->map( 'GET', '/api/settings', function() {
	require_once 'views/api/settings.php';
});


$router->map( 'POST', '/api/settings/import-environment', function() {
    api_token_required();
	require_once 'views/api/settings-import.php';
});


$router->map( 'PUT', '/api/settings', function() {
    api_token_required();
	require_once 'views/api/settings.php';
});


$router->map( 'GET', '/api/jobs', function() {
	require_once 'views/api/job-list.php';
});


$router->map( 'GET', '/api/jobs/[char:job_id]', function( $job_id) {
	require_once 'views/api/job-info.php';
});


$router->map( 'POST', '/api/jobs/[char:job_id]/rear', function( $job_id) {
    api_token_required();
	require_once 'views/api/job-rear.php';
});


$router->map( 'GET', '/api/file-list', function() {
	require_once 'views/api/file-list.php';
});

$router->map( 'GET', '/api/file/[char:file]/info', function( $file) {
	require_once 'views/api/file-info.php';
});


$router->map( 'GET', '/api/file/[char:file]/thumbnail', function( $file) {
	require_once 'views/api/file-thumbnail.php';
});


$router->map( 'GET', '/api/file/[char:file]/download', function( $file) {
	require_once 'views/api/file-download.php';
});


$router->map( 'DELETE', '/api/file/[char:file]/delete', function( $file) {
    api_token_required();
	require_once 'views/api/file-delete.php';
});


$router->map( 'PUT', '/api/file/[char:file]/rename', function( $file) {
    api_token_required();
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
}
?>
