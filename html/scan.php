<?php

ini_set('display_errors', 1);
ini_set('display_startup_errors', 1);
error_reporting(E_ALL);

include 'config.php';

if ($_SERVER['REQUEST_METHOD'] == 'POST') {
    $target = $_POST["target"];
} elseif ($_SERVER['REQUEST_METHOD'] == 'GET') {
    $target = $_GET["target"];
}

if (empty($target)) {
    header($_SERVER["SERVER_PROTOCOL"] . " 400 OK");
    die("Error: No scanning function selected (try append: ?target=<file|email|image|ocr>)");
}
if (in_array($target, array('file','email','image','ocr'))) {
    if ($_SERVER['REQUEST_METHOD'] == 'POST') {
        // return immediately
        $handle = popen('sudo -b -u \#'.$UID.' /opt/brother/scanner/brscan-skey/script/scanto'.$target.'.py', 'r');
    } elseif ($_SERVER['REQUEST_METHOD'] == 'GET') {
        // wait for completion
        $output=shell_exec('sudo -u \#'.$UID.' /opt/brother/scanner/brscan-skey/script/scanto'.$target.'.py');
    }
}
else
{
    header($_SERVER["SERVER_PROTOCOL"] . " 400 OK");
    die("Error: Thou shalt not inject unknown script names!");
}

//TODO: Fix serving of file on get
//if ($_SERVER['REQUEST_METHOD'] == 'GET') {
//      $files = scandir('/scans', SCANDIR_SORT_DESCENDING);
//      $newest_file = $files[0];
//      header($_SERVER["SERVER_PROTOCOL"] . " 200 OK");
//      header("Cache-Control: public"); // needed for internet explorer
//      header("Content-Type: application/pdf");
//      header("Content-Transfer-Encoding: Binary");
//      header("Content-Length:".filesize($newest_file));
//      readfile($newest_file);
//      die();
//}

?>
