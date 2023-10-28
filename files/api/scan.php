<?php
ini_set('display_errors', 1);
ini_set('display_startup_errors', 1);
error_reporting(E_ALL);

$target = htmlspecialchars($_GET["target"]);
if (empty($target)) {
	header($_SERVER["SERVER_PROTOCOL"] . " 400 OK");
	die("Error: No scanning function selected (try append: ?target=<file|email|image|ocr>");
}
if (in_array($target, array('file','email','image','ocr'))) {
    $output = shell_exec('/opt/brother/scanner/brscan-skey/script/scanto'.$target.'.sh');
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