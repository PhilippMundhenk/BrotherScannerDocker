<?php
ini_set('display_errors', 1);
ini_set('display_startup_errors', 1);
error_reporting(E_ALL);

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
    $output = exec('sudo -u NAS /opt/brother/scanner/brscan-skey/script/scanto'.$target.'.sh >> /var/log/scanner.log 2>&1');
}
else
{
	header($_SERVER["SERVER_PROTOCOL"] . " 400 OK");
	die("Error: Thou shalt not inject unknown script names!");
}

header($_SERVER["SERVER_PROTOCOL"] . " 200 OK");
header("Cache-Control: public"); // needed for internet explorer
header("Content-Type: text/plain");
die($output);

?>