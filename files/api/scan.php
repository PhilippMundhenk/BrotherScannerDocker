<?php
ini_set('display_errors', 1);
ini_set('display_startup_errors', 1);
error_reporting(E_ALL);

include 'config.php';

if (!array_key_exists('target', $_GET)) {
	header($_SERVER["SERVER_PROTOCOL"] . " 400 OK");
	die("Error: No scanning function selected (try append: ?target=<file|email|image|ocr>");
}

$target = $_GET["target"];
if (empty($target)) {
	header($_SERVER["SERVER_PROTOCOL"] . " 400 OK");
	die("Error: No scanning function selected (try append: ?target=<file|email|image|ocr>)");
}
if (in_array($target, array('file','email','image','ocr'))) {
	//$output=shell_exec('sudo -u \#'.$UID.' /opt/brother/scanner/brscan-skey/script/scanto'.$target.'.sh');
	$handle = popen('sudo -b -u \#'.$UID.' /opt/brother/scanner/brscan-skey/script/scanto'.$target.'.sh', 'r');
}
else
{
	header($_SERVER["SERVER_PROTOCOL"] . " 400 OK");
	die("Error: Thou shalt not inject unknown script names!");
}

echo('<html><head><meta http-equiv="Refresh" content="0; url=/" /></head></html>');

?>